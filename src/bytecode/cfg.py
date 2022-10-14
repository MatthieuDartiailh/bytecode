import sys
import types
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    SupportsIndex,
    Tuple,
    TypeVar,
    Union,
    overload,
)

# alias to keep the 'bytecode' variable free
import bytecode as _bytecode
from bytecode.concrete import ConcreteInstr
from bytecode.flags import CompilerFlags
from bytecode.instr import UNSET, Instr, Label, SetLineno, TryBegin, TryEnd

T = TypeVar("T", bound="BasicBlock")
U = TypeVar("U", bound="ControlFlowGraph")


class BasicBlock(_bytecode._InstrList[Union[Instr, SetLineno, TryBegin, TryEnd]]):
    def __init__(
        self, instructions: Iterable[Union[Instr, SetLineno, TryBegin, TryEnd]] = None
    ) -> None:
        # a BasicBlock object, or None
        self.next_block: Optional["BasicBlock"] = None
        if instructions:
            super().__init__(instructions)

    def __iter__(self) -> Iterator[Union[Instr, SetLineno, TryBegin, TryEnd]]:
        index = 0
        while index < len(self):
            instr = self[index]
            index += 1

            if not isinstance(instr, (SetLineno, Instr, TryBegin, TryEnd)):
                raise ValueError(
                    "BasicBlock must only contain SetLineno and Instr objects, "
                    "but %s was found" % instr.__class__.__name__
                )

            if isinstance(instr, Instr) and instr.has_jump():
                if index < len(self) and any(
                    isinstance(self[i], Instr) for i in range(index + 1, len(self))
                ):
                    raise ValueError(
                        "Only the last instruction of a basic " "block can be a jump"
                    )

                if not isinstance(instr.arg, BasicBlock):
                    raise ValueError(
                        "Jump target must a BasicBlock, got %s",
                        type(instr.arg).__name__,
                    )

            yield instr

    @overload
    def __getitem__(
        self, index: SupportsIndex
    ) -> Union[Instr, SetLineno, TryBegin, TryEnd]:
        ...

    @overload
    def __getitem__(self: T, index: slice) -> T:
        ...

    def __getitem__(self, index):
        value = super().__getitem__(index)
        if isinstance(index, slice):
            value = type(self)(value)
            value.next_block = self.next_block

        return value

    def get_last_non_artificial_instruction(self) -> Instr | None:
        for instr in reversed(self):
            if isinstance(instr, Instr):
                return instr

        return None

    def copy(self: T) -> T:
        new = type(self)(super().copy())
        new.next_block = self.next_block
        return new

    def legalize(self, first_lineno: int) -> int:
        """Check that all the element of the list are valid and remove SetLineno."""
        lineno_pos = []
        set_lineno = None
        current_lineno = first_lineno

        for pos, instr in enumerate(self):
            if isinstance(instr, SetLineno):
                set_lineno = current_lineno = instr.lineno
                lineno_pos.append(pos)
                continue
            if isinstance(instr, (TryBegin, TryEnd)):
                continue

            if set_lineno is not None:
                instr.lineno = set_lineno
            elif instr.lineno is UNSET:
                instr.lineno = current_lineno
            elif instr.lineno is not None:
                current_lineno = instr.lineno

        for i in reversed(lineno_pos):
            del self[i]

        return current_lineno

    def get_jump(self) -> Optional["BasicBlock"]:
        if not self:
            return None

        last_instr = self.get_last_non_artificial_instruction()
        if last_instr is None or not last_instr.has_jump():
            return None

        target_block = last_instr.arg
        assert isinstance(target_block, BasicBlock)
        return target_block


def _update_size(pre_delta, post_delta, size, maxsize):
    size += pre_delta
    if size < 0:
        msg = "Failed to compute stacksize, got negative size"
        raise RuntimeError(msg)
    size += post_delta
    maxsize = max(maxsize, size)
    return size, maxsize


def _compute_stack_size(
    seen_blocks: Set[int],
    blocks_startsizes: Dict[int, Set[int]],
    seen_try_begin: List[TryBegin],
    block: BasicBlock,
    size: int,
    maxsize: int,
    exception_handler: Optional[bool],
    enter_with_block: bool,
    exception_block_startsize: Dict[int, int],
    exception_block_maxsize: Dict[int, int],
    *,
    check_pre_and_post: bool = True,
):
    """Generator used to reduce the use of function stacks.

    This allows to avoid nested recursion and allow to treat more cases.

    HOW-TO:
        Following the methods of Trampoline
        (see https://en.wikipedia.org/wiki/Trampoline_(computing)),

        We yield either:

        - the arguments that would be used in the recursive calls, i.e,
          'yield block, size, maxsize' instead of making a recursive call
          '_compute_stack_size(block, size, maxsize)', if we encounter an
          instruction jumping to another block or if the block is linked to
          another one (ie `next_block` is set)
        - the required stack from the stack if we went through all the instructions
          or encountered an unconditional jump.

        In the first case, the calling function is then responsible for creating a
        new generator with those arguments, iterating over it till exhaustion to
        determine the stacksize required by the block and resuming this function
        with the determined stacksize.

    """
    # If the block is currently being visited (seen = True) or
    # it was visited previously by the same starting size than the one in use,
    # return the maxsize.
    # FIXME figure why exception handlers behave differently
    if id(block) in seen_blocks or (
        exception_handler is None and size in blocks_startsizes[id(block)]
    ):
        yield maxsize

    # Prevent recursive visit of block if two blocks are nested (jump from one
    # to the other).
    # Blocks are not hashable but in this particular instance we know we won't be
    # modifying blocks in place so we can safely use their id as hash rather than
    # making them generally hashable which would be weird since they are list
    # subclasses
    block_id = id(block)
    seen_blocks.add(block_id)

    # For exception handler block we look for the minimal stacksize which is the
    # one that can be safely restored by the unwinding.
    block_id = id(block)
    blocks_startsizes[block_id].add(size)
    if (
        exception_handler is not None
        and (known_size := exception_block_startsize[block_id]) >= 0
    ):
        exception_block_startsize[block_id] = min(size, known_size)
    else:
        exception_block_startsize[block_id] = size

    # If this block is an exception handler reached through the exception table
    # we will push some extra objects on the stack before processing start.
    if exception_handler is not None:
        size += 1 + exception_handler  # True is used to indicated a push_lasti of True

    for i, instr in enumerate(block):

        # Ignore SetLineno
        if isinstance(instr, (SetLineno)):
            continue

        # Compute the stack size required by the exception handling block and
        # store TryBegin so that we can update the stack size at the entrance of
        # the exception handling block if requested.
        if isinstance(instr, TryBegin):
            seen_try_begin.append(instr)

            # If this is the first TryBegin we see after a 'before with' we need
            # to adjust the stack depth because the opcode will have occurred
            # right after calling __enter__ pushed and will placed __exit__ on
            # the stack which is the only thing that need to be preserved and not
            # the value pushed by __enter__
            s = size
            if enter_with_block:
                s -= 1
                enter_with_block = False

            # For exception handling block we care about the result obtained with
            # the smallest block startsize which is the relevant one and which
            # will yield the smallest overall stack depth usage.
            block_id = id(instr.target)
            block_size = (
                yield seen_blocks,
                blocks_startsizes,
                seen_try_begin,
                instr.target,
                s,
                maxsize,
                instr.push_lasti,
                enter_with_block,
                exception_block_startsize,
                exception_block_maxsize,
            )
            if exception_block_maxsize[block_id] >= 0:
                exception_block_maxsize[block_id] = min(
                    exception_block_maxsize[block_id], block_size
                )
            else:
                exception_block_maxsize[block_id] = block_size
            continue

        elif isinstance(instr, TryEnd):
            # Keep as entry for the exception block the smallest stack size which
            # is the only safe one to restore. This is necessary because some blocks
            # have a net decreasing stack usage.
            # XXX this needs to restart a computation for the exception block
            # we should track TryBegin corresponding to a with in a persistent
            # manner
            # All this needs to be refactored as a class I think
            b_id = id(instr.entry.target)
            if size < exception_block_startsize[b_id]:
                exception_block_startsize[b_id] = size
                block_id = b_id
                block_size = (
                    yield seen_blocks,
                    blocks_startsizes,
                    seen_try_begin,
                    instr.entry.target,
                    size,
                    maxsize,
                    instr.entry.push_lasti,
                    enter_with_block,
                    exception_block_startsize,
                    exception_block_maxsize,
                )
                if exception_block_maxsize[block_id] >= 0:
                    exception_block_maxsize[block_id] = min(
                        exception_block_maxsize[block_id], block_size
                    )
                else:
                    exception_block_maxsize[block_id] = block_size
            continue

        # For instructions with a jump first compute the stacksize required when the
        # jump is taken.
        if instr.has_jump():
            effect = (
                instr.pre_and_post_stack_effect(jump=True)
                if check_pre_and_post
                else (instr.stack_effect(jump=True), 0)
            )
            taken_size, maxsize = _update_size(*effect, size, maxsize)

            # Yield the parameters required to compute the stacksize required
            # by the block to which the jumnp points to and resume when we now
            # the maxsize.
            maxsize = (
                yield seen_blocks,
                blocks_startsizes,
                seen_try_begin,
                instr.arg,
                taken_size,
                maxsize,
                None,
                enter_with_block,
                exception_block_startsize,
                exception_block_maxsize,
            )

            # For unconditional jumps abort early since the other instruction will
            # never be seen.
            if instr.is_uncond_jump():
                # Check for TryEnd and keep as entry for the exception block the
                # smallest stack size which is the only safe one to restore. This is
                # necessary because some block has a net decreasing stack usage.
                if i + 1 < len(block) and isinstance(b := block[i + 1], TryEnd):
                    b_id = id(b.entry.target)
                    if size < exception_block_startsize[b_id]:
                        exception_block_startsize[b_id] = size
                        block_id = b_id
                        block_size = (
                            yield seen_blocks,
                            blocks_startsizes,
                            seen_try_begin,
                            b.entry.target,
                            size,
                            maxsize,
                            b.entry.push_lasti,
                            enter_with_block,
                            exception_block_startsize,
                            exception_block_maxsize,
                        )
                        if exception_block_maxsize[block_id] >= 0:
                            exception_block_maxsize[block_id] = min(
                                exception_block_maxsize[block_id], block_size
                            )
                        else:
                            exception_block_maxsize[block_id] = block_size
                seen_blocks.remove(id(block))
                yield maxsize

        # jump=False: non-taken path of jumps, or any non-jump
        effect = (
            instr.pre_and_post_stack_effect(jump=False)
            if check_pre_and_post
            else (instr.stack_effect(jump=False), 0)
        )
        size, maxsize = _update_size(*effect, size, maxsize)

        if instr.name in ("BEFORE_WITH", "BEFORE_ASYNC_WITH"):
            enter_with_block = True

        # Instruction is final (return, raise, ...) so any following instruction
        # in the block is dead code.
        if instr.is_final():
            seen_blocks.remove(id(block))
            # Check for TryEnd and keep as entry for the exception the smallest
            # stack size which is the only safe one to restore. This is necessary
            # because some block has a net decreasing stack usage.
            if i + 1 < len(block) and isinstance(b := block[i + 1], TryEnd):
                b_id = id(b.entry.target)
                if size < exception_block_startsize[b_id]:
                    exception_block_startsize[b_id] = size
                    block_id = b_id
                    block_size = (
                        yield seen_blocks,
                        blocks_startsizes,
                        seen_try_begin,
                        b.entry.target,
                        s,
                        maxsize,
                        b.entry.push_lasti,
                        enter_with_block,
                        exception_block_startsize,
                        exception_block_maxsize,
                    )
                    if exception_block_maxsize[block_id] >= 0:
                        exception_block_maxsize[block_id] = min(
                            exception_block_maxsize[block_id], block_size
                        )
                    else:
                        exception_block_maxsize[block_id] = block_size
            yield maxsize

    if block.next_block:
        maxsize = (
            yield seen_blocks,
            blocks_startsizes,
            seen_try_begin,
            block.next_block,
            size,
            maxsize,
            None,
            enter_with_block,
            exception_block_startsize,
            exception_block_maxsize,
        )

    seen_blocks.remove(id(block))

    yield maxsize


class ControlFlowGraph(_bytecode.BaseBytecode):
    def __init__(self) -> None:
        super().__init__()
        self._blocks: List[BasicBlock] = []
        self._block_index: Dict[int, int] = {}
        self.argnames: List[str] = []

        self.add_block()

    def legalize(self) -> None:
        """Legalize all blocks."""
        current_lineno = self.first_lineno
        for block in self._blocks:
            current_lineno = block.legalize(current_lineno)

    def get_block_index(self, block: BasicBlock) -> int:
        try:
            return self._block_index[id(block)]
        except KeyError:
            raise ValueError("the block is not part of this bytecode")

    def _add_block(self, block: BasicBlock) -> None:
        block_index = len(self._blocks)
        self._blocks.append(block)
        self._block_index[id(block)] = block_index

    def add_block(
        self, instructions: Iterable[Union[Instr, SetLineno]] = None
    ) -> BasicBlock:
        block = BasicBlock(instructions)
        self._add_block(block)
        return block

    def compute_stacksize(
        self,
        *,
        check_pre_and_post: bool = True,
        compute_exception_stack_depths: bool = True,
    ) -> int:
        """Compute the stack size by iterating through the blocks

        The implementation make use of a generator function to avoid issue with
        deeply nested recursions.

        """
        # In the absence of any block return 0
        if not self:
            return 0

        # Ensure that previous calculation do not impact this one.
        seen_try_begin: List[TryBegin] = []
        seen_blocks: Set[int] = set()
        blocks_startsizes: Dict[int, Set[int]] = {id(b): set() for b in self}
        exception_block_startsize = dict.fromkeys([id(b) for b in self], -32768)
        exception_block_maxsize = dict.fromkeys([id(b) for b in self], -32768)

        # Starting with Python 3.10, generator and coroutines start with one object
        # on the stack (None, anything is an error).
        initial_stack_size = 0
        if sys.version_info >= (3, 10) and self.flags & (
            CompilerFlags.GENERATOR
            | CompilerFlags.COROUTINE
            | CompilerFlags.ASYNC_GENERATOR
        ):
            initial_stack_size = 1

        # Create a generator/coroutine responsible of dealing with the first block
        coro = _compute_stack_size(
            seen_blocks,
            blocks_startsizes,
            seen_try_begin,
            self[0],
            initial_stack_size,
            0,
            None,
            False,
            exception_block_startsize,
            exception_block_maxsize,
            check_pre_and_post=check_pre_and_post,
        )

        # Create a list of generator that have not yet been exhausted
        coroutines: List[Generator[Optional[Tuple], int, None]] = []

        push_coroutine = coroutines.append
        pop_coroutine = coroutines.pop
        args = None

        try:
            while True:
                args = coro.send(None)

                # Consume the stored generators as long as they return a simple
                # integer that is to be used to resume the last stored generator.
                while isinstance(args, int):
                    coro = pop_coroutine()
                    args = coro.send(args)

                # Otherwise we enter a new block and we store the generator under
                # use and create a new one to process the new block
                push_coroutine(coro)
                coro = _compute_stack_size(*args, check_pre_and_post=check_pre_and_post)

        except IndexError:
            # The exception occurs when all the generators have been exhausted
            # in which case the last yielded value is the stacksize.
            assert args is not None

            # Exception handling block size is reported separately since we need
            # to report only the stack usage for the smallest start size for the
            # block
            args = max(args, *exception_block_maxsize.values())

            # If requested update the TryBegin stack size
            if compute_exception_stack_depths:
                for tb in seen_try_begin:
                    size = exception_block_startsize[id(tb.target)]
                    assert size >= 0
                    tb.stack_depth = size

            return args

    def __repr__(self) -> str:
        return "<ControlFlowGraph block#=%s>" % len(self._blocks)

    # Helper to obtain a flat list of instr, which does not refer to block at
    # anymore.
    def _get_instructions(
        self,
    ) -> List[Union[Instr, ConcreteInstr, SetLineno, TryBegin, TryEnd]]:
        instructions: List[
            Union[Instr, ConcreteInstr, SetLineno, TryBegin, TryEnd]
        ] = []
        jumps: List[Tuple[BasicBlock, ConcreteInstr]] = []

        # XXX handle TryBegin
        for block in self:
            target_block = block.get_jump()
            if target_block is not None:
                instr = block[-1]
                assert isinstance(instr, Instr)
                # We use a concrete instr here to be able to use an integer as argument
                # rather than a Label. This is fine for comparison purposes which is
                # our sole goal here.
                jumps.append(
                    (
                        target_block,
                        ConcreteInstr(instr.name, 0, location=instr.location),
                    )
                )

                instructions.extend(block[:-1])
                instructions.append(instr)
            else:
                instructions.extend(block)

        for target_block, c_instr in jumps:
            c_instr.arg = self.get_block_index(target_block)

        return instructions

    def __eq__(self, other: Any) -> bool:
        if type(self) != type(other):
            return False

        if self.argnames != other.argnames:
            return False

        instrs1 = self._get_instructions()
        instrs2 = other._get_instructions()
        if instrs1 != instrs2:
            return False
        # FIXME: compare block.next_block

        return super().__eq__(other)

    def __len__(self) -> int:
        return len(self._blocks)

    def __iter__(self) -> Iterator[BasicBlock]:
        return iter(self._blocks)

    @overload
    def __getitem__(self, index: Union[int, BasicBlock]) -> BasicBlock:
        ...

    @overload
    def __getitem__(self: U, index: slice) -> U:
        ...

    def __getitem__(self, index):
        if isinstance(index, BasicBlock):
            index = self.get_block_index(index)
        return self._blocks[index]

    def __delitem__(self, index: Union[int, BasicBlock]) -> None:
        if isinstance(index, BasicBlock):
            index = self.get_block_index(index)
        block = self._blocks[index]
        del self._blocks[index]
        del self._block_index[id(block)]
        for index in range(index, len(self)):
            block = self._blocks[index]
            self._block_index[id(block)] -= 1

    def split_block(self, block: BasicBlock, index: int) -> BasicBlock:
        if not isinstance(block, BasicBlock):
            raise TypeError("expected block")
        block_index = self.get_block_index(block)

        if index < 0:
            raise ValueError("index must be positive")

        block = self._blocks[block_index]
        if index == 0:
            return block

        if index > len(block):
            raise ValueError("index out of the block")

        instructions = block[index:]
        if not instructions:
            if block_index + 1 < len(self):
                return self[block_index + 1]

        del block[index:]

        block2 = BasicBlock(instructions)
        block.next_block = block2

        for block in self[block_index + 1 :]:
            self._block_index[id(block)] += 1

        self._blocks.insert(block_index + 1, block2)
        self._block_index[id(block2)] = block_index + 1

        return block2

    @staticmethod
    def from_bytecode(bytecode: _bytecode.Bytecode) -> "ControlFlowGraph":
        # label => instruction index
        label_to_block_index = {}
        jumps = []
        try_end_locations = {}
        for index, instr in enumerate(bytecode):
            if isinstance(instr, Label):
                label_to_block_index[instr] = index
            elif isinstance(instr, Instr) and isinstance(instr.arg, Label):
                jumps.append((index, instr.arg))
            elif isinstance(instr, TryBegin):
                assert isinstance(instr.target, Label)
                jumps.append((index, instr.target))
            elif isinstance(instr, TryEnd):
                try_end_locations[instr.entry] = index

        # Figure out on which index block targeted by a label start
        block_starts = {}
        for target_index, target_label in jumps:
            target_index = label_to_block_index[target_label]
            block_starts[target_index] = target_label

        bytecode_blocks = ControlFlowGraph()
        bytecode_blocks._copy_attr_from(bytecode)
        bytecode_blocks.argnames = list(bytecode.argnames)

        # copy instructions, convert labels to block labels
        block = bytecode_blocks[0]
        labels = {}
        jumping_instrs: List[Instr] = []
        try_begins: Dict[TryBegin, TryBegin] = {}  # Map input TryBegin to CFG TryBegin
        add_try_end = {}

        # Track the currently active try begin
        active_try_begin: Optional[TryBegin] = None
        for index, instr in enumerate(bytecode):

            if index in block_starts:
                old_label = block_starts[index]
                # Create a new block if the last created one is not empty
                if index != 0 and block:
                    new_block = bytecode_blocks.add_block()
                    # If the last non artificial instruction is not final connect
                    # this block to the next.
                    li = block.get_last_non_artificial_instruction()
                    if li is not None and not li.is_final():
                        block.next_block = new_block
                    block = new_block
                if old_label is not None:
                    labels[old_label] = block

            elif block and (
                (last_instr := block.get_last_non_artificial_instruction()) is not None
            ):

                # The last instruction is final, if the current instruction is a
                # TryEnd insert it in the same block and move to the next instruction
                if last_instr.is_final():
                    b = block
                    block = bytecode_blocks.add_block()
                    # If the next instruction is a TryEnd ensures it remains
                    # part of the block (since TryEnd is artificial)
                    if isinstance(instr, TryEnd):
                        assert active_try_begin
                        nte = instr.copy()
                        nte.entry = try_begins[active_try_begin]
                        b.append(nte)
                        active_try_begin = None
                        continue

                elif last_instr.has_jump():
                    assert isinstance(last_instr.arg, Label)
                    new_block = bytecode_blocks.add_block()
                    block.next_block = new_block
                    block = new_block

                    # Check if the jump goes beyond the existing TryEnd
                    # and if it does add a TryEnd at the beginning of the target
                    # block to ensure that we always see a TryEnd while
                    # going through the CFG
                    if (
                        active_try_begin in try_end_locations
                        and (
                            label_to_block_index[last_instr.arg]
                            >= try_end_locations[active_try_begin]
                        )
                    ):
                        add_try_end[last_instr.arg] = TryEnd(try_begins[active_try_begin])

            if isinstance(instr, Label):
                continue

            # don't copy SetLineno objects
            if isinstance(instr, (Instr, TryBegin, TryEnd)):
                new = instr.copy()
                if isinstance(instr, TryBegin):
                    assert active_try_begin is None
                    active_try_begin = instr
                    assert isinstance(new, TryBegin)
                    try_begins[instr] = new
                elif isinstance(instr, TryEnd):
                    assert isinstance(new, TryEnd)
                    new.entry = try_begins[instr.entry]
                    active_try_begin = None
                elif isinstance(instr.arg, Label):
                    assert isinstance(new, Instr)
                    jumping_instrs.append(new)

                instr = new

            block.append(instr)

        # Insert TryEnd at the beginning of block that were marked
        for lab, te in add_try_end.items():
            labels[lab].insert(0, te)

        # Replace labels by block in jumping instructions
        for instr in jumping_instrs:
            label = instr.arg
            assert isinstance(label, Label)
            instr.arg = labels[label]

        # Replace labels by block in TryBegin
        for b_tb, c_tb in try_begins.items():
            label = b_tb.target
            assert isinstance(label, Label)
            c_tb.target = labels[label]

        return bytecode_blocks

    def to_bytecode(self) -> _bytecode.Bytecode:
        """Convert to Bytecode."""

        used_blocks = set()
        for block in self:
            target_block = block.get_jump()
            if target_block is not None:
                used_blocks.add(id(target_block))

            for tb in (i for i in block if isinstance(i, TryBegin)):
                used_blocks.add(id(tb.target))

        labels = {}
        jumps = []
        try_begins = {}
        seen_try_end: Set[TryBegin] = set()
        instructions: List[Union[Instr, Label, TryBegin, TryEnd, SetLineno]] = []

        for block in self:
            if id(block) in used_blocks:
                new_label = Label()
                labels[id(block)] = new_label
                instructions.append(new_label)

            for instr in block:
                # don't copy SetLineno objects
                if isinstance(instr, (Instr, TryBegin, TryEnd)):
                    new = instr.copy()
                    if isinstance(instr, TryBegin):
                        assert isinstance(new, TryBegin)
                        try_begins[instr] = new
                    elif isinstance(instr, TryEnd):
                        # Only keep the first seen TryEnd matching a TryBegin
                        assert isinstance(new, TryEnd)
                        if instr.entry in seen_try_end:
                            continue
                        seen_try_end.add(instr.entry)
                        new.entry = try_begins[instr.entry]
                    elif isinstance(instr.arg, BasicBlock):
                        assert isinstance(new, Instr)
                        jumps.append(new)

                    instr = new

                instructions.append(instr)

        # Map to new labels
        for instr in jumps:
            instr.arg = labels[id(instr.arg)]

        for tb in try_begins.values():
            tb.target = labels[id(tb.target)]

        bytecode = _bytecode.Bytecode()
        bytecode._copy_attr_from(self)
        bytecode.argnames = list(self.argnames)
        bytecode[:] = instructions

        return bytecode

    def to_code(
        self,
        stacksize: Optional[int] = None,
        *,
        check_pre_and_post: bool = True,
        compute_exception_stack_depths: bool = True,
    ) -> types.CodeType:
        """Convert to code."""
        if stacksize is None:
            stacksize = self.compute_stacksize(
                check_pre_and_post=check_pre_and_post,
                compute_exception_stack_depths=compute_exception_stack_depths,
            )
        bc = self.to_bytecode()
        return bc.to_code(
            stacksize=stacksize,
            check_pre_and_post=False,
            compute_exception_stack_depths=False,
        )

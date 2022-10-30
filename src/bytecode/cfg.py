from dataclasses import dataclass
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
                    isinstance(self[i], Instr) for i in range(index, len(self))
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


def _update_size(pre_delta, post_delta, size, maxsize, minsize):
    size += pre_delta
    if size < 0:
        msg = "Failed to compute stacksize, got negative size"
        raise RuntimeError(msg)
    size += post_delta
    maxsize = max(maxsize, size)
    minsize = min(minsize, size)
    return size, maxsize, minsize


# We can never have nested TryBegin, so we can simply update the min stack size
# when we encounter one and use the number we have when we encounter the TryEnd


@dataclass
class _StackSizeComputationStorage:
    """Common storage shared by the computers involved in computing CFG stack usage."""

    #: Should we check that all stack operation are "safe" i.e. occurs while there
    #: is a sufficient number of items on the stack.
    check_pre_and_post: bool

    #: Id the blocks for which an analysis is under progress to avoid getting stuck
    #: in recursions.
    seen_blocks: Set[int]

    #: Sizes and exception handling status with which the analysis of the block
    #: has been performed. Used to avoid running multiple times equivalent analysis.
    blocks_startsizes: Dict[int, Set[Tuple[int, Optional[bool]]]]

    #: Track the encountered TryBegin pseudo-instruction to update their target
    #: depth at the end of the calculation.
    try_begins: List[TryBegin]

    #: Stacksize that should be used for exception blocks. This is the smallest size
    #: with which this block was reached which is the only size that can be safely
    #: restored.
    exception_block_startsize: Dict[int, int]

    #: Largest stack size used in an exception block. We record the size corresponding
    #: to the smallest start size for the block since the interpreter enforces that
    #: we start with this size.
    exception_block_maxsize: Dict[int, int]


class _StackSizeComputer:
    """Helper computing the stack usage for a single block."""

    #: Common storage shared by all helpers involved in the stack size computation
    common: _StackSizeComputationStorage

    #: Block this helper is running the computation for.
    block: BasicBlock

    #: Current stack usage.
    size: int

    #: Maximal stack usage.
    maxsize: int

    #: Minimal stack usage. This value is only relevant in between a TryBegin/TryEnd
    #: pair and determine the startsize for the exception handling block associated
    #: with the try begin.
    minsize: int

    #: Flag indicating if the block analyzed is an exception handler (i.e. a target
    #: of a TryBegin).
    exception_handler: Optional[bool]

    #: TryBegin that was encountered before jumping to this block and for which
    #: no try end was met yet.
    pending_try_begin: Optional[TryBegin]

    def __init__(
        self,
        common: _StackSizeComputationStorage,
        block: BasicBlock,
        size: int,
        maxsize: int,
        minsize: int,
        exception_handler: Optional[bool],
        pending_try_begin: Optional[TryBegin],
    ) -> None:
        self.common = common
        self.block = block
        self.size = size
        self.maxsize = maxsize
        self.minsize = minsize
        self.exception_handler = exception_handler
        self.pending_try_begin = pending_try_begin
        self._current_try_begin = pending_try_begin

    def run(self):
        """Iterate over the block instructions to compute stack usage."""
        # Blocks are not hashable but in this particular context we know we won't be
        # modifying blocks in place so we can safely use their id as hash rather than
        # making them generally hashable which would be weird since they are list
        # subclasses
        block_id = id(self.block)

        # If the block is currently being visited (seen = True) or
        # it was visited previously by the same starting size and exception handler
        # status than the one in use, return the maxsize.
        fingerprint = (self.size, self.exception_handler)
        if id(self.block) in self.common.seen_blocks or (
            fingerprint in self.common.blocks_startsizes[block_id]
        ):
            yield self.maxsize

        # Prevent recursive visit of block if two blocks are nested (jump from one
        # to the other).
        self.common.seen_blocks.add(block_id)

        # Track which size has been used to run an analysis to avoid re-running multiple
        # times the same calculation.
        self.common.blocks_startsizes[block_id].add(fingerprint)

        # If this block is an exception handler reached through the exception table
        # we will push some extra objects on the stack before processing start.
        if self.exception_handler is not None:
            self._update_size(0, 1 + self.exception_handler)
            # True is used to indicated that push_lasti is True, leading to pushing
            # an extra object on the stack.

        for i, instr in enumerate(self.block):

            # Ignore SetLineno
            if isinstance(instr, (SetLineno)):
                continue

            # When we encounter a TryBegin, we:
            # - store it as the current TryBegin (TryBegin cannot be nested)
            # - record its existence to remember to update its stack size when
            # the computation ends
            # - update the minsize to the current size value since we need to
            # know the minimal stack usage between the TryBegin/TryEnd pair to
            # set the startsize of the exception handling block
            # This approach does not require any special handling for with statements.
            if isinstance(instr, TryBegin):
                self._current_try_begin = instr
                self.common.try_begins.append(instr)
                self.minsize = self.size

                continue

            elif isinstance(instr, TryEnd):
                # When we encounter a TryEnd we can start the computation for the
                # exception block using the minimum stack size encountered since
                # the TryBegin matching this TryEnd.

                # TryBegin cannot be nested so a TryEnd should always match the
                # current try begin. However inside the CFG some blocks may
                # start with a TryEnd relevant only when reaching this block
                # through a particular jump. So we are lenient here.
                if instr.entry is not self._current_try_begin:
                    continue

                b_id = id(instr.entry.target)
                if self.minsize < self.common.exception_block_startsize[b_id]:
                    self.common.exception_block_startsize[b_id] = self.minsize
                    block_size = yield _StackSizeComputer(
                        self.common,
                        instr.entry.target,
                        self.minsize,
                        self.maxsize,
                        self.minsize,
                        instr.entry.push_lasti,
                        None,
                    )
                    self.common.exception_block_maxsize[b_id] = block_size
                continue

            # For instructions with a jump first compute the stacksize required when the
            # jump is taken.
            if instr.has_jump():
                effect = (
                    instr.pre_and_post_stack_effect(jump=True)
                    if self.common.check_pre_and_post
                    else (instr.stack_effect(jump=True), 0)
                )
                taken_size, maxsize, minsize = _update_size(
                    *effect, self.size, self.maxsize, self.minsize
                )

                # Yield the parameters required to compute the stacksize required
                # by the block to which the jumnp points to and resume when we now
                # the maxsize.
                maxsize = yield _StackSizeComputer(
                    self.common,
                    instr.arg,
                    taken_size,
                    maxsize,
                    minsize,
                    None,
                    self._current_try_begin,
                )

                # For unconditional jumps abort early since the other instruction will
                # never be seen.
                if instr.is_uncond_jump():
                    # Check for TryEnd after the final instruction which is possible
                    # TryEnd being only pseudo instructions
                    if te := self._get_trailing_try_end(i):
                        # TryBegin cannot be nested
                        assert te.entry is self._current_try_begin

                        b_id = id(te.entry.target)
                        if self.minsize < self.common.exception_block_startsize[b_id]:
                            self.common.exception_block_startsize[b_id] = self.minsize
                            block_size = yield _StackSizeComputer(
                                self.common,
                                te.entry.target,
                                self.minsize,
                                self.maxsize,
                                self.minsize,
                                te.entry.push_lasti,
                                None,
                            )
                            self.common.exception_block_maxsize[b_id] = block_size

                    self.common.seen_blocks.remove(id(self.block))
                    yield maxsize

            # jump=False: non-taken path of jumps, or any non-jump
            effect = (
                instr.pre_and_post_stack_effect(jump=False)
                if self.common.check_pre_and_post
                else (instr.stack_effect(jump=False), 0)
            )
            self._update_size(*effect)

            # Instruction is final (return, raise, ...) so any following instruction
            # in the block is dead code.
            if instr.is_final():
                self.common.seen_blocks.remove(id(self.block))
                # Check for TryEnd after the final instruction which is possible
                # TryEnd being only pseudo instructions.
                if (
                    te := self._get_trailing_try_end(i)
                ):

                    b_id = id(te.entry.target)
                    if self.minsize < self.common.exception_block_startsize[b_id]:
                        self.common.exception_block_startsize[b_id] = self.minsize
                        block_size = yield _StackSizeComputer(
                            self.common,
                            te.entry.target,
                            self.minsize,
                            self.maxsize,
                            self.minsize,
                            te.entry.push_lasti,
                            None,
                        )
                        self.common.exception_block_maxsize[b_id] = block_size

                yield self.maxsize

        if self.block.next_block:
            self.maxsize = yield _StackSizeComputer(
                self.common,
                self.block.next_block,
                self.size,
                self.maxsize,
                self.minsize,
                None,
                self._current_try_begin,
            )

        self.common.seen_blocks.remove(id(self.block))

        yield self.maxsize

    # --- Private API

    _current_try_begin: Optional[TryBegin]

    def _update_size(self, pre_delta: int, post_delta: int) -> None:
        size, maxsize, minsize = _update_size(
            pre_delta, post_delta, self.size, self.maxsize, self.minsize
        )
        self.size = size
        self.minsize = minsize
        self.maxsize = maxsize

    def _get_trailing_try_end(self, index: int):
        while index + 1 < len(self.block):
            if isinstance(b := self.block[index + 1], TryEnd):
                return b
            index += 1

        return None


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

        # Create the common storage for the calculation
        common = _StackSizeComputationStorage(
            check_pre_and_post,
            seen_blocks=set(),
            blocks_startsizes={id(b): set() for b in self},
            exception_block_startsize=dict.fromkeys([id(b) for b in self], 32768),
            exception_block_maxsize=dict.fromkeys([id(b) for b in self], -32768),
            try_begins=[],
        )

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
        coro = _StackSizeComputer(
            common, self[0], initial_stack_size, 0, 0, None, None
        ).run()

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
                coro = args.run()

        except IndexError:
            # The exception occurs when all the generators have been exhausted
            # in which case the last yielded value is the stacksize.
            assert args is not None

            # Exception handling block size is reported separately since we need
            # to report only the stack usage for the smallest start size for the
            # block
            args = max(args, *common.exception_block_maxsize.values())

            # If requested update the TryBegin stack size
            if compute_exception_stack_depths:
                for tb in common.try_begins:
                    size = common.exception_block_startsize[id(tb.target)]
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
                    if active_try_begin in try_end_locations and (
                        label_to_block_index[last_instr.arg]
                        >= try_end_locations[active_try_begin]
                    ):
                        add_try_end[last_instr.arg] = TryEnd(
                            try_begins[active_try_begin]
                        )

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

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
from bytecode.instr import Instr, Label, SetLineno

T = TypeVar("T", bound="BasicBlock")
U = TypeVar("U", bound="ControlFlowGraph")


class BasicBlock(_bytecode._InstrList[Union[Instr, SetLineno]]):
    def __init__(self, instructions: Iterable[Union[Instr, SetLineno]] = None) -> None:
        # a BasicBlock object, or None
        self.next_block: Optional["BasicBlock"] = None
        if instructions:
            super().__init__(instructions)

    def __iter__(self) -> Iterator[Union[Instr, SetLineno]]:
        index = 0
        while index < len(self):
            instr = self[index]
            index += 1

            if not isinstance(instr, (SetLineno, Instr)):
                raise ValueError(
                    "BasicBlock must only contain SetLineno and Instr objects, "
                    "but %s was found" % instr.__class__.__name__
                )

            if isinstance(instr, Instr) and instr.has_jump():
                if index < len(self):
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
    def __getitem__(self, index: SupportsIndex) -> Union[Instr, SetLineno]:
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
            if set_lineno is not None:
                instr.lineno = set_lineno
            elif instr.lineno is None:
                instr.lineno = current_lineno
            else:
                current_lineno = instr.lineno

        for i in reversed(lineno_pos):
            del self[i]

        return current_lineno

    def get_jump(self) -> Optional["BasicBlock"]:
        if not self:
            return None

        last_instr = self[-1]
        if not (isinstance(last_instr, Instr) and last_instr.has_jump()):
            return None

        target_block = last_instr.arg
        assert isinstance(target_block, BasicBlock)
        return target_block


def _compute_stack_size(
    seen_blocks: Set[int],
    blocks_startsize: Dict[int, int],
    block: BasicBlock,
    size: int,
    maxsize: int,
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
    # If the block is currently being visited (seen = True) or if it was visited
    # previously by using a larger starting size than the one in use, return the
    # maxsize.
    if id(block) in seen_blocks or blocks_startsize[id(block)] >= size:
        yield maxsize

    def update_size(pre_delta, post_delta, size, maxsize):
        size += pre_delta
        if size < 0:
            msg = "Failed to compute stacksize, got negative size"
            raise RuntimeError(msg)
        size += post_delta
        maxsize = max(maxsize, size)
        return size, maxsize

    # Prevent recursive visit of block if two blocks are nested (jump from one
    # to the other).
    # Blocks are not hashable but in this particular instance we know we won't be
    # modifying blocks in place so we can safely use their id as hash rather than
    # making them generally hashable which would be weird since they are list
    # subclasses
    seen_blocks.add(id(block))
    blocks_startsize[id(block)] = size

    for instr in block:

        # Ignore SetLineno
        if isinstance(instr, SetLineno):
            continue

        # For instructions with a jump first compute the stacksize required when the
        # jump is taken.
        if instr.has_jump():
            effect = (
                instr.pre_and_post_stack_effect(jump=True)
                if check_pre_and_post
                else (instr.stack_effect(jump=True), 0)
            )
            taken_size, maxsize = update_size(*effect, size, maxsize)
            # Yield the parameters required to compute the stacksize required
            # by the block to which the jumnp points to and resume when we now
            # the maxsize.
            maxsize = (
                yield seen_blocks,
                blocks_startsize,
                instr.arg,
                taken_size,
                maxsize,
            )

            # For unconditional jumps abort early since the other instruction will
            # never be seen.
            if instr.is_uncond_jump():
                seen_blocks.remove(id(block))
                yield maxsize

        # jump=False: non-taken path of jumps, or any non-jump
        effect = (
            instr.pre_and_post_stack_effect(jump=False)
            if check_pre_and_post
            else (instr.stack_effect(jump=False), 0)
        )
        size, maxsize = update_size(*effect, size, maxsize)

    if block.next_block:
        maxsize = yield seen_blocks, blocks_startsize, block.next_block, size, maxsize

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

    def compute_stacksize(self, *, check_pre_and_post: bool = True) -> int:
        """Compute the stack size by iterating through the blocks

        The implementation make use of a generator function to avoid issue with
        deeply nested recursions.

        """
        # In the absence of any block return 0
        if not self:
            return 0

        # Ensure that previous calculation do not impact this one.
        seen_blocks: Set[int] = set()
        blocks_startsize = dict.fromkeys([id(b) for b in self], -32768)

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
            blocks_startsize,
            self[0],
            initial_stack_size,
            0,
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
            # in which case teh last yielded value is the stacksize.
            assert args is not None
            return args

    def __repr__(self) -> str:
        return "<ControlFlowGraph block#=%s>" % len(self._blocks)

    # Helper to obtain a flat list of instr, which does not refer to block at
    # anymore.
    def _get_instructions(self) -> List[Union[Instr, ConcreteInstr, SetLineno]]:
        instructions: List[Union[Instr, ConcreteInstr, SetLineno]] = []
        jumps: List[Tuple[BasicBlock, ConcreteInstr]] = []

        for block in self:
            target_block = block.get_jump()
            if target_block is not None:
                instr = block[-1]
                assert isinstance(instr, Instr)
                # We use a conrete instr here to be able to use an interger as argument
                # rather than a Label. This is fine for comparison purposes which is
                # our sole goal here.
                jumps.append(
                    (target_block, ConcreteInstr(instr.name, 0, lineno=instr.lineno))
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
        block_starts = {}
        for index, instr in enumerate(bytecode):
            if isinstance(instr, Label):
                label_to_block_index[instr] = index
            else:
                if isinstance(instr, Instr) and isinstance(instr.arg, Label):
                    jumps.append((index, instr.arg))

        for target_index, target_label in jumps:
            target_index = label_to_block_index[target_label]
            block_starts[target_index] = target_label

        bytecode_blocks = ControlFlowGraph()
        bytecode_blocks._copy_attr_from(bytecode)
        bytecode_blocks.argnames = list(bytecode.argnames)

        # copy instructions, convert labels to block labels
        block = bytecode_blocks[0]
        labels = {}
        jumping_instrs = []
        for index, instr in enumerate(bytecode):
            if index in block_starts:
                old_label = block_starts[index]
                if index != 0:
                    new_block = bytecode_blocks.add_block()
                    assert isinstance(block[-1], Instr)
                    if not block[-1].is_final():
                        block.next_block = new_block
                    block = new_block
                if old_label is not None:
                    labels[old_label] = block
            elif block and isinstance(last_instr := block[-1], Instr):
                if last_instr.is_final():
                    block = bytecode_blocks.add_block()
                elif last_instr.has_jump():
                    new_block = bytecode_blocks.add_block()
                    block.next_block = new_block
                    block = new_block

            if isinstance(instr, Label):
                continue

            # don't copy SetLineno objects
            if isinstance(instr, Instr):
                instr = instr.copy()
                if isinstance(instr.arg, Label):
                    jumping_instrs.append(instr)
            block.append(instr)

        for instr in jumping_instrs:
            label = instr.arg
            assert isinstance(label, Label)
            instr.arg = labels[label]

        return bytecode_blocks

    def to_bytecode(self) -> _bytecode.Bytecode:
        """Convert to Bytecode."""

        used_blocks = set()
        for block in self:
            target_block = block.get_jump()
            if target_block is not None:
                used_blocks.add(id(target_block))

        labels = {}
        jumps = []
        instructions: List[Union[Instr, Label, SetLineno]] = []

        for block in self:
            if id(block) in used_blocks:
                new_label = Label()
                labels[id(block)] = new_label
                instructions.append(new_label)

            for instr in block:
                # don't copy SetLineno objects
                if isinstance(instr, Instr):
                    instr = instr.copy()
                    if isinstance(instr.arg, BasicBlock):
                        jumps.append(instr)
                instructions.append(instr)

        # Map to new labels
        for instr in jumps:
            instr.arg = labels[id(instr.arg)]

        bytecode = _bytecode.Bytecode()
        bytecode._copy_attr_from(self)
        bytecode.argnames = list(self.argnames)
        bytecode[:] = instructions

        return bytecode

    def to_code(self, stacksize=None) -> types.CodeType:
        """Convert to code."""
        if stacksize is None:
            stacksize = self.compute_stacksize()
        bc = self.to_bytecode()
        return bc.to_code(stacksize=stacksize)

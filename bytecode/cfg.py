# alias to keep the 'bytecode' variable free
import bytecode as _bytecode
from bytecode.concrete import ConcreteInstr
from bytecode.instr import Label, SetLineno, Instr


class BasicBlock(_bytecode._InstrList):

    def __init__(self, instructions=None):
        # a BasicBlock object, or None
        self.next_block = None
        if instructions:
            super().__init__(instructions)

    def __iter__(self):
        index = 0
        while index < len(self):
            instr = self[index]
            index += 1

            if not isinstance(instr, (SetLineno, Instr, ConcreteInstr)):
                raise ValueError("BasicBlock must only contain SetLineno, "
                                 "Instr and ConcreteInstr objects, "
                                 "but %s was found"
                                 % instr.__class__.__name__)

            if isinstance(instr, Instr) and instr.has_jump():
                if index < len(self):
                    raise ValueError("Only the last instruction of a basic "
                                     "block can be a jump")

                if not isinstance(instr.arg, BasicBlock):
                    raise ValueError("Jump target must a BasicBlock, got %s",
                                     type(instr.arg).__name__)

            yield instr

    def get_jump(self):
        if not self:
            return None

        last_instr = self[-1]
        if not(isinstance(last_instr, Instr) and last_instr.has_jump()):
            return None

        target_block = last_instr.arg
        assert isinstance(target_block, BasicBlock)
        return target_block


def _compute_stack_size(block, size, maxsize):

    if block.seen or block.startsize >= size:
        return maxsize

    block.seen = True
    block.startsize = size

    for instr in block:

        if isinstance(instr, SetLineno):
            continue

        size += instr.stack_effect
        maxsize = max(maxsize, size)

        if size < 0:
            msg = 'Failed to compute stacksize, got negative size'
            raise RuntimeError(msg)

        if instr.has_jump():
            target_size = size

            if instr.name == 'FOR_ITER':
                target_size = size - 2

            elif instr.name in {'SETUP_FINALLY', 'SETUP_EXCEPT'}:
                target_size = size + 3
                maxsize = max(target_size, maxsize)

            elif instr.name.startswith('JUMP_IF'):
                size -= 1

            maxsize = _compute_stack_size(instr.arg, target_size, maxsize)

            if instr.is_uncond_jump():
                block.seen = False
                return maxsize

    if block.next_block:
        maxsize = _compute_stack_size(block.next_block, size, maxsize)

    block.seen = 0
    return maxsize


class ControlFlowGraph(_bytecode.BaseBytecode):

    def __init__(self):
        super().__init__()
        self._blocks = []
        self._block_index = {}
        self.argnames = []

        self.add_block()

    def get_block_index(self, block):
        try:
            return self._block_index[id(block)]
        except KeyError:
            raise ValueError("the block is not part of this bytecode")

    def _add_block(self, block):
        block_index = len(self._blocks)
        self._blocks.append(block)
        self._block_index[id(block)] = block_index

    def add_block(self, instructions=None):
        block = BasicBlock(instructions)
        self._add_block(block)
        return block

    def compute_stacksize(self):
        if not self:
            return 0

        for block in self:
            block.seen = False
            block.startsize = -32768  # INT_MIN

        return _compute_stack_size(self[0], 0, 0)

    def __repr__(self):
        return '<ControlFlowGraph block#=%s>' % len(self._blocks)

    def get_instructions(self):
        instructions = []
        jumps = []

        for block in self:
            target_block = block.get_jump()
            if target_block is not None:
                instr = block[-1]
                instr = ConcreteInstr(instr.name, 0, lineno=instr.lineno)
                jumps.append((target_block, instr))

                instructions.extend(block[:-1])
                instructions.append(instr)
            else:
                instructions.extend(block)

        for target_block, instr in jumps:
            instr.arg = self.get_block_index(target_block)

        return instructions

    def __eq__(self, other):
        if type(self) != type(other):
            return False

        if self.argnames != other.argnames:
            return False

        instrs1 = self.get_instructions()
        instrs2 = other.get_instructions()
        if instrs1 != instrs2:
            return False
        # FIXME: compare block.next_block

        return super().__eq__(other)

    def __len__(self):
        return len(self._blocks)

    def __iter__(self):
        return iter(self._blocks)

    def __getitem__(self, index):
        if isinstance(index, BasicBlock):
            index = self.get_block_index(index)
        return self._blocks[index]

    def __delitem__(self, index):
        if isinstance(index, BasicBlock):
            index = self.get_block_index(index)
        block = self._blocks[index]
        del self._blocks[index]
        del self._block_index[id(block)]
        for index in range(index, len(self)):
            block = self._blocks[index]
            self._block_index[id(block)] -= 1

    def split_block(self, block, index):
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

        for block in self[block_index + 1:]:
            self._block_index[id(block)] += 1

        self._blocks.insert(block_index + 1, block2)
        self._block_index[id(block2)] = block_index + 1

        return block2

    @staticmethod
    def from_bytecode(bytecode):
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

        bytecode_blocks = _bytecode.ControlFlowGraph()
        bytecode_blocks._copy_attr_from(bytecode)
        bytecode_blocks.argnames = list(bytecode.argnames)

        # copy instructions, convert labels to block labels
        block = bytecode_blocks[0]
        labels = {}
        jumps = []
        for index, instr in enumerate(bytecode):
            if index in block_starts:
                old_label = block_starts[index]
                if index != 0:
                    new_block = bytecode_blocks.add_block()
                    if not block[-1].is_final():
                        block.next_block = new_block
                    block = new_block
                if old_label is not None:
                    labels[old_label] = block
            elif block and isinstance(block[-1], Instr):
                if block[-1].is_final():
                    block = bytecode_blocks.add_block()
                elif block[-1].has_jump():
                    new_block = bytecode_blocks.add_block()
                    block.next_block = new_block
                    block = new_block

            if isinstance(instr, Label):
                continue

            # don't copy SetLineno objects
            if isinstance(instr, (Instr, ConcreteInstr)):
                instr = instr.copy()
                if isinstance(instr.arg, Label):
                    jumps.append(instr)
            block.append(instr)

        for instr in jumps:
            label = instr.arg
            instr.arg = labels[label]

        return bytecode_blocks

    def to_bytecode(self):
        """Convert to Bytecode."""

        used_blocks = set()
        for block in self:
            target_block = block.get_jump()
            if target_block is not None:
                used_blocks.add(id(target_block))

        labels = {}
        jumps = []
        instructions = []

        for block in self:
            if id(block) in used_blocks:
                new_label = Label()
                labels[id(block)] = new_label
                instructions.append(new_label)

            for instr in block:
                # don't copy SetLineno objects
                if isinstance(instr, (Instr, ConcreteInstr)):
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

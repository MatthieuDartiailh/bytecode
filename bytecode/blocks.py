# alias to keep the 'bytecode' variable free
import bytecode as _bytecode
from bytecode.instr import Instr, Label


class Block(_bytecode._InstrList):
    def __init__(self, instructions=None):
        # a Block object, or None
        self.next_block = None
        if instructions:
            super().__init__(instructions)


class BytecodeBlocks(_bytecode.BaseBytecode):
    def __init__(self):
        super().__init__()
        self._blocks = []
        self._block_index = {}
        self.argnames = []

        self.add_block()

    def _add_block(self, block):
        block_index = len(self._blocks)
        self._blocks.append(block)
        self._block_index[id(block)] = block_index

    def add_block(self, instructions=None):
        block = Block(instructions)
        self._add_block(block)
        return block

    def __repr__(self):
        return '<BytecodeBlocks block#=%s>' % len(self._blocks)

    def _flat(self):
        instructions = []
        labels = {}
        jumps = []
        offset = 0

        for block_index, block in enumerate(self, 1):
            labels[id(block)] = offset

            for index, instr in enumerate(block):
                offset += 1
                if isinstance(instr, Instr) and isinstance(instr.arg, Block):
                    # copy the instruction to be able to modify
                    # its argument below
                    instr = instr.copy()
                    jumps.append(instr)
                instructions.append(instr)

        for instr in jumps:
            instr.arg = labels[id(instr.arg)]

        return instructions

    def __eq__(self, other):
        if type(self) != type(other):
            return False

        if self.argnames != other.argnames:
            return False

        instrs1 = self._flat()
        instrs2 = other._flat()
        if instrs1 != instrs2:
            return False
        # FIXME: compare block.next_block

        return super().__eq__(other)

    def __len__(self):
        return len(self._blocks)

    def __iter__(self):
        return iter(self._blocks)

    def __getitem__(self, index):
        if isinstance(index, Block):
            index = self._block_index[id(index)]
        return self._blocks[index]

    def __delitem__(self, index):
        if isinstance(index, Block):
            index = self._block_index[id(index)]
        block = self._blocks[index]
        del self._blocks[index]
        del self._block_index[id(block)]
        for index in range(index, len(self)):
            block = self._blocks[index]
            self._block_index[id(block)] -= 1

    def split_block(self, block, index):
        if not isinstance(block, Block):
            raise TypeError("expected block")
        block_index = self._block_index[id(block)]

        if index < 0:
            raise ValueError("index must be positive")

        block = self._blocks[block_index]
        if index == 0:
            return block

        instructions = block[index:]
        if not instructions:
            raise ValueError("cannot create a label at the end of a block")
        del block[index:]

        block2 = Block(instructions)
        block.next_block = block2

        for block in self[block_index+1:]:
            self._block_index[id(block)] += 1

        self._blocks.insert(block_index+1, block2)
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
                if isinstance(instr.arg, Label):
                    jumps.append((index, instr.arg))

        for target_index, target_label  in jumps:
            target_index = label_to_block_index[target_label]
            block_starts[target_index] = target_label

        bytecode_blocks = _bytecode.BytecodeBlocks()
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
            elif block and block[-1].is_final():
                block = bytecode_blocks.add_block()
            elif block and block[-1].is_cond_jump():
                new_block = bytecode_blocks.add_block()
                block.next_block = new_block
                block = new_block

            if not isinstance(instr, Label):
                # copy the instruction to be able to modify its argument below
                instr = instr.copy()
                if isinstance(instr.arg, Label):
                    jumps.append(instr)
                block.append(instr)

        for instr in jumps:
            label = instr.arg
            instr.arg = labels[label]

        return bytecode_blocks

    def to_code(self):
        return self.to_concrete_bytecode().to_code()

    def to_concrete_bytecode(self):
        return self.to_bytecode().to_concrete_bytecode()

    def to_bytecode(self):
        """Convert to Bytecode.

        Unused labels are removed.
        """

        used_blocks = set()
        for block in self:
            for instr in block:
                if isinstance(instr, Label):
                    raise ValueError("Label must not be used in blocks")
                if isinstance(instr, Instr) and isinstance(instr.arg, Block):
                    used_blocks.add(id(instr.arg))

        labels = {}
        jumps = []
        instructions = []

        for block in self:
            if id(block) in used_blocks:
                new_label = Label()
                labels[id(block)] = new_label
                instructions.append(new_label)

            for instr in block:
                instr = instr.copy()
                if isinstance(instr.arg, Block):
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

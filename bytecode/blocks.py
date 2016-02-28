# alias to keep the 'bytecode' variable free
import bytecode as _bytecode
from bytecode.instr import Instr, Label


class Block(_bytecode._InstrList):
    def __init__(self, instructions=None):
        # create a unique object as label
        self.label = Label()
        # a Block object, or None
        self.next_block = None
        if instructions:
            super().__init__(instructions)


class BytecodeBlocks(_bytecode.BaseBytecode):
    def __init__(self):
        super().__init__()
        self._blocks = []
        self._label_to_index = {}
        self.argnames = []

        self.add_block()

    def _add_block(self, block):
        block_index = len(self._blocks)
        self._blocks.append(block)
        self._label_to_index[block.label] = block_index

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
            labels[block.label] = offset

            for index, instr in enumerate(block):
                if isinstance(instr, Label):
                    labels[instr] = offset
                else:
                    offset += 1
                    if isinstance(instr.arg, Label):
                        # copy the instruction to be able to modify
                        # its argument below
                        instr = instr.copy()
                        jumps.append(instr)
                    instructions.append(instr)

        for instr in jumps:
            instr.arg = labels[instr.arg]

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

    def __getitem__(self, block_index):
        if isinstance(block_index, Label):
            block_index = self._label_to_index[block_index]
        return self._blocks[block_index]

    def __delitem__(self, block_index):
        if isinstance(block_index, Label):
            block_index = self._label_to_index[block_index]
        block = self._blocks[block_index]
        del self._blocks[block_index]
        del self._label_to_index[block.label]
        for block_index in range(block_index, len(self)):
            label = self[block_index].label
            self._label_to_index[label] -= 1

    def create_label(self, block_index, index):
        if isinstance(block_index, Label):
            block_index = self._label_to_index[block_index]
        elif block_index < 0:
            raise ValueError("block_index must be positive")

        if index < 0:
            raise ValueError("index must be positive")

        block = self._blocks[block_index]
        if index == 0:
            return block.label

        instructions = block[index:]
        if not instructions:
            raise ValueError("cannot create a label at the end of a block")
        del block[index:]

        block2 = Block(instructions)
        block.next_block = block2

        for block in self[block_index+1:]:
            self._label_to_index[block.label] += 1

        self._blocks.insert(block_index+1, block2)
        self._label_to_index[block2.label] = block_index + 1

        return block2.label

    @staticmethod
    def from_bytecode(bytecode):
        # label => instruction index
        label_to_index = {}
        jumps = []
        block_starts = {}
        for index, instr in enumerate(bytecode):
            if isinstance(instr, Label):
                label_to_index[instr] = index
            else:
                if isinstance(instr.arg, Label):
                    jumps.append((index, instr.arg))

        for target_index, target_label  in jumps:
            target_index = label_to_index[target_label]
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
                    if not block[-1]._is_final():
                        block.next_block = new_block
                    block = new_block
                if old_label is not None:
                    labels[old_label] = block.label
            elif block and block[-1]._is_final():
                block = bytecode_blocks.add_block()

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
        used_labels = set()
        for block in self:
            for instr in block:
                if (not isinstance(instr, Label)
                   and isinstance(instr.arg, Label)):
                    used_labels.add(instr.arg)

        labels = {}
        jumps = []
        instructions = []

        for block in self:
            if block.label in used_labels:
                new_label = Label()
                labels[block.label] = new_label
                instructions.append(new_label)

            for instr in block:
                if isinstance(instr, Label):
                    old_label = instr
                    if old_label in used_labels:
                        new_label = Label()
                        labels[old_label] = new_label
                        instructions.append(new_label)
                else:
                    instr = instr.copy()
                    if isinstance(instr.arg, Label):
                        jumps.append(instr)
                    instructions.append(instr)

        for instr in jumps:
            instr.arg = labels[instr.arg]

        bytecode = _bytecode.Bytecode()
        bytecode._copy_attr_from(self)
        bytecode.argnames = list(self.argnames)
        bytecode[:] = instructions
        return bytecode

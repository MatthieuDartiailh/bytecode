import dis
import opcode
import struct
import types

__version__ = '0.0'


class BaseInstr:
    def __init__(self, lineno, name, arg=None):
        assert isinstance(lineno, int)
        self._lineno = lineno
        assert isinstance(name, str)
        self._name = name
        self._arg = arg

    @property
    def lineno(self):
        return self._lineno

    @property
    def name(self):
        return self._name

    @property
    def arg(self):
        return self._arg

    @property
    def size(self):
        return 0

    def __repr__(self):
        if self.arg is not None:
            return '<%s arg=%s lineno=%s>' % (self.name, self.arg, self.lineno)
        else:
            return '<%s lineno=%s>' % (self.name, self.lineno)

    def __eq__(self, other):
        if not isinstance(other, BaseInstr):
            return False
        key1 = (self._lineno, self._name, self._arg)
        key2 = (other._lineno, other._name, other._arg)
        return key1 == key2



class Instr(BaseInstr):
    def __init__(self, lineno, name, arg=None):
        super().__init__(lineno, name, arg)
        if self.arg is not None:
            self._size = 3
        else:
            self._size = 1
        self._op = opcode.opmap[self.name]

    @property
    def op(self):
        return self._op

    @property
    def size(self):
        return self._size

    def replace(self, name, arg=None):
        return Instr(self.lineno, name, arg)

    def replace_arg(self, arg=None):
        return Instr(self.lineno, self.name, arg)

    def get_jump_target(self, instr_offset):
        if isinstance(self._arg, Label):
            raise ValueError("jump target is a label")
        if self._op in opcode.hasjrel:
            return instr_offset + self._size + self._arg
        if self._op in opcode.hasjabs:
            return self._arg
        return None

    def is_jump(self):
        return (self._op in opcode.hasjrel or self._op in opcode.hasjabs)

    def is_cond_jump(self):
        # Ex: POP_JUMP_IF_TRUE, JUMP_IF_FALSE_OR_POP
        return 'JUMP_IF_' in self.name

    def assemble(self):
        if self._arg is not None:
            return struct.pack('<BH', self._op, self._arg)
        else:
            return struct.pack('<B', self._op)

    @classmethod
    def disassemble(cls, lineno, code, offset):
        op = code[offset]
        if op >= opcode.HAVE_ARGUMENT:
            arg = code[offset + 1] + code[offset + 2] * 256
        else:
            arg = None
        name = opcode.opname[op]
        return cls(lineno, name, arg)


class Label:
    __slots__ = ()


class Block(list):
    def __init__(self, instructions=None):
        # create a unique object as label
        self.label = Label()
        if instructions:
            super().__init__(instructions)


class Code:
    def __init__(self, code_obj, blocks):
        # FIXME: store all code_obj to individual attributes
        self.code_obj = code_obj

        self._stacksize = code_obj.co_stacksize
        self._nlocals = code_obj.co_nlocals
        self._flags = code_obj.co_flags

        self.argcount = code_obj.co_argcount
        self.kw_only_argcount = code_obj.co_kwonlyargcount
        self.first_lineno = code_obj.co_firstlineno

        # FIXME: is there a link between names and varnames?
        self.names = code_obj.co_names
        self.varnames = code_obj.co_varnames

        self.filename = code_obj.co_filename
        self.name = code_obj.co_name
        self.freevars = code_obj.co_freevars
        self.cellvars = code_obj.co_cellvars

        self._blocks = blocks
        self._block_map = dict((block.label, block) for block in blocks)
        self.consts = list(self.code_obj.co_consts)

    def __repr__(self):
        return '<Code block#=%s>' % len(self._blocks)

    def __eq__(self, other):
        if not isinstance(other, Code):
            return False
        if len(self._blocks) != len(other._blocks):
            return False
        targets1 = {}
        for block_index, block in enumerate(self, 1):
            targets1[block.label] = 'label%s' % block_index
        targets2 = {}
        for block_index, block in enumerate(other, 1):
            targets2[block.label] = 'label%s' % block_index
        for block1, block2 in zip(self._blocks, other._blocks):
            if len(block1) != len(block2):
                return False
            for instr1, instr2 in zip(block1, block2):

                arg1 = instr1._arg
                arg1 = targets1.get(arg1, arg1)
                key1 = (instr1._lineno, instr1._name, arg1)

                arg2 = instr2._arg
                arg2 = targets2.get(arg2, arg2)
                key2 = (instr2._lineno, instr2._name, arg2)

                if key1 != key2:
                    return False
        if self.consts != other.consts:
            return False
        return True

    def __len__(self):
        return len(self._blocks)

    def __iter__(self):
        return iter(self._blocks)

    def __getitem__(self, index):
        if isinstance(index, Label):
            return self._block_map[index]
        else:
            return self._blocks[index]

    def create_label(self, block_index, index):
        if isinstance(block_index, Label):
            block = self._block_map[block_index]
            # FIXME: O(n) complexity where n is the number of blocks
            block_index = self._blocks.index(block)
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
        block2 = Block(instructions)

        self._blocks.insert(block_index+1, block2)
        self._block_map[block2.label] = block2
        del block[index:]

        return block2.label

    @classmethod
    def disassemble(cls, code_obj):
        code = code_obj.co_code
        line_starts = dict(dis.findlinestarts(code_obj))

        # find block starts
        instructions = []
        block_starts = set()

        offset = 0
        lineno = code_obj.co_firstlineno
        while offset < len(code):
            instr = Instr.disassemble(lineno, code, offset)

            key = offset # + instr.size
            if key in line_starts:
                lineno = line_starts[key]
                instr = Instr(lineno, instr.name, instr.arg)

            target = instr.get_jump_target(offset)
            if target is not None:
                block_starts.add(target)

            instructions.append(instr)

            offset += instr.size

        # split instructions in blocks
        blocks = []
        block_map = {}
        offset = 0

        block = Block()
        blocks.append(block)
        block_map[offset] = block
        for instr in instructions:
            if offset != 0 and offset in block_starts:
                block = Block()
                block_map[offset] = block
                blocks.append(block)
            block.append(instr)
            offset += instr.size
        assert len(block) != 0

        # replace jump targets with blocks
        offset = 0
        for block in blocks:
            for index, instr in enumerate(block):
                target = instr.get_jump_target(offset)
                if target is not None:
                    target_block = block_map[target]
                    block[index] = instr.replace_arg(target_block.label)
                offset += instr.size

        return cls(code_obj, blocks)

    def assemble(self):
        targets = {}
        linenos = []
        blocks = [(block.label, list(block)) for block in self]

        # find targets
        offset = 0
        for label, instructions in blocks:
            targets[label] = offset
            for instr in instructions:
                offset += instr.size

        # replace targets with offsets
        offset = 0
        code_str = []
        linenos = []
        for target, instructions in blocks:
            for instr in instructions:
                if isinstance(instr.arg, Label):
                    target_off = targets[instr.arg]
                    if instr.op in opcode.hasjrel:
                        target_off = target_off - (offset + instr.size)
                    instr = instr.replace_arg(target_off)

                code_str.append(instr.assemble())
                linenos.append((offset, instr.lineno))

                offset += instr.size

        lnotab = []
        old_offset = 0
        old_lineno = self.first_lineno
        for offset, lineno in  linenos:
            dlineno = lineno - old_lineno
            if dlineno == 0:
                continue
            old_lineno = lineno

            doff = offset - old_offset
            old_offset = offset

            while doff > 255:
                lnotab.append(b'\xff0')
                doff -= 255

            while dlineno < -127:
                lnotab.append(struct.pack('Bb', 0, -127))
                dlineno -= -127

            while dlineno > 126:
                lnotab.append(struct.pack('Bb', 0, 126))
                dlineno -= 126

            assert 0 <= doff <= 255
            assert -127 <= dlineno <= 126

            lnotab.append(struct.pack('Bb', doff, dlineno))

        code_str = b''.join(code_str)
        lnotab = b''.join(lnotab)

        return types.CodeType(self.argcount,
                              self.kw_only_argcount,
                              # FIXME: compute number of locals
                              self._nlocals,
                              # FIXME: compute stack size
                              self._stacksize,
                              self._flags,
                              code_str,
                              tuple(self.consts),
                              self.names,
                              self.varnames,
                              self.filename,
                              self.name,
                              self.first_lineno,
                              lnotab,
                              self.freevars,
                              self.cellvars)


def dump_code(code):
    labels = {}
    for block_index, block in enumerate(code, 1):
        labels[block.label] = "[Block #%s]" % block_index
    for block in code:
        print(labels[block.label])
        for instr in block:
            if isinstance(instr.arg, Label):
                instr = instr.replace_arg(labels[instr.arg])
            print("  %s" % instr)
        print()
    print()
    print()

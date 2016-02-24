import dis
import opcode
import struct
import types

__version__ = '0.0'


# Prepare code to support None value as Instr.arg for LOAD_CONST(None)
UNSET = None


class Instr:
    """
    Abstract instruction: argument can be any kind of object.
    """

    __slots__ = ('_lineno', '_name', '_arg', '_op', '_size')

    def __init__(self, lineno, name, arg=UNSET):
        if not isinstance(lineno, int):
            raise TypeError("lineno must be an int")
        if lineno < 1:
            raise ValueError("invalid lineno")
        if not isinstance(name, str):
            raise TypeError("name must be a str")
        try:
            op = opcode.opmap[name]
        except KeyError:
            raise ValueError("invalid operation name")

        has_arg = (arg is not UNSET)
        if op >= opcode.HAVE_ARGUMENT:
            if not has_arg:
                raise ValueError("%s requires an argument")
        else:
            if has_arg:
                raise ValueError("%s has no argument")

        size = 1
        if has_arg:
            size += 2
            if not isinstance(arg, Label) and arg > 0xffff:
                size += 3

        self._lineno = lineno
        self._name = name
        self._arg = arg
        self._op = op
        self._size = size

    # FIXME: stack effect

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
    def op(self):
        return self._op

    @property
    def size(self):
        return self._size

    def __repr__(self):
        if self._arg is not UNSET:
            return '<%s arg=%s lineno=%s>' % (self._name, self._arg, self._lineno)
        else:
            return '<%s lineno=%s>' % (self._name, self._lineno)

    def __eq__(self, other):
        if not isinstance(other, Instr):
            return False
        key1 = (self._lineno, self._name, self._arg)
        key2 = (other._lineno, other._name, other._arg)
        return key1 == key2

    def replace(self, name, arg=UNSET):
        return Instr(self._lineno, name, arg)

    def replace_arg(self, arg=UNSET):
        return Instr(self._lineno, self._name, arg)

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
        return ('JUMP_IF_' in self._name)


class ConcreteInstr(Instr):
    __slots__ = ()

    def __init__(self, lineno, name, arg=UNSET):
        if arg is not UNSET:
            if isinstance(arg, int):
                # FIXME: it looks like assemble_emit() allows negative argument
                # (minimum=-2147483648) and use a maximum of 2147483647
                if arg < 0:
                    raise ValueError("arg must be positive")
                if arg > 2147483647:
                    raise ValueError("arg must be in range 0..2147483647")
            elif not isinstance(arg, Label):
                raise TypeError("arg must be an int or a bytecode.Label")

        super().__init__(lineno, name, arg)

    def assemble(self):
        if self._arg is UNSET:
            return struct.pack('<B', self._op)

        arg = self._arg
        if isinstance(arg, Label):
            raise ValueError("arg is a label")
        if arg > 0xffff:
            return struct.pack('<BHBH',
                               opcode.EXTENDED_ARG, arg >> 16,
                               self._op, arg & 0xffff)
        else:
            return struct.pack('<BH', self._op, arg)

    @classmethod
    def disassemble(cls, lineno, code, offset):
        op = code[offset]
        if op >= opcode.HAVE_ARGUMENT:
            arg = code[offset + 1] + code[offset + 2] * 256
        else:
            arg = UNSET
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
    def __init__(self, name, filename, flags):
        self.argcount = 0
        self.kw_only_argcount = 0
        self._nlocals = 0
        self._stacksize = 0
        self.flags = flags
        self.first_lineno = 1
        self.names = []
        self.varnames = []
        self.filename = filename
        self.name = name
        self.freevars = []
        self.cellvars = []
        self.consts = []

        self._blocks = []
        self._label_to_index = {}

        self.add_block()

    def _add_block(self, block):
        block_index = len(self._blocks)
        self._blocks.append(block)
        self._label_to_index[block.label] = block_index

    def add_block(self):
        block = Block()
        self._add_block(block)
        return block

    def __repr__(self):
        return '<Code block#=%s>' % len(self._blocks)

    def __eq__(self, other):
        if not isinstance(other, Code):
            return False

        if self.argcount != other.argcount:
            return False
        if self.kw_only_argcount != other.kw_only_argcount:
            return False
        if self._nlocals != other._nlocals:
            return False
        if self._stacksize != other._stacksize:
            return False
        if self.flags != other.flags:
            return False
        if self.first_lineno != other.first_lineno:
            return False
        if self.names != other.names:
            return False
        if self.varnames != other.varnames:
            return False
        if self.filename != other.filename:
            return False
        if self.name != other.name:
            return False
        if self.freevars != other.freevars:
            return False
        if self.cellvars != other.cellvars:
            return False
        # FIXME: don't use == but a key function, 1 and 1.0 are not the same
        # constant, see _PyCode_ConstantKey() in Objects/codeobject.c
        if self.consts != other.consts:
            return False

        # Compare blocks (need to "renumber" labels)
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

        return True

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
        # Note: complexity of O(n) where n is the number of blocks
        del self._blocks[block_index]
        del self._label_to_index[block.label]

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

        for block in self[block_index+1:]:
            self._label_to_index[block.label] += 1

        self._blocks.insert(block_index+1, block2)
        self._label_to_index[block2.label] = block_index + 1

        return block2.label

    @classmethod
    def disassemble(cls, code_obj, *, use_labels=True, extended_arg_op=False):
        code = code_obj.co_code
        line_starts = dict(dis.findlinestarts(code_obj))

        # find block starts
        instructions = []
        block_starts = set()
        offset = 0
        lineno = code_obj.co_firstlineno
        while offset < len(code):
            if offset in line_starts:
                lineno = line_starts[offset]

            instr = ConcreteInstr.disassemble(lineno, code, offset)

            if use_labels:
                target = instr.get_jump_target(offset)
                if target is not None:
                    block_starts.add(target)

            instructions.append(instr)
            offset += instr.size

        # split instructions in blocks
        blocks = []
        label_to_block = {}
        offset = 0

        block = Block()
        blocks.append(block)
        label_to_block[offset] = block
        for instr in instructions:
            if offset != 0 and offset in block_starts:
                block = Block()
                label_to_block[offset] = block
                blocks.append(block)
            block.append(instr)
            offset += instr.size
        assert len(block) != 0

        # replace jump targets with blocks
        offset = 0
        for block in blocks:
            extended_arg = None
            index = 0
            while index < len(block):
                instr = block[index]

                if instr.name == 'EXTENDED_ARG' and not extended_arg_op:
                    if extended_arg is not None:
                        raise ValueError("EXTENDED_ARG followed "
                                         "by EXTENDED_ARG")
                    extended_arg = instr.arg
                    del block[index]
                    continue

                if use_labels:
                    target = instr.get_jump_target(offset)
                else:
                    target = None
                if target is not None:
                    target_block = label_to_block[target]
                    arg = target_block.label
                    if extended_arg is not None:
                        raise ValueError("EXTENDED_ARG before %s"
                                         % instr.name)
                else:
                    arg = instr.arg
                    if extended_arg is not None:
                        arg = (extended_arg << 16) + arg
                        extended_arg = None

                block[index] = Instr(instr.lineno, instr.name, arg)

                offset += instr.size
                index += 1

            if extended_arg is not None:
                raise ValueError("EXTENDED_ARG at the end of a block")

        code = cls(code_obj.co_name,
                   code_obj.co_filename,
                   code_obj.co_flags)
        code.argcount = code_obj.co_argcount
        code.kw_only_argcount = code_obj.co_kwonlyargcount
        code._nlocals = code_obj.co_nlocals
        code._stacksize = code_obj.co_stacksize
        code.first_lineno = code_obj.co_firstlineno
        code.names = list(code_obj.co_names)
        code.varnames = list(code_obj.co_varnames)
        code.freevars = list(code_obj.co_freevars)
        code.cellvars = list(code_obj.co_cellvars)
        code.consts = list(code_obj.co_consts)
        # delete the first empty block
        del code[0]
        for block in blocks:
            code._add_block(block)
        return code

    def assemble(self):
        targets = {}
        linenos = []
        blocks = [(block.label, list(block)) for block in self]

        # FIXME: validate code?

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
                arg = instr.arg
                if isinstance(arg, Label):
                    target_off = targets[arg]
                    if instr.op in opcode.hasjrel:
                        target_off = target_off - (offset + instr.size)
                    arg = target_off

                instr = ConcreteInstr(instr.lineno, instr.name, arg)
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
                              self.flags,
                              code_str,
                              tuple(self.consts),
                              tuple(self.names),
                              tuple(self.varnames),
                              self.filename,
                              self.name,
                              self.first_lineno,
                              lnotab,
                              tuple(self.freevars),
                              tuple(self.cellvars))


def _dump_code(code):
    offset = 0
    lineno = None
    line_width = 3
    for block_index, block in enumerate(code, 1):
        print("[Block #%s]" % block_index)
        for instr in block:
            fields = []
            if instr.lineno != lineno:
                fields.append(str(instr.lineno).rjust(line_width))
                lineno = instr.lineno
            else:
                fields.append(" " * line_width)

            fields.append("% 3s    %s" % (offset, instr.name))
            arg = instr.arg
            if arg is not UNSET:
                if isinstance(arg, Label):
                    arg = '<block #%s>' % code._label_to_index[arg]
                fields.append("(%s)" % arg)
            print(''.join(fields))

            offset += instr.size
        print()

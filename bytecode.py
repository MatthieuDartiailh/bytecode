import abc
import dis
import opcode
import struct
import types

__version__ = '0.0'


UNSET = object()


def _const_key(obj):
    # FIXME: don't use == but a key function, 1 and 1.0 are not the same
    # constant, see _PyCode_ConstantKey() in Objects/codeobject.c
    return (type(obj), obj)


class BaseInstr:
    __slots__ = ('_lineno', '_name', '_arg', '_op')

    def __init__(self, lineno, name, arg=UNSET):
        self._set_lineno(lineno)
        self._set_name(name)
        self._arg = arg

    # FIXME: stack effect

    def _set_lineno(self, lineno):
        if not isinstance(lineno, int):
            raise TypeError("lineno must be an int")
        if lineno < 1:
            raise ValueError("invalid lineno")
        self._lineno = lineno

    def _set_name(self, name):
        if not isinstance(name, str):
            raise TypeError("name must be a str")
        try:
            op = opcode.opmap[name]
        except KeyError:
            raise ValueError("invalid operation name")
        self._name = name
        self._op = op

    @property
    def op(self):
        return self._op

    @op.setter
    def op(self, op):
        if not isinstance(op, int):
            raise TypeError("operator must be an int")
        if 0 <= op <= 255:
            name = opcode.opname[op]
            valid = (name != '<%r>' % op)
        else:
            valid = False
        if not valid:
            raise ValueError("invalid operator")

        self._name = name
        self._op = op

    def format(self, labels):
        text = self.name
        arg = self._arg
        if arg is not UNSET:
            if isinstance(arg, Label):
                arg = '<%s>' % labels[arg]
            else:
                arg = repr(arg)
            text = '%s %s' % (text, arg)
        return text

    def __repr__(self):
        if self._arg is not UNSET:
            return '<%s arg=%r lineno=%s>' % (self._name, self._arg, self._lineno)
        else:
            return '<%s lineno=%s>' % (self._name, self._lineno)

    def _cmp_key(self, labels=None):
        arg = self._arg
        if self._op in opcode.hasconst:
            arg = _const_key(arg)
        elif isinstance(arg, Label) and labels is not None:
            arg = labels[arg]
        return (self._lineno, self._name, arg)

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        return self._cmp_key() == other._cmp_key()

    def is_jump(self):
        return (self._op in opcode.hasjrel or self._op in opcode.hasjabs)

    def is_cond_jump(self):
        # Ex: POP_JUMP_IF_TRUE, JUMP_IF_FALSE_OR_POP
        return ('JUMP_IF_' in self._name)


class Instr(BaseInstr):
    """Abstract instruction.

    lineno, name, op and arg attributes can be modified.

    arg is not checked.
    """

    __slots__ = ()

    @property
    def lineno(self):
        return self._lineno

    @lineno.setter
    def lineno(self, lineno):
        self._set_lineno(lineno)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._set_name(name)

    @property
    def arg(self):
        return self._arg

    @arg.setter
    def arg(self, arg):
        self._arg = arg


class ConcreteInstr(BaseInstr):
    __slots__ = ('_size',)

    def __init__(self, lineno, name, arg=UNSET):
        super().__init__(lineno, name, arg)

        if self._op >= opcode.HAVE_ARGUMENT:
            if arg is UNSET:
                raise ValueError("%s opcode requires an argument" % name)

            if isinstance(arg, int):
                # FIXME: it looks like assemble_emit() allows negative argument
                # (minimum=-2147483648) and use a maximum of 2147483647
                if arg < 0:
                    raise ValueError("arg must be positive")
                if arg > 2147483647:
                    raise ValueError("arg must be in range 0..2147483647")
            else:
                raise TypeError("arg must be an int")
        else:
            if arg is not UNSET:
                raise ValueError("%s opcode has no argument" % name)

        size = 1
        if arg is not UNSET:
            size += 2
            if arg > 0xffff:
                size += 3

        self._size = size

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
        return self._size

    def get_jump_target(self, instr_offset):
        if self._op in opcode.hasjrel:
            return instr_offset + self._size + self._arg
        if self._op in opcode.hasjabs:
            return self._arg
        return None

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


class BaseBytecode(metaclass=abc.ABCMeta):
    def __init__(self):
        self.argcount = 0
        self.kw_only_argcount = 0
        self._stacksize = 0
        self.flags = 0
        self.first_lineno = 1
        self.name = '<module>'
        self.filename = '<string>'
        self.docstring = UNSET

        # FIXME: move to ConcreteBytecode
        self.freevars = []
        self.cellvars = []

    def __eq__(self, other):
        if type(self) != type(other):
            return False

        if self.argcount != other.argcount:
            return False
        if self.kw_only_argcount != other.kw_only_argcount:
            return False
        if self._stacksize != other._stacksize:
            return False
        if self.flags != other.flags:
            return False
        if self.first_lineno != other.first_lineno:
            return False
        if self.filename != other.filename:
            return False
        if self.name != other.name:
            return False
        if self.docstring != other.docstring:
            return False
        if self.freevars != other.freevars:
            return False
        if self.cellvars != other.cellvars:
            return False

        return True


class ConcreteBytecode(BaseBytecode, list):
    def __init__(self):
        super().__init__()
        self.consts = []
        self.names = []
        self.varnames = []

    def __repr__(self):
        return '<ConcreteBytecode instr#=%s const#=%s>' % len(self)

    def __eq__(self, other):
        if type(self) != type(other):
            return False

        const_keys1 = list(map(_const_key, self.consts))
        const_keys2 = list(map(_const_key, other.consts))
        if const_keys1 != const_keys2:
            return False

        if self.names != other.names:
            return False
        if self.varnames != other.varnames:
            return False

        return super().__eq__(other)

    @staticmethod
    def from_code(code, *, extended_arg_op=False):
        line_starts = dict(dis.findlinestarts(code))

        # find block starts
        instructions = []
        offset = 0
        lineno = code.co_firstlineno
        while offset < len(code.co_code):
            if offset in line_starts:
                lineno = line_starts[offset]

            instr = ConcreteInstr.disassemble(lineno, code.co_code, offset)

            instructions.append(instr)
            offset += instr.size

        # replace jump targets with blocks
        if not extended_arg_op:
            extended_arg = None
            index = 0
            while index < len(instructions):
                instr = instructions[index]

                if instr.name == 'EXTENDED_ARG' and not extended_arg_op:
                    if extended_arg is not None:
                        raise ValueError("EXTENDED_ARG followed "
                                         "by EXTENDED_ARG")
                    extended_arg = instr.arg
                    del instructions[index]
                    continue

                if extended_arg is not None:
                    arg = (extended_arg << 16) + instr.arg
                    extended_arg = None

                    instr = ConcreteInstr(instr.lineno, instr.name, arg)
                    instructions[index] = instr

                index += 1

            if extended_arg is not None:
                raise ValueError("EXTENDED_ARG at the end of the code")

        bytecode = ConcreteBytecode()
        bytecode.name = code.co_name
        bytecode.filename = code.co_filename
        bytecode.flags = code.co_flags
        bytecode.argcount = code.co_argcount
        bytecode.kw_only_argcount = code.co_kwonlyargcount
        bytecode._stacksize = code.co_stacksize
        bytecode.first_lineno = code.co_firstlineno
        bytecode.names = list(code.co_names)
        bytecode.consts = list(code.co_consts)
        bytecode.varnames = list(code.co_varnames)
        bytecode.freevars = list(code.co_freevars)
        bytecode.cellvars = list(code.co_cellvars)

        first_const = code.co_consts[0]
        if isinstance(first_const, str):
            bytecode.docstring = first_const
        elif first_const is None:
            bytecode.docstring = first_const

        bytecode[:] = instructions
        return bytecode

    def _assemble_code(self):
        offset = 0
        code_str = []
        linenos = []
        for instr in self:
            code_str.append(instr.assemble())
            linenos.append((offset, instr.lineno))
            offset += instr.size
        code_str = b''.join(code_str)
        return (code_str, linenos)

    @staticmethod
    def _assemble_lnotab(first_lineno, linenos):
        lnotab = []
        old_offset = 0
        old_lineno = first_lineno
        for offset, lineno in linenos:
            dlineno = lineno - old_lineno
            if dlineno == 0:
                continue
            old_lineno = lineno

            doff = offset - old_offset
            old_offset = offset

            while doff > 255:
                lnotab.append(b'\xff\x00')
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

        return b''.join(lnotab)

    def to_code(self):
        code_str, linenos = self._assemble_code()
        lnotab = self._assemble_lnotab(self.first_lineno, linenos)
        nlocals = len(self.varnames) - self.argcount - self.kw_only_argcount
        return types.CodeType(self.argcount,
                              self.kw_only_argcount,
                              nlocals,
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

    def to_concrete_bytecode(self):
        return self

    def to_bytecode(self):
        # find jump targets
        jump_targets = set()
        offset = 0
        for instr in self:
            target = instr.get_jump_target(offset)
            if target is not None:
                jump_targets.add(target)
            offset += instr.size

        # create labels
        jumps = []
        instructions = []
        labels = {}
        offset = 0

        for instr in self:
            if offset in jump_targets:
                label = Label()
                labels[offset] = label
                instructions.append(label)

            jump_target = instr.get_jump_target(offset)
            size = instr.size

            arg = instr.arg
            # FIXME: better error reporting
            if instr.op in opcode.hasconst:
                arg = self.consts[arg]
            elif instr.op in opcode.haslocal:
                arg = self.varnames[arg]
            elif instr.op in opcode.hasname:
                arg = self.names[arg]
            # FIXME: hasfree

            instr = Instr(instr.lineno, instr.name, arg)
            instructions.append(instr)
            offset += size

            if jump_target is not None:
                jumps.append((instr, jump_target))

        # replace jump targets with blocks
        for instr, jump_target in jumps:
            # FIXME: better error reporting on missing label
            instr.arg = labels[jump_target]

        bytecode = Bytecode()
        bytecode.name = self.name
        bytecode.filename = self.filename
        bytecode.flags = self.flags
        bytecode.argcount = self.argcount
        bytecode.kw_only_argcount = self.kw_only_argcount
        bytecode._stacksize = self._stacksize
        bytecode.first_lineno = self.first_lineno
        bytecode.freevars = list(self.freevars)
        bytecode.cellvars = list(self.cellvars)

        nargs = bytecode.argcount + bytecode.kw_only_argcount
        bytecode.argnames = self.varnames[:nargs]

        first_const = self.consts[0]
        if isinstance(first_const, str):
            bytecode.docstring = first_const
        elif first_const is None:
            bytecode.docstring = first_const

        bytecode.extend(instructions)
        return bytecode

    def to_bytecode_blocks(self):
        return self.to_bytecode().to_bytecode_blocks()


class Label:
    __slots__ = ()


class _InstrList(list):
    def _flat(self):
        instructions = []
        labels = {}
        jumps = []
        offset = 0

        for index, instr in enumerate(self):
            if isinstance(instr, Label):
                labels[instr] = offset
            else:
                offset += 1
                if isinstance(instr.arg, Label):
                    # copy the instruction to be able to modify
                    # its argument above
                    instr = Instr(instr.lineno, instr.name, instr.arg)
                    jumps.append(instr)
                instructions.append(instr)

        for instr in jumps:
            instr.arg = labels[instr.arg]

        return instructions

    def __eq__(self, other):
        if not isinstance(other, _InstrList):
            other = _InstrList(other)

        instrs1 = self._flat()
        instrs2 = self._flat()
        return (instrs1 == instrs2)


class Block(_InstrList):
    def __init__(self, instructions=None):
        # create a unique object as label
        self.label = Label()
        if instructions:
            super().__init__(instructions)


class _ConvertCodeToConcrete:
    def __init__(self, code):
        self.bytecode = code
        self.consts = []
        self.names = []
        self.varnames = []

    def add_const(self, value):
        key = _const_key(value)
        for index, const in enumerate(self.consts):
            if _const_key(const) == key:
                return index
        index = len(self.consts)
        self.consts.append(value)
        return index

    @staticmethod
    def add(names, name):
        try:
            index = names.index(name)
        except ValueError:
            index = len(names)
            names.append(name)
        return index

    def concrete_instructions(self):
        use_blocks = isinstance(self.bytecode, BytecodeBlocks)

        if use_blocks:
            blocks = self.bytecode
        else:
            blocks = (self.bytecode,)

        targets = {}
        jumps = []

        # convert abstract instructions to concrete instructions
        instructions = []
        offset = 0
        for block in blocks:
            if use_blocks:
                label = block.label
                targets[label] = offset

            for instr in block:
                if isinstance(instr, Label):
                    targets[instr] = offset
                    continue

                if not isinstance(instr, Instr):
                    raise ValueError("expect Instr, got %s"
                                     % instr.__class__.__name__)

                arg = instr.arg
                is_jump = isinstance(arg, Label)
                if is_jump:
                    label = arg
                    arg = 0
                elif instr.op in opcode.hasconst:
                    arg = self.add_const(arg)
                elif instr.op in opcode.haslocal:
                    arg = self.add(self.varnames, arg)
                elif instr.op in opcode.hasname:
                    arg = self.add(self.names, arg)

                instr = ConcreteInstr(instr.lineno, instr.name, arg)
                if is_jump:
                    jumps.append((offset, len(instructions), instr, label))

                instructions.append(instr)
                offset += instr.size

        # fix argument of jump instructions: resolve labels
        for instr_offset, index, instr, label in jumps:
            offset = targets[label]
            if instr.op in opcode.hasjrel:
                offset = offset - (instr_offset + instr.size)

            if offset > 0xffff:
                # FIXME: should we supported this?
                raise ValueError("EXTENDED_ARG is not supported for jumps")

            # FIXME: reject negative offset?
            # (ex: JUMP_FORWARD arg must be positive)
            # ConcreteInstr._set_arg() already rejects negative argument

            instr = ConcreteInstr(instr.lineno, instr.name, offset)
            instructions[index] = instr

        return instructions

    def to_concrete_bytecode(self):
        first_const = self.bytecode.docstring
        if first_const is not UNSET:
            self.add_const(first_const)

        self.varnames.extend(self.bytecode.argnames)

        instructions = self.concrete_instructions()

        code = self.bytecode
        concrete = ConcreteBytecode()
        concrete.name = code.name
        concrete.filename = code.filename
        concrete.flags = code.flags
        # copy from abstract code
        concrete.argcount = code.argcount
        concrete.kw_only_argcount = code.kw_only_argcount
        concrete._stacksize = code._stacksize
        concrete.flags = code.flags
        concrete.first_lineno = code.first_lineno
        concrete.filename = code.filename
        concrete.name = code.name
        concrete.freevars = list(concrete.freevars)
        concrete.cellvars = list(concrete.cellvars)

        # copy from assembler
        concrete.consts = self.consts
        concrete.names = self.names
        concrete.varnames = self.varnames

        # copy instructions
        concrete[:] = instructions
        return concrete


class Bytecode(_InstrList, BaseBytecode):
    def __init__(self):
        BaseBytecode.__init__(self)
        self.argnames = []

    @staticmethod
    def from_code(code):
        return ConcreteBytecode.from_code(code).to_bytecode()

    def to_code(self):
        return self.to_concrete_bytecode().to_code()

    def to_concrete_bytecode(self):
        return _ConvertCodeToConcrete(self).to_concrete_bytecode()

    def to_bytecode(self):
        return self

    def to_bytecode_blocks(self):
        # label => instruction index
        index_to_label = {}
        label_to_index = {}
        jumps = []
        for index, instr in enumerate(self):
            if isinstance(instr, Label):
                label = instr
                label_to_index[label] = index
                index_to_label[index] = label
            elif isinstance(instr.arg, Label):
                jumps.append(instr.arg)

        block_starts = {}
        for label in jumps:
            index = label_to_index[label]
            block_starts[index] = label

        bytecode = BytecodeBlocks()
        bytecode.argcount = self.argcount
        bytecode.kw_only_argcount = self.kw_only_argcount
        bytecode._stacksize = self._stacksize
        bytecode.flags = self.flags
        bytecode.first_lineno = self.first_lineno
        bytecode.name = self.name
        bytecode.filename = self.filename
        bytecode.freevars = list(self.freevars)
        bytecode.cellvars = list(self.cellvars)
        bytecode.argnames = list(self.argnames)
        bytecode.docstring = self.docstring

        # copy instructions, convert labels to block labels
        block = bytecode[0]
        labels = {}
        jumps = []
        for index, instr in enumerate(self):
            if index != 0 and index in block_starts:
                old_label = block_starts[index]
                block = bytecode.add_block()
                labels[old_label] = block.label
                # FIXME: remap labels

            if isinstance(instr, Label):
                pass
            else:
                instr = Instr(instr.lineno, instr.name, instr.arg)
                if isinstance(instr.arg, Label):
                    jumps.append(instr)
                block.append(instr)

        for instr in jumps:
            label = instr.arg
            instr.arg = labels[label]

        return bytecode


class BytecodeBlocks(BaseBytecode):
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
                        instr = Instr(instr.lineno, instr.name, instr.arg)
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

    @staticmethod
    def from_code(code):
        return ConcreteBytecode.from_code(code).to_bytecode_blocks()

    def to_code(self):
        return self.to_concrete_bytecode().to_code()

    def to_concrete_bytecode(self):
        return _ConvertCodeToConcrete(self).to_concrete_bytecode()

    def to_bytecode(self):
        raise Exception("FIXME! not implemented")

    def to_bytecode_blocks(self):
        return self


def _dump_concrete_bytecode(code):
    line_width = 3

    offset = 0
    lineno = None
    for instr in code:
        fields = []
        if instr.lineno != lineno:
            fields.append(str(instr.lineno).rjust(line_width))
            lineno = instr.lineno
        else:
            fields.append(" " * line_width)

        fields.append("% 3s    %s" % (offset, instr.name))
        if instr.arg is not UNSET:
            fields.append("(%s)" % instr.arg)
        print(''.join(fields))

        offset += instr.size

def _dump_code(code):
    indent = ' ' * 4
    if isinstance(code, ConcreteBytecode):
        _dump_concrete_bytecode(code)
    elif isinstance(code, Bytecode):
        labels = code._labels()
        for instr in code:
            if isinstance(instr, Label):
                label = labels[instr]
                print(label)
            else:
                print(instr.format(labels))
        print()
    elif isinstance(code, BytecodeBlocks):
        labels = {}
        for block_index, block in enumerate(code, 1):
            block_label = 'label_block%s' % block_index
            labels[block.label] = block_label

            for index, instr in enumerate(block):
                if isinstance(instr, Label):
                    labels[instr] = '%s_instr%s' % (block_label, index)

        for block_index, block in enumerate(code, 1):
            print('%s:' % labels[block.label])
            for instr in block:
                if isinstance(instr, Label):
                    label = labels[instr]
                    line = '%s:' % label
                else:
                    line = indent + instr.format(labels)
                print(line)
            print()
    else:
        raise TypeError("unknown bycode code")

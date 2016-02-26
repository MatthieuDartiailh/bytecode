import dis
import opcode
import struct
import types

# alias to keep the 'bytecode' variable free
import bytecode as _bytecode
from bytecode.instr import BaseInstr, Instr, Label, SetLineno, const_key, UNSET


class ConcreteInstr(BaseInstr):
    __slots__ = ('_size',)

    def __init__(self, name, arg=UNSET, *, lineno=None):
        super().__init__(name, arg, lineno=lineno)

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
        return cls(name, arg, lineno=lineno)


class ConcreteBytecode(_bytecode.BaseBytecode, list):
    def __init__(self):
        super().__init__()
        self.consts = []
        self.names = []
        self.varnames = []

    def __repr__(self):
        return '<ConcreteBytecode instr#=%s>' % len(self)

    def __eq__(self, other):
        if type(self) != type(other):
            return False

        const_keys1 = list(map(const_key, self.consts))
        const_keys2 = list(map(const_key, other.consts))
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

                    instr = ConcreteInstr(instr.name, arg, lineno=instr.lineno)
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

            instr = Instr(instr.name, arg, lineno=instr.lineno)
            instructions.append(instr)
            offset += size

            if jump_target is not None:
                jumps.append((instr, jump_target))

        # replace jump targets with blocks
        for instr, jump_target in jumps:
            # FIXME: better error reporting on missing label
            instr.arg = labels[jump_target]

        bytecode = _bytecode.Bytecode()
        bytecode._copy_attr_from(self)

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


class _ConvertCodeToConcrete:
    def __init__(self, code):
        self.bytecode = code
        self.consts = []
        self.names = []
        self.varnames = []

    def add_const(self, value):
        key = const_key(value)
        for index, const in enumerate(self.consts):
            if const_key(const) == key:
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
        use_blocks = isinstance(self.bytecode, _bytecode.BytecodeBlocks)

        if use_blocks:
            blocks = self.bytecode
        else:
            blocks = (self.bytecode,)

        targets = {}
        jumps = []

        # convert abstract instructions to concrete instructions
        instructions = []
        offset = 0
        lineno = self.bytecode.first_lineno
        for block in blocks:
            if use_blocks:
                label = block.label
                targets[label] = offset

            for instr in block:
                if isinstance(instr, Label):
                    targets[instr] = offset
                    continue

                if isinstance(instr, SetLineno):
                    lineno = instr.lineno
                    continue

                if instr.lineno is not None:
                    lineno = instr.lineno

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

                instr = ConcreteInstr(instr.name, arg, lineno=lineno)
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

            instr = ConcreteInstr(instr.name, offset, lineno=instr.lineno)
            instructions[index] = instr

        return instructions

    def to_concrete_bytecode(self):
        first_const = self.bytecode.docstring
        if first_const is not UNSET:
            self.add_const(first_const)

        self.varnames.extend(self.bytecode.argnames)

        instructions = self.concrete_instructions()

        concrete = ConcreteBytecode()
        concrete._copy_attr_from(self.bytecode)
        concrete.consts = self.consts
        concrete.names = self.names
        concrete.varnames = self.varnames

        # copy instructions
        concrete[:] = instructions
        return concrete

import dis
import opcode
import struct
import types

__version__ = '0.0'


# Prepare code to support None value as Instr.arg for LOAD_CONST(None)
UNSET = object()


def _const_key(obj):
    # FIXME: don't use == but a key function, 1 and 1.0 are not the same
    # constant, see _PyCode_ConstantKey() in Objects/codeobject.c
    return (type(obj), obj)


class Instr:
    """
    Abstract instruction: argument can be any kind of object.
    """

    __slots__ = ('_lineno', '_name', '_arg', '_op')

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
                raise ValueError("%s opcode requires an argument" % name)
        else:
            if has_arg:
                raise ValueError("%s opcode has no argument" % name)

        self._lineno = lineno
        self._name = name
        self._arg = arg
        self._op = op

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

    def __repr__(self):
        if self._arg is not UNSET:
            return '<%s arg=%r lineno=%s>' % (self._name, self._arg, self._lineno)
        else:
            return '<%s lineno=%s>' % (self._name, self._lineno)

    def _cmp_key(self):
        if self._op in opcode.hasconst:
            arg = _const_key(self._arg)
        else:
            arg = self._arg
        return (self._lineno, self._name, arg)

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        return self._cmp_key() == other._cmp_key()

    def replace(self, name, arg=UNSET):
        return self.__class__(self._lineno, name, arg)

    def replace_arg(self, arg=UNSET):
        return self.__class__(self._lineno, self._name, arg)

    def is_jump(self):
        return (self._op in opcode.hasjrel or self._op in opcode.hasjabs)

    def is_cond_jump(self):
        # Ex: POP_JUMP_IF_TRUE, JUMP_IF_FALSE_OR_POP
        return ('JUMP_IF_' in self._name)


class ConcreteInstr(Instr):
    __slots__ = ('_size',)

    def __init__(self, lineno, name, arg=UNSET):
        if arg is not UNSET:
            if isinstance(arg, int):
                # FIXME: it looks like assemble_emit() allows negative argument
                # (minimum=-2147483648) and use a maximum of 2147483647
                if arg < 0:
                    raise ValueError("arg must be positive")
                if arg > 2147483647:
                    raise ValueError("arg must be in range 0..2147483647")
            else:
                raise TypeError("arg must be an int")

        size = 1
        if arg is not UNSET:
            size += 2
            if arg > 0xffff:
                size += 3

        super().__init__(lineno, name, arg)
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
        return cls(lineno, name, arg)



class Label:
    __slots__ = ()


class Block(list):
    def __init__(self, instructions=None):
        # create a unique object as label
        self.label = Label()
        if instructions:
            super().__init__(instructions)


class Assembler:
    def __init__(self, code):
        self.code = code
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
    def _add(names, name):
        try:
            index = names.index(name)
        except ValueError:
            index = len(names)
            names.append(name)
        return index

    def _concrete_blocks(self):
        # FIXME: rewrite this code!?

        blocks = [list(block) for block in self.code]
        labels = [block.label for block in self.code]

        # convert abstract instructions to concrete instructions,
        # but keep jump instructions using labels unchanged
        for block in blocks:
            for index, instr in enumerate(block):
                if isinstance(instr.arg, Label):
                    # handled below
                    continue

                if not isinstance(instr, ConcreteInstr):
                    arg = instr.arg
                    if instr.op in opcode.hasconst:
                        arg = self.add_const(arg)
                    elif instr.op in opcode.haslocal:
                        arg = self._add(self.varnames, arg)
                    elif instr.op in opcode.hasname:
                        arg = self._add(self.names, arg)

                    instr = ConcreteInstr(instr.lineno, instr.name, arg)
                block[index] = instr

        # find targets
        targets = {}
        offset = 0
        for block_index, block in enumerate(blocks):
            label = labels[block_index]
            targets[label] = offset
            for instr in block:
                if isinstance(instr.arg, Label):
                    # Make the assumption that the jump target fits
                    # into 2 bytes (don't need EXTENDED_ARG)
                    instr = ConcreteInstr(instr.lineno, instr.name, 0)
                offset += instr.size

        # replace abstract jumps with concrete jumps
        offset = 0
        for block in blocks:
            for index, instr in enumerate(block):
                arg = instr.arg
                if isinstance(arg, Label):
                    target_off = targets[arg]
                    if instr.op in opcode.hasjrel:
                        if isinstance(instr.arg, Label):
                            # Make the assumption that the jump target fits
                            # into 2 bytes (don't need EXTENDED_ARG)
                            tmp_instr = ConcreteInstr(instr.lineno, instr.name, 0)
                        else:
                            tmp_instr = instr

                        target_off = target_off - (offset + tmp_instr.size)
                    arg = target_off

                    # FIXME: reject negative offset?
                    # (ex: JUMP_FORWARD arg must be positive)
                    # ConcreteInstr already rejects negative argument

                    if arg > 0xffff:
                        # FIXME: should we supported this?
                        raise ValueError("EXTENDED_ARG is not supported "
                                         "for jumps")
                    instr = ConcreteInstr(instr.lineno, instr.name, arg)

                    block[index] = instr

                offset += instr.size

        return blocks

    def _assemble_lnotab(self, linenos):
        lnotab = []
        old_offset = 0
        old_lineno = self.code.first_lineno
        for offset, lineno in linenos:
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

        return b''.join(lnotab)

    def _concrete_code(self):
        first_const = self.code.docstring
        if first_const is not UNSET:
            self.add_const(first_const)

        return self._concrete_blocks()

    def assemble(self):
        # FIXME: validate code?

        first_const = self.code.docstring
        if first_const is not UNSET:
            self.add_const(first_const)

        blocks = self._concrete_blocks()

        # emit bytecode
        offset = 0
        code_str = []
        linenos = []
        for block in blocks:
            for instr in block:
                code_str.append(instr.assemble())
                linenos.append((offset, instr.lineno))
                offset += instr.size

        # assemble lnotab
        lnotab = self._assemble_lnotab(linenos)

        code_str = b''.join(code_str)

        return types.CodeType(self.code.argcount,
                              self.code.kw_only_argcount,
                              # FIXME: compute number of locals
                              self.code._nlocals,
                              # FIXME: compute stack size
                              self.code._stacksize,
                              self.code.flags,
                              code_str,
                              tuple(self.consts),
                              tuple(self.names),
                              tuple(self.varnames),
                              self.code.filename,
                              self.code.name,
                              self.code.first_lineno,
                              lnotab,
                              tuple(self.code.freevars),
                              tuple(self.code.cellvars))


def _disassemble(code_obj, *,
                 use_labels=None, extended_arg_op=False, concrete=False):
    code = code_obj.co_code
    line_starts = dict(dis.findlinestarts(code_obj))

    if use_labels is None:
        use_labels = True
    elif concrete and use_labels:
        raise ValueError("concrete and use_labels cannot be used together")

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

                if not concrete:
                    if instr.op in opcode.hasconst:
                        arg = code_obj.co_consts[arg]
                    elif instr.op in opcode.haslocal:
                        arg = code_obj.co_varnames[arg]
                    elif instr.op in opcode.hasname:
                        arg = code_obj.co_names[arg]

            if concrete:
                block[index] = ConcreteInstr(instr.lineno, instr.name, arg)
            else:
                block[index] = Instr(instr.lineno, instr.name, arg)

            offset += instr.size
            index += 1

        if extended_arg is not None:
            raise ValueError("EXTENDED_ARG at the end of a block")

    if concrete:
        cls = ConcreteCode
    else:
        cls = Code
    code = cls(code_obj.co_name,
               code_obj.co_filename,
               code_obj.co_flags)
    code.argcount = code_obj.co_argcount
    code.kw_only_argcount = code_obj.co_kwonlyargcount
    code._nlocals = code_obj.co_nlocals
    code._stacksize = code_obj.co_stacksize
    code.first_lineno = code_obj.co_firstlineno
    if concrete:
        code.names = list(code_obj.co_names)
        code.consts = list(code_obj.co_consts)
        code.varnames = list(code_obj.co_varnames)
    code.freevars = list(code_obj.co_freevars)
    code.cellvars = list(code_obj.co_cellvars)

    first_const = code_obj.co_consts[0]
    if isinstance(first_const, str):
        code.docstring = first_const
    elif first_const is None:
        code.docstring = first_const

    # delete the first empty block
    del code[0]
    for block in blocks:
        code._add_block(block)
    return code



class BaseCode:
    def __init__(self, name, filename, flags):
        self.argcount = 0
        self.kw_only_argcount = 0
        self._nlocals = 0
        self._stacksize = 0
        self.flags = flags
        self.first_lineno = 1
        self.filename = filename
        self.name = name
        # FIXME: move to ConcreteCode
        self.freevars = []
        self.cellvars = []

        self._blocks = []
        self._label_to_index = {}

        self.docstring = UNSET

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
        if type(self) != type(other):
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
        if self.filename != other.filename:
            return False
        if self.name != other.name:
            return False
        if self.freevars != other.freevars:
            return False
        if self.cellvars != other.cellvars:
            return False
        if self.docstring != other.docstring:
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

    def assemble(self):
        return Assembler(self).assemble()


class Code(BaseCode):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

    @staticmethod
    def disassemble(code_obj, *, use_labels=None, extended_arg_op=False):
        return _disassemble(code_obj,
                            use_labels=use_labels,
                            extended_arg_op=extended_arg_op)


class ConcreteCode(BaseCode):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.consts = []
        self.names = []
        self.varnames = []

    @staticmethod
    def disassemble(code_obj, *, extended_arg_op=False):
        return _disassemble(code_obj,
                            concrete=True,
                            extended_arg_op=extended_arg_op)

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


def _dump_code(code):
    offset = 0
    lineno = None
    line_width = 3

    blocks = Assembler(code)._concrete_code()

    for block_index, block in enumerate(blocks, 1):
        print("[Block #%s]" % block_index)
        for instr in block:
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
        print()

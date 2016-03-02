# alias to keep the 'bytecode' variable free
import bytecode as _bytecode
from bytecode.instr import UNSET, Label, SetLineno, Instr


class BaseBytecode:
    def __init__(self):
        self.argcount = 0
        self.kwonlyargcount = 0
        # FIXME: insane and safe value until _ConvertBytecodeToConcrete is able
        # to compute the value itself
        self._stacksize = 256
        # FIXME: use something higher level? make it private?
        self.flags = 0
        self.first_lineno = 1
        self.name = '<module>'
        self.filename = '<string>'
        self.docstring = UNSET
        self.cellvars = []
        # we cannot recreate freevars from instructions because of super()
        # special-case
        self.freevars = []

    def _copy_attr_from(self, bytecode):
        self.argcount = bytecode.argcount
        self.kwonlyargcount = bytecode.kwonlyargcount
        self._stacksize = bytecode._stacksize
        self.flags = bytecode.flags
        self.first_lineno = bytecode.first_lineno
        self.name = bytecode.name
        self.filename = bytecode.filename
        self.docstring = bytecode.docstring
        self.cellvars = list(bytecode.cellvars)
        self.freevars = list(bytecode.freevars)

    def __eq__(self, other):
        if type(self) != type(other):
            return False

        if self.argcount != other.argcount:
            return False
        if self.kwonlyargcount != other.kwonlyargcount:
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
        if self.cellvars != other.cellvars:
            return False
        if self.freevars != other.freevars:
            return False

        return True


class _InstrList(list):
    def _flat(self):
        instructions = []
        labels = {}
        jumps = []

        offset = 0
        for index, instr in enumerate(self):
            if isinstance(instr, Label):
                instructions.append('label_instr%s' % index)
                labels[instr] = offset
            else:
                if isinstance(instr, Instr) and isinstance(instr.arg, Label):
                    target_label = instr.arg
                    instr = _bytecode.ConcreteInstr(instr.name, 0,
                                                    lineno=instr.lineno)
                    jumps.append((target_label, instr))
                instructions.append(instr)
                offset += 1

        for target_label, instr in jumps:
            instr.arg = labels[target_label]

        return instructions

    def __eq__(self, other):
        if not isinstance(other, _InstrList):
            other = _InstrList(other)

        return (self._flat() == other._flat())


class Bytecode(_InstrList, BaseBytecode):
    def __init__(self, instructions=None):
        BaseBytecode.__init__(self)
        if instructions is not None:
            self.extend(instructions)
        self.argnames = []

    def __iter__(self):
        instructions = super().__iter__()
        for instr in instructions:
            if not isinstance(instr, (Label, SetLineno, Instr,
                                      _bytecode.ConcreteInstr)):
                raise ValueError("Bytecode must only contain Label, "
                                 "SetLineno, Instr and ConcreteInstr objects, "
                                 "but %s was found"
                                 % instr.__class__.__name__)

            yield instr

    @staticmethod
    def from_code(code):
        concrete = _bytecode.ConcreteBytecode.from_code(code)
        return concrete.to_bytecode()

    def to_code(self):
        return self.to_concrete_bytecode().to_code()

    def to_concrete_bytecode(self):
        converter = _bytecode._ConvertBytecodeToConcrete(self)
        return converter.to_concrete_bytecode()

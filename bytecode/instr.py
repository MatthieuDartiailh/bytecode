import math
import opcode as _opcode
import types

import bytecode as _bytecode


UNSET = object()

def const_key(obj):
    # Python implmentation of the C function _PyCode_ConstantKey()
    # of Python 3.6

    obj_type = type(obj)
    # Note: check obj_type == test_type rather than isinstance(obj, test_type)
    # to not merge instance of subtypes

    if (obj is None
       or obj is Ellipsis
       or obj_type in {int, bool, bytes, str, types.CodeType}):
        return (obj_type, obj)

    if obj_type == float:
        # all we need is to make the tuple different in either the 0.0
        # or -0.0 case from all others, just to avoid the "coercion".
        if obj == 0.0 and math.copysign(1.0, obj) < 0:
            return (obj_type, obj, None)
        else:
            return (obj_type, obj)

    if obj_type == complex:
        # For the complex case we must make complex(x, 0.)
        # different from complex(x, -0.) and complex(0., y)
        # different from complex(-0., y), for any x and y.
        # All four complex zeros must be distinguished.
        real_negzero = (obj.real == 0.0 and math.copysign(1.0, obj.real) < 0.0)
        imag_negzero = (obj.imag == 0.0 and math.copysign(1.0, obj.imag) < 0.0)

        # use True, False and None singleton as tags for the real and imag
        # sign, to make tuples different
        if real_negzero and imag_negzero:
            return (obj_type, obj, True)
        elif imag_negzero:
            return (obj_type, obj, False)
        elif real_negzero:
            return (obj_type, obj, None)
        else:
            return (obj_type, obj)

    if type(obj) == tuple:
        key = tuple(const_key(item) for item in obj)
        return (obj_type, obj, key)

    if type(obj) == frozenset:
        key = frozenset(const_key(item) for item in obj)
        return (obj_type, obj, key)

    # for other types, use the object identifier as an unique identifier
    # to ensure that they are seen as unequal.
    return (obj_type, obj, id(obj))


def _check_lineno(lineno):
    if not isinstance(lineno, int):
        raise TypeError("lineno must be an int")
    if lineno < 1:
        raise ValueError("invalid lineno")


class SetLineno:
    __slots__ = ('lineno',)

    def __init__(self, lineno):
        _check_lineno(lineno)
        self.lineno = lineno

    def __eq__(self, other):
        if not isinstance(other, SetLineno):
            return False
        return (self.lineno == other.lineno)


class Label:
    __slots__ = ()


class Instr:
    """Abstract instruction.

    lineno, name, op and arg attributes can be modified.
    """

    __slots__ = ('_name', '_opcode', '_arg', '_lineno')

    def __init__(self, name, arg=UNSET, *, lineno=None):
        self.set(name, arg, lineno=lineno)

    def _check(self, name, arg, lineno):
        # check operation name
        if not isinstance(name, str):
            raise TypeError("operation name must be a str")
        try:
            opcode = _opcode.opmap[name]
        except KeyError:
            raise ValueError("invalid operation name")

        # check lineno
        if lineno is not None:
            _check_lineno(lineno)

        if isinstance(arg, Label) and not self._has_jump(opcode):
            raise ValueError("label argument cannot be used in %s operation"
                             % name)

    def set(self, name, arg=UNSET, *, lineno=None):
        """Modify the instruction in-place.

        Replace name, arg and lineno attributes.
        """
        self._check(name, arg, lineno)

        opcode = _opcode.opmap[name]
        self._name = name
        self._opcode = opcode
        self._arg = arg
        self._lineno = lineno

    def require_arg(self):
        """Does the instruction require an argument?"""
        return (self._opcode >= _opcode.HAVE_ARGUMENT)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self.set(name, self._arg, lineno=self._lineno)

    @property
    def op(self):
        return self._opcode

    @op.setter
    def op(self, op):
        if not isinstance(op, int):
            raise TypeError("operator code must be an int")
        if 0 <= op <= 255:
            name = _opcode.opname[op]
            valid = (name != '<%r>' % op)
        else:
            valid = False
        if not valid:
            raise ValueError("invalid operator code")

        self.set(name, self._arg, lineno=self._lineno)

    @property
    def arg(self):
        return self._arg

    @arg.setter
    def arg(self, arg):
        self.set(self._name, arg, lineno=self._lineno)

    @property
    def lineno(self):
        return self._lineno

    @lineno.setter
    def lineno(self, lineno):
        self.set(self._name, self._arg, lineno=lineno)

    def copy(self):
        return self.__class__(self._name, self._arg, lineno=self._lineno)

    # FIXME: stack effect

    def __repr__(self):
        if self._arg is not UNSET:
            return ('<%s arg=%r lineno=%s>'
                    % (self._name, self._arg, self._lineno))
        else:
            return ('<%s lineno=%s>'
                    % (self._name, self._lineno))

    def _cmp_key(self, labels=None):
        arg = self._arg
        if self._opcode in _opcode.hasconst:
            arg = const_key(arg)
        elif isinstance(arg, Label) and labels is not None:
            arg = labels[arg]
        return (self._lineno, self._name, arg)

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        return self._cmp_key() == other._cmp_key()

    @staticmethod
    def _has_jump(opcode):
        return (opcode in _opcode.hasjrel
                or opcode in _opcode.hasjabs)

    def has_jump(self):
        return self._has_jump(self._opcode)

    def is_cond_jump(self):
        """Is a conditional jump?"""
        # Ex: POP_JUMP_IF_TRUE, JUMP_IF_FALSE_OR_POP
        return ('JUMP_IF_' in self._name)

    def is_uncond_jump(self):
        """Is an unconditional jump?"""
        return self.name in {'JUMP_FORWARD', 'JUMP_ABSOLUTE'}

    def is_final(self):
        if self._name in {'RETURN_VALUE', 'RAISE_VARARGS',
                          'BREAK_LOOP', 'CONTINUE_LOOP'}:
            return True
        if self.is_uncond_jump():
            return True
        return False

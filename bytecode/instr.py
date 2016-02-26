import math
import opcode
import types


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


class Label:
    __slots__ = ()


class BaseInstr:
    __slots__ = ('_name', '_op', '_arg', '_lineno')

    def __init__(self, name, arg=UNSET, *, lineno=None):
        self._set_name(name)
        self._arg = arg
        self._set_lineno(lineno)

    @property
    def name(self):
        return self._name

    @property
    def op(self):
        return self._op

    @property
    def arg(self):
        return self._arg

    @property
    def lineno(self):
        return self._lineno

    def copy(self):
        return self.__class__(self._name, self._arg, lineno=self._lineno)

    # FIXME: stack effect

    def _set_lineno(self, lineno):
        if lineno is not None:
            _check_lineno(lineno)
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
            arg = const_key(arg)
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

    def is_uncond_jump(self):
        """Is an unconditiona jump?"""
        return self.name in {'JUMP_FORWARD', 'JUMP_ABSOLUTE'}

    def _is_final(self):
        if self._name in {'RETURN_VALUE', 'RAISE_VARARGS',
                          'BREAK_LOOP', 'CONTINUE_LOOP'}:
            return True
        if self.is_uncond_jump():
            return True
        return False


class Instr(BaseInstr):
    """Abstract instruction.

    lineno, name, op and arg attributes can be modified.

    arg is not checked.
    """

    __slots__ = ()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._set_name(name)

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

    @property
    def arg(self):
        return self._arg

    @arg.setter
    def arg(self, arg):
        self._arg = arg

    @property
    def lineno(self):
        return self._lineno

    @lineno.setter
    def lineno(self, lineno):
        self._set_lineno(lineno)

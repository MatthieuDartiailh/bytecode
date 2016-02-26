import opcode

UNSET = object()


def const_key(obj):
    # FIXME: don't use == but a key function, 1 and 1.0 are not the same
    # constant, see _PyCode_ConstantKey() in Objects/codeobject.c
    return (type(obj), obj)


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

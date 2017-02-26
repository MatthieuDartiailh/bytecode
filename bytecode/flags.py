# alias to keep the 'bytecode' variable free
from enum import IntEnum
from collections import defaultdict

import bytecode as _bytecode


class CoFlags(IntEnum):
    """Possible values of the co_flags attribute of Code object.

    Notes
    -----
    We do not rely on inspect values here as some of them are missing and
    furthermore would be version dependent.

    """
    CO_OPTIMIZED             = 0x00001  # noqa
    CO_NEWLOCALS             = 0x00002  # noqa
    CO_VARARGS               = 0x00004  # noqa
    CO_VARKEYWORDS           = 0x00008  # noqa
    CO_NESTED                = 0x00010  # noqa
    CO_GENERATOR             = 0x00020  # noqa
    CO_NOFREE                = 0x00040  # noqa
    # New in Python 3.5
    CO_COROUTINE             = 0x00080  # noqa
    CO_ITERABLE_COROUTINE    = 0x00100  # noqa
    # New in Python 3.6
    CO_ASYNC_GENERATOR       = 0x00200  # noqa

    # __future__ flags
    CO_FUTURE_GENERATOR_STOP = 0x80000  # noqa


_CAN_DEDUCE_FROM_CODE = ('optimized', 'generator', 'nofree', 'coroutine')


class Flags:
    """Object representing the flags set for the bytecode.

    Flags can be bools indicating their state, or for some of them None
    indicating that the value should be inferred from the ConcreteBytecode
    object passed when converting to an integer. If no bytecode is provided the
    default values are used.

    The flags whose natural values can be inferred are:
    - optimized
    - generator
    - nofree
    - coroutine

    """

    def __init__(self, int_or_flags=0):

        self._forced = {}

        if isinstance(int_or_flags, Flags):
            self._defaults = int_or_flags._defaults.copy()
            self._forced = int_or_flags._forced.copy()
        elif isinstance(int_or_flags, int):
            self._defaults = {name.split('_', 1)[1].lower():
                              bool(int_or_flags & val)
                              for name, val in CoFlags.__members__.items()}
        else:
            msg = ("Flags object should be passed either None, an int  or a "
                   "Flags instance at init, got {}.")
            raise TypeError(msg.format(int_or_flags))

    def __eq__(self, other):
        if isinstance(other, int):
            return self.to_int() == other
        elif isinstance(other, Flags):
            return ((self._defaults == other._defaults) and
                    (self._forced == other._forced))
        else:
            raise TypeError('Cannot compare Flags to {}'.format(other))

    def to_int(self, bytecode=None):

        flags = defaultdict(bool)
        flags.update(self._forced)
        print(bytecode)
        if bytecode is not None:
            if not isinstance(bytecode, _bytecode.ConcreteBytecode):
                msg = 'Expected a ConcreteBytecode instance not %s'
                raise ValueError(msg % bytecode)
            instr_names = {i.name for i in bytecode
                           if not isinstance(i, _bytecode.SetLineno)}

        print(self._defaults)
        for k, v in self._defaults.items():
            if k not in flags:
                print(k in _CAN_DEDUCE_FROM_CODE, bytecode is not None)
                if k in _CAN_DEDUCE_FROM_CODE and bytecode is not None:
                    print('y')
                    if k == 'optimized':
                        flags[k] = not (instr_names & {'STORE_NAME',
                                                       'LOAD_NAME',
                                                       'DELETE_NAME'})
                    elif k == 'generator':
                        if not self.async_generator:
                            flags[k] = bool(instr_names & {'YIELD_VALUE',
                                                           'YIELD_FROM'})
                        else:
                            flags[k] = False
                    elif k == 'nofree':
                        flags[k] = not (instr_names & {'LOAD_CLOSURE',
                                                       'LOAD_DEREF',
                                                       'STORE_DEREF',
                                                       'DELETE_DEREF',
                                                       'LOAD_CLASSDEREF'})
                    else:
                        if not any((self.async_generator,
                                    self.iterable_coroutine)):
                            flags[k] = bool(instr_names & {'GET_AWAITABLE',
                                                           'GET_AITER',
                                                           'GET_ANEXT',
                                                           'BEFORE_ASYNC_WITH',
                                                           'SETUP_ASYNC_WITH'})
                        else:
                            flags[k] = False
                else:
                    flags[k] = v

        if [flags[k] for k in ('coroutine', 'iterable_coroutine',
                               'async_generator')].count(True) > 1:
            raise ValueError("Code cannot be a coroutine and an iterable "
                             "coroutine and an async generator")
        if flags['generator'] and flags['async_generator']:
            raise ValueError("Code cannot be both generator and async "
                             "generator.")

        return sum(flags[k] and getattr(CoFlags, 'CO_' + k.upper())
                   for k in flags)

    def get_default(self, flag_name):
        return self._defaults[flag_name]

    @property
    def optimized(self):
        """Denotes that the code block uses fast locals.

        """
        return self._forced.get('optimized')

    @optimized.setter
    def optimized(self, value):
        print(value)
        if value is None:
            del self._forced['optimized']
        elif not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean or None')
        else:
            self._forced['optimized'] = value

    @property
    def newlocals(self):
        """Denotes that a new dictionary should be created for the code block.

        """
        return self._forced.get('newlocals', self._defaults['newlocals'])

    @newlocals.setter
    def newlocals(self, value):
        if not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean')
        self._forced['newlocals'] = value

    @property
    def varargs(self):
        """The compiled code block has a varargs argument.

        """
        return self._forced.get('varargs', self._defaults['varargs'])

    @varargs.setter
    def varargs(self, value):
        if not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean')
        self._forced['varargs'] = value

    @property
    def varkeywords(self):
        """The compiled code block has a varkeyword argument.

        """
        return self._forced.get('varkeywords', self._defaults['varkeywords'])

    @varkeywords.setter
    def varkeywords(self, value):
        if not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean')
        self._forced['varkeywords'] = value

    @property
    def nested(self):
        """Denotes that nested scopes are enabled in the code block.

        """
        return self._forced.get('nested', self._defaults['nested'])

    @nested.setter
    def nested(self, value):
        if not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean')
        self._forced['nested'] = value

    @property
    def generator(self):
        """The compiled code block is a generator code block.

        """
        return self._forced.get('generator')

    @generator.setter
    def generator(self, value):
        if value is None:
            del self._forced['generator']
        elif not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean or None')
        else:
            self._forced['generator'] = value

    @property
    def nofree(self):
        """Flag set if there are no free or cell variables.

        """
        return self._forced.get('nofree')

    @nofree.setter
    def nofree(self, value):
        if value is None:
            del self._forced['nofree']
        elif not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean or None')
        else:
            self._forced['nofree'] = value

    @property
    def coroutine(self):
        """Flag set for coroutine functions (defined with 'async def' keywords)

        New in Python version 3.5

        """
        return self._forced.get('coroutine')

    @coroutine.setter
    def coroutine(self, value):
        if value is None:
            del self._forced['coroutine']
        elif not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean or None')
        else:
            self._forced['coroutine'] = value

    @property
    def iterable_coroutine(self):
        """Flag used to transform generators into generator-based coroutines

        This flag is incompatible with coroutine.

        New in Python version 3.5

        """
        return self._forced.get('iterable_coroutine',
                                self._defaults['iterable_coroutine'])

    @iterable_coroutine.setter
    def iterable_coroutine(self, value):
        if not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean')
        self._forced['iterable_coroutine'] = value

    @property
    def async_generator(self):
        """Flag set when the code object is an asynchronous generator function

        New in Python version 3.6

        """
        return self._forced.get('async_generator',
                                self._defaults['async_generator'])

    @async_generator.setter
    def async_generator(self, value):
        if not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean')
        self._forced['async_generator'] = value

    @property
    def future_generator_stop(self):
        """Flag set if the code block use from __future__ import generator_stop

        """
        return self._forced.get('future_generator_stop',
                                self._defaults['future_generator_stop'])

    @future_generator_stop.setter
    def future_generator_stop(self, value):
        if not isinstance(value, bool):
            raise ValueError('Flag value should be a boolean')
        self._forced['future_generator_stop'] = value

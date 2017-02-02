# alias to keep the 'bytecode' variable free
from enum import IntEnum

import bytecode as _bytecode


class CoFlags(IntEnum):
    """Possible values of the co_flags attribute of Code object.

    Notes
    -----
    We do not rely on inspect values here as some of them are missing and
    furthermore would be version dependent.

    """
    CO_OPTIMIZED             = 0x0001
    CO_NEWLOCALS             = 0x0002
    CO_VARARGS               = 0x0004
    CO_VARKEYWORDS           = 0x0008
    CO_NESTED                = 0x0010
    CO_GENERATOR             = 0x0020
    CO_NOFREE                = 0x0400
    # New in Python 3.5
    CO_COROUTINE             = 0x0080
    CO_ITERABLE_COROUTINE    = 0x0100
    #♣ New in Python 3.6
    CO_ASYNC_GENERATOR       = 0x0200
    CO_FUTURE_GENERATOR8STOP = 0x80000


_CAN_DEDUCE_FROM_CODE = ('optimized', 'generator', 'nofree', 'coroutine')


class Flags:
    """Object representing the flags set for the bytecode.

    Flags can be bools indicating their state, or for some of them None
    indicating that the value should be inferred from the bytecode object
    passed when converting to an integer. If no bytecode is provided the
    default values are used.

    The flags whose natural values can be inferred are:
    - optimized
    - generator
    - nofree
    - coroutine

    """

    def __init__(self, int_or_flags=None):

        self._defaults = {}
        self._forced = {}

        if isinstance(int_or_flags, Flags):
            self._defaults = int_or_flags._defaults.copy()
            self._forced = int_or_flags._forced.copy()
        elif isinstance(int_or_flags, int):
            self._defaults = {name.split('_', 1)[1].lower():
                              bool(int_or_flags & val)
                              for name, val in CoFlags.__members__.items()}
        else:
            raise TypeError("Flags object should be passed either None, an int"
                            " or a Flags instance at init.")

    def to_int(self, bytecode=None):

        flags = self._forced.copy()
        if bytecode:
            instr_names = {i.name for i in bytecode}
        for k, v in self._defaults.items():
            if k not in flags:
                if k in _CAN_DEDUCE_FROM_CODE and bytecode:
                    if k == 'optimized':
                        flags[k] = not (instr_names & {'STORE_NAME',
                                                       'LOAD_NAME',
                                                       'DELETE_NAME'})
                    elif k == 'generator':
                        if not any(self.async_generator, self.coroutine,
                                   self.iterable_coroutine):
                            flags[k] = instr_names & {'YIELD_VALUE',
                                                      'YIELD_FROM'}
                        else:
                            flags[k] = False
                    elif k == 'nofree':
                        flags[k] = not (instr_names & {'LOAD_CLOSURE',
                                                       'LOAD_DEREF',
                                                       'STORE_DEREF',
                                                       'DELETE_DEREF',
                                                       'LOAD_CLASSDEREF'})
                    else:
                        if not self.iterable_coroutine:
                            flags[k] = instr_names & {'GET_AWAITABLE',
                                                      'GET_AITER',
                                                      'GET_ANEXT',
                                                      'BEFORE_ASYNC_WITH',
                                                      'SETUP_ASYNC_WITH'}
                        else:
                            flags[k] = False
                else:
                    flags[k] = v

        if [flags[k] for k in ('coroutine', 'iterable_coroutine',
                               'async_generator')].count() > 1:
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
        if not isinstance(value, bool) or value is None:
            raise ValueError('Flag value should be a boolean or None')
        if value is None:
            del self._forced['optimized']
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
        return self._forced.get('generator', self._defaults['generator'])

    @generator.setter
    def generator(self, value):
        if not isinstance(value, bool) or value is None:
            raise ValueError('Flag value should be a boolean or None')
        if value is None:
            del self._forced['generator']
        else:
            self._forced['generator'] = value

    @property
    def nofree(self):
        """Flag set if there are no free or cell variables.

        """
        return self._forced.get('nofree')

    @nofree.setter
    def nofree(self, value):
        if not isinstance(value, bool) or value is None:
            raise ValueError('Flag value should be a boolean or None')
        if value is None:
            del self._forced['nofree']
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
        if not isinstance(value, bool) or value is None:
            raise ValueError('Flag value should be a boolean or None')
        if value is None:
            del self._forced['coroutine']
        else:
            self._forced['coroutine'] = value

    @property
    def iterable_coroutine(self):
        """Flag used to transform generators into generator-based coroutines

        This flag is incompatible with coroutine.

        New in Python version 3.5

        """
        return self._forced.get('iterable_coroutine')

    @iterable_coroutine.setter
    def iterable_coroutine(self, value):
        if not isinstance(value, bool) or value is None:
            raise ValueError('Flag value should be a boolean or None')
        if value is None:
            del self._forced['iterable_coroutine']
        else:
            self._forced['iterable_coroutine'] = value

    @property
    def async_generator(self):
        """Flag set when the code object is an asynchronous generator function

        New in Python version 3.6

        """
        return self._forced.get('async_generator')

    @async_generator.setter
    def async_generator(self, value):
        if not isinstance(value, bool) or value is None:
            raise ValueError('Flag value should be a boolean or None')
        if value is None:
            del self._forced['async_generator']
        else:
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

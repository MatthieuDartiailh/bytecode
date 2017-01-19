# alias to keep the 'bytecode' variable free
import bytecode as _bytecode


class Flags:
    """
    """

    def __init__(self, int_or_flags=None):

        self._defaults = {}
        self._forced = {}

    def to_int(self, concrete_code=None):
        """
        """
        pass

    @property
    def optimized(self):
        """
        """
        pass

    @optimized.setter
    def optimized(self, value):
        pass

    @property
    def newlocals(self):
        """
        """
        pass

    @newlocals.setter
    def newlocals(self, value):
        pass

    @property
    def varargs(self):
        """
        """
        pass

    @varargs.setter
    def varargs(self, value):
        pass

    @property
    def varkeywords(self):
        """
        """
        pass

    @varkeywords.setter
    def varkeywords(self, value):
        pass

    @property
    def nested(self):
        """
        """
        pass

    @nested.setter
    def nested(self, value):
        pass

    @property
    def generator(self):
        """
        """
        pass

    @generator.setter
    def generator(self, value):
        pass

    @property
    def nofree(self):
        """
        """
        pass

    @nofree.setter
    def nofree(self, value):
        pass

    @property
    def coroutine(self):
        """
        """
        pass

    @coroutine.setter
    def coroutine(self, value):
        pass

    @property
    def iterable_coroutine(self):
        """
        """
        pass

    @iterable_coroutine.setter
    def iterable_coroutine(self, value):
        pass

    @property
    def future_generator_stop(self):
        """
        """
        pass

    @future_generator_stop.setter
    def future_generator_stop(self, value):
        pass

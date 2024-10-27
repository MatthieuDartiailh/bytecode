# Function making heavy use of cell and free vars to test bytecode round tripping
# capabilities.


def simple_cellvar():  # a cellvar in f
    a = 1

    def g():  # a freevar in g
        return a

    return g


def cellvar_share_name(a=1):  # a cellvar in f, but stored as varname
    def g():  # a freevar in g
        return a

    return g


def cellvar_shared_and_unshared(a=1):  # a, b cellvar in f, but a stored as varname
    b = 1

    def g():  # a, b freevar in g
        return a + b

    return g


class A:
    a = 1

    def f(self):
        return 1


def class_loadderef():
    a = 1

    class B(A):
        b = a

    return B.b


# NOTE aliasing super such that there is no LOAD_GLOBAL super cause the omission of
# the required implicit __class__ cell which breaks the subsequent call
# Under Python 3.11 the creation of cellvars is made explicit by MAKE_CELL


def class_super():
    class B(A):
        def f(self):
            super().f()

    return B().f


def test_freevar():
    class Foo:
        r = 0

        @classmethod
        def bar(cls, k):
            class Snafu(k):
                def do_debug(self, arg):
                    cls.r += 1
                    return super().d(arg)

            return Snafu


# NOTE this is not really a cell var case but it ensures proper
# placements of CACHE vs labels
_localedirs: dict = {}
_default_localedir = ""


def bindtextdomain(domain="", localedir=None):
    global _localedirs
    if localedir is not None:
        _localedirs[domain] = localedir
    return _localedirs.get(domain, _default_localedir)


TEST_CASES = [
    simple_cellvar,
    cellvar_share_name,
    cellvar_shared_and_unshared,
    class_super,
    class_loadderef,
    bindtextdomain,
    test_freevar,
]

if __name__ == "__main__":
    import dis
    import inspect

    for f in TEST_CASES:
        print("--------------------------------------------------------------")
        for line in inspect.getsourcelines(f)[0]:  # type: ignore
            print(line.rstrip())
        print()
        dis.dis(f.__code__)
        print()

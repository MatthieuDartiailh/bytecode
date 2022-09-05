# flake8: noqa
import contextlib
import sys


# XXX add exception group cases

def try_except():
    try:
        a = 1
    except Exception:
        return 0

    return a


def try_multi_except():
    try:
        a = 1
    except ValueError:
        return 0
    except Exception:
        return 0

    return a


def try_finally():
    try:
        a = 1
    finally:
        c = 2

    return a


def try_except_else():
    try:
        a = 1
    except Exception:
        return 0
    else:
        b = 1

    return a


def try_except_finally():
    try:
        a = 1
    except Exception:
        return 0
    finally:
        c = 1

    return a


def try_except_else_finally():
    try:
        a = 1
    except Exception:
        return 0
    else:
        b = 1
    finally:
        c = 1

    return a


def nested_try():
    try:
        a = 1
        try:
            b = 2
        except Exception:
            pass
        c = 3
    except Exception:
        d = 4

    return a


def try_in_except():
    try:
        a = 1
    except Exception:
        d = 4
        try:
            b = 2
        except Exception:
            return 0
        c = 3

    return a


def with_no_store():
    with contextlib.nullcontext(1):
        a = 1
    return a


def with_store():
    with contextlib.nullcontext(1) as b:
        a = 1
    return a


def try_with():
    try:
        with contextlib.nullcontext(1):
            a = 1
    except Exception:
        return 0

    return a


def with_try():
    with contextlib.nullcontext(1):
        try:
            b = 1
        except Exception:
            return 0

    return b


TEST_CASES = [
    try_except,
    try_multi_except,
    try_finally,
    try_except_else,
    try_except_finally,
    try_except_else_finally,
    nested_try,
    try_in_except,
    with_no_store,
    with_store,
    try_with,
    with_try,
]

# On 3.8 those two cases fail due to a re-ordering of the fast variables
if sys.version_info < (3, 9):
    TEST_CASES.remove(try_except_else_finally)
    TEST_CASES.remove(try_except_finally)

if __name__ == "__main__":
    import dis
    import inspect

    for f in TEST_CASES:
        print("--------------------------------------------------------------")
        for l in inspect.getsourcelines(f)[0]:
            print(l.rstrip())
        print()
        dis.dis(f)
        print()

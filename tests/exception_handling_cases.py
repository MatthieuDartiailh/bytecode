# flake8: noqa
import contextlib
import sys

# Functions attempting to cover most combination of exception error handling mechanisms
# to test bytecode round tripping capabilities.

# NOTE we use call in except/finally clause expression requiring a larger stack usage


def try_except():
    try:
        a = 1
    except Exception:
        return min(1, 2)

    return a


def try_multi_except():
    try:
        a = 1
    except ValueError:
        return min(1, 2)
    except Exception:
        return min(1, 2)

    return a


def try_finally():
    try:
        a = 1
    finally:
        c = min(1, 2)

    return a


def try_except_else():
    try:
        a = 1
    except Exception:
        return min(1, 2)
    else:
        b = 1

    return a


def try_except_finally():
    try:
        a = 1
    except Exception:
        return min(1, 2)
    finally:
        c = 1

    return a


def try_except_else_finally():
    try:
        a = 1
    except Exception:
        return min(1, 2)
    else:
        b = 1
    finally:
        c = min(1, 2)

    return a


def nested_try():
    try:
        a = 1
        try:
            b = 2
        except Exception:
            e = min(1, 2)
        c = 3
    except Exception:
        d = min(1, 2)

    return a


def try_in_except():
    try:
        a = 1
    except Exception:
        d = 4
        try:
            b = 2
        except Exception:
            return min(1, 2)
        c = 3

    return a


# Trick since the syntax does not exist pre-3.11
if sys.version_info >= (3, 11):
    src = """
def try_except_group():
    try:
        a = 1
    except* ValueError:
        b = min(1, 2)
    return a
"""
    exec(src)


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
        return min(1, 2)

    return a


def with_try():
    with contextlib.nullcontext(1):
        try:
            b = 1
        except Exception:
            return min(1, 2)

    return b


async def async_with_no_store():
    async with contextlib.nullcontext():
        a = 1
    return a


async def async_with_store():
    async with contextlib.nullcontext() as b:
        a = 1
    return a


async def try_async_with():
    try:
        async with contextlib.nullcontext(1):
            a = 1
    except Exception:
        return min(1, 2)

    return a


async def async_with_try():
    async with contextlib.nullcontext(1):
        try:
            b = 1
        except Exception:
            return min(1, 2)

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
    async_with_no_store,
    async_with_store,
    try_async_with,
    async_with_try,
]

if sys.version_info >= (3, 11):
    TEST_CASES.insert(0, try_except_group)  # type: ignore

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

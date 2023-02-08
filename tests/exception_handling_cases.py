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


def nested_try_finally():
    try:
        a = 1
        try:
            b = 2
        finally:
            e = min(1, 2)
        c = 3
    finally:
        d = min(1, 2)

    return a


# This case exhibits several pitfalls:
# - a TryBegin appears in the block as a reraise requiring to create an artificial
#  TryBegin/TryEnd pair
# - complex exit conditions through jumps
# - TryEnd following a non conditional jump
def nested_try_with_looping_construct():
    try:
        try:
            a = 1
        finally:
            b = min(1, 2)

        while a:
            c = 0
            if min(5, 6):
                break
    finally:
        c = 3

    return a


# Test converting from bytecode to concrete in the presence of extended arg
# which means the number of instruction before generating extended arg is not
# the offset.
# Here if we ignore this we end with wrong start/stop value in the table
def try_except_with_extended_arg():
    a = [1]
    b = [(1, 2), (3, 4)]
    for x in a:
        if a[0] is b[1]:
            try:
                a.append(b.index((a[0], 2)))
            except BrokenPipeError:
                sys.stdout.write(str(a))
                sys.stdout.flush()
            else:
                c = 1
                d = 2
                b.append(a.append((c, d)))
                sys.stdout.write(str(b))
                sys.stdout.flush()


# Here extended arg can lead to omitting a TryEnd because we went over the offset
# value at which we expected it.
def try_except_with_extended_arg2():
    a = list(range(10))

    with contextlib.nullcontext() as selector:
        while a.pop():
            # timeout = self._remaining_time(endtime)
            if sys is not None and sys.hexversion < 0:
                sys.stdout.write(a)
                raise RuntimeError("test")

            for key in sys.version_info:
                # Dead code for the execution but help trigger the bug this test
                # is meant to avoid regressing.
                if key is sys.stdin:
                    chunk = a[self._input_offset : self._input_offset + _PIPE_BUF]
                    try:
                        self._input_offset += os.write(key.fd, chunk)
                    except BrokenPipeError:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    else:
                        if self._input_offset >= len(self._input):
                            selector.unregister(key.fileobj)
                            key.fileobj.close()


def try_except_in_except():
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


def try_finally_in_except():
    try:
        a = min(1, 2)
    except Exception:
        try:
            b = min(3, 4)
        finally:
            c = 1
        return c
    return a


def try_except_in_else():
    try:
        a = min(1, 2)
    except Exception:
        a = 1
    else:
        try:
            b = min(3, 4)
        except Exception:
            b = 1
        return b

    return a


def try_finally_in_else():
    try:
        a = 1
    except ValueError as e:
        return
    else:
        try:
            pass
        finally:
            a = 1


def try_except_in_finally():
    try:
        a = min(1, 2)
    finally:
        try:
            a = max(1, 2)
        except Exception:
            a = 1

    return a


def try_finally_in_finally():
    a = 0
    try:
        a = min(1, 2)
    finally:
        try:
            a = max(1, 2)
        finally:
            a = min(a, 1)

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
    nested_try_finally,
    nested_try_with_looping_construct,
    try_except_in_except,
    try_except_in_else,
    try_except_in_finally,
    try_finally_in_except,
    try_finally_in_else,
    try_finally_in_finally,
    try_except_with_extended_arg,
    try_except_with_extended_arg2,
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
    # Fail due to a varname re-ordering
    TEST_CASES.remove(try_finally)
    TEST_CASES.remove(nested_try_finally)
    TEST_CASES.remove(try_finally_in_except)
    TEST_CASES.remove(nested_try_with_looping_construct)
    TEST_CASES.remove(try_except_with_extended_arg)
    TEST_CASES.remove(try_except_with_extended_arg2)

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

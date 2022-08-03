# flake8: noqa
import contextlib


def try_except():
    try:
        a = 1
    except Exception:
        return 0


def try_except_else():
    try:
        a = 1
    except Exception:
        return 0
    else:
        b = 1


def try_except_finally():
    try:
        a = 1
    except Exception:
        return 0
    finally:
        c = 1


def try_except_else_finally():
    try:
        a = 1
    except Exception:
        return 0
    else:
        b = 1
    finally:
        c = 1


def with_no_store():
    with contextlib.nullcontext(1):
        pass


def with_store():
    with contextlib.nullcontext(1) as b:
        pass


def try_with():
    try:
        with contextlib.nullcontext(1):
            pass
    except Exception:
        return 0


def with_try():
    with contextlib.nullcontext(1):
        try:
            b = 1
        except Exception:
            return 0

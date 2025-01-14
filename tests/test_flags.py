#!/usr/bin/env python3
import sys
import unittest
from copy import copy

from bytecode import (
    Bytecode,
    CompilerFlags,
    ConcreteBytecode,
    ConcreteInstr,
    ControlFlowGraph,
)
from bytecode.flags import infer_flags
from bytecode.instr import UNSET, FreeVar, Instr
from bytecode.utils import PY311, PY312


def trivial():
    pass


def _fact(a):
    def inner():
        return a

    return inner


hasfree = _fact(1)


def gen():
    yield 1


async def trivial_async():
    pass


async def async_await(a):
    await a


async def async_with_comprehension():
    return [await i for i in range(10)]


async def async_generator():
    yield 1


FLAG_INFERENCE_TEST_CASES = [
    trivial,
    hasfree,
    gen,
    trivial_async,
    async_await,
    async_with_comprehension,
    async_generator,
]


class FlagsTests(unittest.TestCase):
    def test_type_validation_on_inference(self):
        with self.assertRaises(ValueError):
            infer_flags(1)

    def test_flag_inference(self):
        # Check no loss of non-infered flags
        code = ControlFlowGraph()
        code.flags |= (
            CompilerFlags.NEWLOCALS
            | CompilerFlags.VARARGS
            | CompilerFlags.VARKEYWORDS
            | CompilerFlags.NESTED
            | CompilerFlags.FUTURE_GENERATOR_STOP
        )
        code.update_flags()
        for f in (
            CompilerFlags.NEWLOCALS,
            CompilerFlags.VARARGS,
            CompilerFlags.VARKEYWORDS,
            CompilerFlags.NESTED,
            CompilerFlags.NOFREE,
            CompilerFlags.OPTIMIZED,
            CompilerFlags.FUTURE_GENERATOR_STOP,
        ):
            self.assertTrue(bool(code.flags & f))

        # Infer optimized and nofree
        code = Bytecode()
        flags = infer_flags(code)
        self.assertTrue(bool(flags & CompilerFlags.OPTIMIZED))
        self.assertTrue(bool(flags & CompilerFlags.NOFREE))
        code.append(Instr("STORE_NAME", "a"))
        flags = infer_flags(code)
        self.assertFalse(bool(flags & CompilerFlags.OPTIMIZED))
        self.assertTrue(bool(flags & CompilerFlags.NOFREE))
        code.append(Instr("STORE_DEREF", FreeVar("b")))
        code.update_flags()
        self.assertFalse(bool(code.flags & CompilerFlags.OPTIMIZED))
        self.assertFalse(bool(code.flags & CompilerFlags.NOFREE))

    def test_function_rountrip(self):
        for f in FLAG_INFERENCE_TEST_CASES:
            for cls in (Bytecode, ConcreteBytecode):
                with self.subTest(f"Testing {f.__name__} with {cls}"):
                    b = cls.from_code(f.__code__)
                    existing = copy(b.flags)
                    b.update_flags()
                    # NOTE: as far as I can tell NOFREE is not used by CPython anymore
                    # it shows up nowhere in the interpreter logic and only exist in
                    # dis and inspect...
                    self.assertEqual(
                        existing & ~CompilerFlags.NOFREE,
                        b.flags & ~CompilerFlags.NOFREE,
                    )

    def test_async_gen_no_flag_is_async_None(self):
        # Test inference in the absence of any flag set on the bytecode

        # Infer generator
        code = ConcreteBytecode()
        code.append(
            ConcreteInstr("YIELD_VALUE", 0) if PY312 else ConcreteInstr("YIELD_VALUE")
        )
        if PY311:
            code.append(ConcreteInstr("RESUME", 1))
        code.update_flags()
        self.assertTrue(bool(code.flags & CompilerFlags.GENERATOR))

        # Infer coroutine
        code = ConcreteBytecode()
        code.append(
            ConcreteInstr("GET_AWAITABLE", 0 if sys.version_info >= (3, 11) else UNSET)
        )
        code.update_flags()
        self.assertTrue(bool(code.flags & CompilerFlags.COROUTINE))

        # Infer coroutine or async generator
        for i, r, expected in (
            ("YIELD_VALUE", 1, CompilerFlags.ASYNC_GENERATOR),
            ("YIELD_VALUE", 2, CompilerFlags.ASYNC_GENERATOR),
            # YIELD_VALUE is used for normal await flow in Py 3.11+ when followed
            # by a RESUME whose lowest two bits are set to 3
            *((("YIELD_VALUE", 3, CompilerFlags.COROUTINE),) if PY311 else ()),
            ("YIELD_FROM", 0, CompilerFlags.COROUTINE),
        ):
            with self.subTest(i):
                if PY311 and i == "YIELD_FROM":
                    self.skipTest("YIELD_FROM does not exist on 3.11")
                code = ConcreteBytecode()
                code.append(ConcreteInstr("GET_AWAITABLE", 0 if PY311 else UNSET))
                code.append(ConcreteInstr(i, 0) if PY312 else ConcreteInstr(i))
                if PY311:
                    code.append(ConcreteInstr("RESUME", r))
                code.update_flags()
                self.assertTrue(bool(code.flags & expected))

    def test_async_gen_no_flag_is_async_True(self):
        # Test inference when we request an async function

        # Force coroutine
        code = ConcreteBytecode()
        code.update_flags(is_async=True)
        self.assertTrue(bool(code.flags & CompilerFlags.COROUTINE))

        # Infer coroutine or async generator
        for i, r, expected in (
            ("YIELD_VALUE", 1, CompilerFlags.ASYNC_GENERATOR),
            ("YIELD_VALUE", 2, CompilerFlags.ASYNC_GENERATOR),
            # YIELD_VALUE is used for normal await flow in Py 3.11+ when followed
            # by a RESUME whose lowest two bits are set to 3
            *((("YIELD_VALUE", 3, CompilerFlags.COROUTINE),) if PY311 else ()),
            ("YIELD_FROM", 0, CompilerFlags.COROUTINE),
        ):
            with self.subTest(i):
                if PY311 and i == "YIELD_FROM":
                    self.skipTest("YIELD_FROM does not exist on 3.11")
                code = ConcreteBytecode()
                code.append(ConcreteInstr(i, 0) if PY312 else ConcreteInstr(i))
                if PY311:
                    code.append(ConcreteInstr("RESUME", r))
                code.update_flags(is_async=True)
                self.assertEqual(code.flags & expected, expected)

    def test_async_gen_no_flag_is_async_False(self):
        # Test inference when we request a non-async function

        # Infer generator
        code = ConcreteBytecode()
        code.append(
            ConcreteInstr("YIELD_VALUE", 0) if PY312 else ConcreteInstr("YIELD_VALUE")
        )
        if PY311:
            code.append(ConcreteInstr("RESUME", 1))
        code.flags = CompilerFlags(CompilerFlags.COROUTINE)
        code.update_flags(is_async=False)
        self.assertTrue(bool(code.flags & CompilerFlags.GENERATOR))

        # Abort on coroutine
        code = ConcreteBytecode()
        code.append(
            ConcreteInstr("GET_AWAITABLE", 0 if sys.version_info >= (3, 11) else UNSET)
        )
        code.flags = CompilerFlags(CompilerFlags.COROUTINE)
        with self.assertRaises(ValueError):
            code.update_flags(is_async=False)

    def test_async_gen_flags(self):
        # Test inference in the presence of pre-existing flags

        for is_async in (None, True):
            # Infer generator
            code = ConcreteBytecode()
            code.append(
                ConcreteInstr("YIELD_VALUE", 0)
                if PY312
                else ConcreteInstr("YIELD_VALUE")
            )
            if PY311:
                code.append(ConcreteInstr("RESUME", 1))
            for f, expected in (
                (CompilerFlags.COROUTINE, CompilerFlags.ASYNC_GENERATOR),
                (CompilerFlags.ASYNC_GENERATOR, CompilerFlags.ASYNC_GENERATOR),
                (CompilerFlags.ITERABLE_COROUTINE, CompilerFlags.ITERABLE_COROUTINE),
            ):
                code.flags = CompilerFlags(f)
                code.update_flags(is_async=is_async)
                self.assertTrue(bool(code.flags & expected))

            # Infer coroutine
            if not PY311:
                code = ConcreteBytecode()
                code.append(ConcreteInstr("YIELD_FROM"))
                for f, expected in (
                    (CompilerFlags.COROUTINE, CompilerFlags.COROUTINE),
                    (CompilerFlags.ASYNC_GENERATOR, CompilerFlags.COROUTINE),
                    (
                        CompilerFlags.ITERABLE_COROUTINE,
                        CompilerFlags.ITERABLE_COROUTINE,
                    ),
                ):
                    code.flags = CompilerFlags(f)
                    code.update_flags(is_async=is_async)
                    self.assertTrue(bool(code.flags & expected))

            # Crash on ITERABLE_COROUTINE with async bytecode
            code = ConcreteBytecode()
            code.append(ConcreteInstr("GET_AWAITABLE", 0 if PY311 else UNSET))
            code.flags = CompilerFlags(CompilerFlags.ITERABLE_COROUTINE)
            with self.assertRaises(ValueError):
                code.update_flags(is_async=is_async)


if __name__ == "__main__":
    unittest.main()  # pragma: no cover

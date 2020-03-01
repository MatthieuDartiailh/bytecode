#!/usr/bin/env python3
import unittest
from bytecode import (CompilerFlags, ConcreteBytecode, ConcreteInstr, Bytecode,
                      ControlFlowGraph)
from bytecode.flags import infer_flags


class FlagsTests(unittest.TestCase):

    def test_type_validation_on_inference(self):
        with self.assertRaises(ValueError):
            infer_flags(1)

    def test_flag_inference(self):

        # Check no loss of non-infered flags
        code = ControlFlowGraph()
        code.flags |= (CompilerFlags.NEWLOCALS | CompilerFlags.VARARGS
                       | CompilerFlags.VARKEYWORDS | CompilerFlags.NESTED
                       | CompilerFlags.FUTURE_GENERATOR_STOP)
        code.update_flags()
        for f in (CompilerFlags.NEWLOCALS, CompilerFlags.VARARGS,
                  CompilerFlags.VARKEYWORDS, CompilerFlags.NESTED,
                  CompilerFlags.NOFREE, CompilerFlags.OPTIMIZED,
                  CompilerFlags.FUTURE_GENERATOR_STOP):
            self.assertTrue(bool(code.flags & f))

        # Infer optimized and nofree
        code = Bytecode()
        flags = infer_flags(code)
        self.assertTrue(bool(flags & CompilerFlags.OPTIMIZED))
        self.assertTrue(bool(flags & CompilerFlags.NOFREE))
        code.append(ConcreteInstr('STORE_NAME', 1))
        flags = infer_flags(code)
        self.assertFalse(bool(flags & CompilerFlags.OPTIMIZED))
        self.assertTrue(bool(flags & CompilerFlags.NOFREE))
        code.append(ConcreteInstr('STORE_DEREF', 2))
        code.update_flags()
        self.assertFalse(bool(code.flags & CompilerFlags.OPTIMIZED))
        self.assertFalse(bool(code.flags & CompilerFlags.NOFREE))

    def test_async_gen_no_flag_is_async_None(self):
        # Test inference in the absence of any flag set on the bytecode

        # Infer generator
        code = ConcreteBytecode()
        code.append(ConcreteInstr('YIELD_VALUE'))
        self.assertTrue(bool(infer_flags(code) & CompilerFlags.GENERATOR))

        # Infer coroutine
        code = ConcreteBytecode()
        code.append(ConcreteInstr('GET_AWAITABLE'))
        self.assertTrue(bool(infer_flags(code) & CompilerFlags.COROUTINE))

        # Infer coroutine or async generator
        for i, expected in (("YIELD_VALUE", CompilerFlags.ASYNC_GENERATOR),
                            ("YIELD_FROM", CompilerFlags.COROUTINE)):
            code = ConcreteBytecode()
            code.append(ConcreteInstr('GET_AWAITABLE'))
            code.append(ConcreteInstr(i))
            print(i, expected, infer_flags(code))
            self.assertTrue(bool(infer_flags(code) & expected))

    def test_async_gen_no_flag_is_async_True(self):
        # Test inference when we request an async function

        # Force coroutine
        code = ConcreteBytecode()
        self.assertTrue(bool(infer_flags(code, True) &
                             CompilerFlags.COROUTINE))

        # Infer coroutine or async generator
        for i, expected in (("YIELD_VALUE", CompilerFlags.ASYNC_GENERATOR),
                            ("YIELD_FROM", CompilerFlags.COROUTINE)):
            code = ConcreteBytecode()
            code.append(ConcreteInstr(i))
            print(i, expected)
            self.assertTrue(bool(infer_flags(code, True) & expected))

    def test_async_gen_no_flag_is_async_False(self):
        # Test inference when we request a non-async function

        # Infer generator
        code = ConcreteBytecode()
        code.append(ConcreteInstr('YIELD_VALUE'))
        code.flags = CompilerFlags(CompilerFlags.COROUTINE)
        self.assertTrue(bool(infer_flags(code, False) &
                             CompilerFlags.GENERATOR))

        # Abort on coroutine
        code = ConcreteBytecode()
        code.append(ConcreteInstr('GET_AWAITABLE'))
        code.flags = CompilerFlags(CompilerFlags.COROUTINE)
        with self.assertRaises(ValueError):
            infer_flags(code, False)

    # TODO
    def test_async_gen_flags(self):
        # Test inference in the presence of pre-existing flags

        for is_async in (None, True):

            # Infer generator
            code = ConcreteBytecode()
            code.append(ConcreteInstr('YIELD_VALUE'))
            for f, expected in ((CompilerFlags.COROUTINE,
                                 CompilerFlags.ASYNC_GENERATOR),
                                (CompilerFlags.ASYNC_GENERATOR,
                                 CompilerFlags.ASYNC_GENERATOR),
                                (CompilerFlags.ITERABLE_COROUTINE,
                                 CompilerFlags.ITERABLE_COROUTINE)):
                code.flags = CompilerFlags(f)
                self.assertTrue(bool(infer_flags(code, is_async) & expected))

            # Infer coroutine
            code = ConcreteBytecode()
            code.append(ConcreteInstr('YIELD_FROM'))
            for f, expected in ((CompilerFlags.COROUTINE,
                                 CompilerFlags.COROUTINE),
                                (CompilerFlags.ASYNC_GENERATOR,
                                 CompilerFlags.COROUTINE),
                                (CompilerFlags.ITERABLE_COROUTINE,
                                 CompilerFlags.ITERABLE_COROUTINE)):
                code.flags = CompilerFlags(f)
                self.assertTrue(bool(infer_flags(code, is_async) & expected))

            # Crash on ITERABLE_COROUTINE with async bytecode
            code = ConcreteBytecode()
            code.append(ConcreteInstr('GET_AWAITABLE'))
            code.flags = CompilerFlags(CompilerFlags.ITERABLE_COROUTINE)
            with self.assertRaises(ValueError):
                infer_flags(code, is_async)


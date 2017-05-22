#!/usr/bin/env python3
import unittest
from bytecode import (CompilerFlags, ConcreteBytecode, ConcreteInstr, Bytecode,
                      ControlFlowGraph)
from bytecode.flags import infer_flags


class FlagsTests(unittest.TestCase):

    def test_flag_inference(self):

        # Check no loss of non-infered flags
        code = ControlFlowGraph()
        code.flags |= (CompilerFlags.NEWLOCALS | CompilerFlags.VARARGS |
                       CompilerFlags.VARKEYWORDS | CompilerFlags.NESTED |
                       CompilerFlags.FUTURE_GENERATOR_STOP)
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

        # Infer generator
        code = ConcreteBytecode()
        code.append(ConcreteInstr('YIELD_VALUE'))
        for is_async, expected in ((False, CompilerFlags.GENERATOR),
                                   (True, CompilerFlags.ASYNC_GENERATOR)):
            self.assertTrue(bool(infer_flags(code, is_async) & expected))

        # Infer coroutine
        code = ConcreteBytecode()
        code.append(ConcreteInstr('GET_AWAITABLE'))
        iter_flags = CompilerFlags(CompilerFlags.ITERABLE_COROUTINE)
        for f, expected in ((CompilerFlags(0), True), (iter_flags, False)):
            code.flags = f
            self.assertEqual(bool(infer_flags(code) & CompilerFlags.COROUTINE),
                             expected)

        # Test check flag sanity
        code.append(ConcreteInstr('YIELD_VALUE'))
        code.flags = CompilerFlags(CompilerFlags.GENERATOR |
                                   CompilerFlags.COROUTINE)
        infer_flags(code, is_async=True)  # Just want to be sure it pases
        with self.assertRaises(ValueError):
            code.update_flags()

        with self.assertRaises(ValueError):
            infer_flags(None)

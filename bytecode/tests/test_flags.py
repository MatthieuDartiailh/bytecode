#!/usr/bin/env python3
import unittest
from bytecode import Flags, Flag, Bytecode, ConcreteBytecode, ConcreteInstr


class FlagsTests(unittest.TestCase):

    def test_instantiation(self):

        empty_flag = Flags()
        self.assertFalse(any(empty_flag._defaults.values()))
        self.assertFalse(empty_flag._forced)

        flags = Flags(Flag.OPTIMIZED | Flag.NESTED)
        for m in Flag.__members__:
            expected = (True
                        if m in {'OPTIMIZED', 'NESTED'} else
                        False)
            self.assertEqual(flags.get_default(m.lower()), expected)

        new = Flags(flags)
        self.assertEqual(new, flags)
        # Ensure that we really copied the original one.
        new.newlocals = True
        self.assertFalse(flags.newlocals)

        # Check type validation
        with self.assertRaises(TypeError):
            Flags(object())

    def test_equality(self):

        f1, f2 = Flags(1), Flags(1)
        self.assertEqual(f1, f2)
        f2.nested = True
        self.assertNotEqual(f1, f2)
        with self.assertRaises(TypeError):
            Flags(1) == object()

    def test_conversions(self):

        self.assertEqual(Flags().to_int(), 0)

        # Test conversion without inference.
        for val in Flag.__members__.values():
            self.assertEqual(Flags(val).to_int(), val)

        with self.assertRaises(ValueError):
            Flags().to_int(Bytecode())

        # Infer optimized and nofree
        forced_flag = Flags()
        forced_flag.optimized = False
        forced_flag.nofree = False
        code = ConcreteBytecode()
        for f, expected in ((Flags(), True), (forced_flag, False)):
            self.assertEqual(bool(f.to_int(code) & Flag.OPTIMIZED),
                             expected)
            self.assertEqual(bool(f.to_int(code) & Flag.NOFREE),
                             expected)

        # Infer generator
        code = ConcreteBytecode()
        code.append(ConcreteInstr('YIELD_VALUE'))
        async_flags = Flags(Flag.ASYNC_GENERATOR)
        for f, expected in ((Flags(), True), (async_flags, False)):
            self.assertEqual(bool(f.to_int(code) & Flag.GENERATOR),
                             expected)

        # Infer coroutine
        code = ConcreteBytecode()
        code.append(ConcreteInstr('GET_AWAITABLE'))
        iter_flags = Flags(Flag.ITERABLE_COROUTINE)
        async_flags = Flags(Flag.ASYNC_GENERATOR)
        for f, expected in ((Flags(), True), (iter_flags, False),
                            (async_flags, False)):
            self.assertEqual(bool(f.to_int(code) & Flag.COROUTINE),
                             expected)

        # Test check flag sanity
        with self.assertRaises(ValueError):
            Flags(Flag.GENERATOR | Flag.COROUTINE).to_int()

    def test_descriptors(self):

        from bytecode.flags import _CAN_DEDUCE_FROM_CODE
        flags = Flags()
        for m in [m.lower() for m in Flag.__members__]:
            if m in _CAN_DEDUCE_FROM_CODE:
                self.assertIs(getattr(flags, m), None)
            else:
                self.assertFalse(getattr(flags, m))
            setattr(flags, m, True)
            self.assertTrue(getattr(flags, m))

            with self.assertRaises(ValueError):
                setattr(flags, m, 5 if m in _CAN_DEDUCE_FROM_CODE else None)

        for m in _CAN_DEDUCE_FROM_CODE:
            setattr(flags, m, None)
            self.assertIs(getattr(flags, m), None)

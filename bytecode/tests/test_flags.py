#!/usr/bin/env python3
import unittest
from bytecode import Flags, CoFlags, Bytecode, ConcreteBytecode, ConcreteInstr


class FlagsTests(unittest.TestCase):

    def test_instantiation(self):

        empty_flag = Flags()
        self.assertFalse(any(empty_flag._defaults.values()))
        self.assertFalse(empty_flag._forced)

        flags = Flags(CoFlags.CO_OPTIMIZED + CoFlags.CO_NESTED)
        for m in CoFlags.__members__:
            expected = (True
                        if m in {'CO_OPTIMIZED', 'CO_NESTED'} else
                        False)
            self.assertEqual(flags.get_default(m.split('_', 1)[1].lower()),
                             expected)

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
        for val in CoFlags.__members__.values():
            self.assertEqual(Flags(val).to_int(), val)

        with self.assertRaises(ValueError):
            Flags().to_int(Bytecode())

        # Infer optimized and nofree
        forced_flag = Flags()
        forced_flag.optimized = False
        forced_flag.nofree = False
        for f, expected in ((Flags(), True), (forced_flag, False)):
            self.assertEqual(bool(f.to_int(ConcreteBytecode()) &
                                  CoFlags.CO_OPTIMIZED),
                             expected)
            self.assertEqual(bool(f.to_int(ConcreteBytecode()) &
                                  CoFlags.CO_NOFREE),
                             expected)

        # Infer generator
        code = ConcreteBytecode()
        code.append(ConcreteInstr('YIELD_VALUE'))
        async_flags = Flags(CoFlags.CO_ASYNC_GENERATOR)
        for f, expected in ((Flags(), True), (async_flags, False)):
            self.assertEqual(bool(f.to_int(code) & CoFlags.CO_GENERATOR),
                             expected)

        # Infer coroutine
        code = ConcreteBytecode()
        code.append(ConcreteInstr('GET_AWAITABLE'))
        iter_flags = Flags(CoFlags.CO_ITERABLE_COROUTINE)
        async_flags = Flags(CoFlags.CO_ASYNC_GENERATOR)
        for f, expected in ((Flags(), True), (iter_flags, False),
                            (async_flags, False)):
            self.assertEqual(bool(f.to_int(code) & CoFlags.CO_COROUTINE),
                             expected)

        # Test check flag sanity
        with self.assertRaises(ValueError):
            Flags(CoFlags.CO_GENERATOR + CoFlags.CO_COROUTINE).to_int()

    def test_descriptors(self):

        from bytecode.flags import _CAN_DEDUCE_FROM_CODE
        flags = Flags()
        for m in [m.split('_', 1)[1].lower() for m in CoFlags.__members__]:
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

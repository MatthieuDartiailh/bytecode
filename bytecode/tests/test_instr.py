#!/usr/bin/env python3
import opcode
import unittest
from bytecode import UNSET, Label, Instr, CellVar, FreeVar, BasicBlock
from bytecode.tests import TestCase


class InstrTests(TestCase):

    def test_constructor(self):
        # invalid line number
        with self.assertRaises(TypeError):
            Instr("NOP", lineno="x")
        with self.assertRaises(ValueError):
            Instr("NOP", lineno=0)

        # invalid name
        with self.assertRaises(TypeError):
            Instr(1)
        with self.assertRaises(ValueError):
            Instr("xxx")

    def test_invalid_arg(self):
        label = Label()
        block = BasicBlock()

        # has_jump()
        self.assertRaises(TypeError, Instr, "JUMP_ABSOLUTE", 1)
        self.assertRaises(TypeError, Instr, "JUMP_ABSOLUTE", 1.0)
        Instr("JUMP_ABSOLUTE", label)
        Instr("JUMP_ABSOLUTE", block)

        # hasfree
        self.assertRaises(TypeError, Instr, "LOAD_DEREF", "x")
        Instr("LOAD_DEREF", CellVar("x"))
        Instr("LOAD_DEREF", FreeVar("x"))

        # haslocal
        self.assertRaises(TypeError, Instr, "LOAD_FAST", 1)
        Instr("LOAD_FAST", "x")

        # hasname
        self.assertRaises(TypeError, Instr, "LOAD_NAME", 1)
        Instr("LOAD_NAME", "x")

        # hasconst
        self.assertRaises(ValueError, Instr, "LOAD_CONST")   # UNSET
        self.assertRaises(ValueError, Instr, "LOAD_CONST", label)
        self.assertRaises(ValueError, Instr, "LOAD_CONST", block)
        Instr("LOAD_CONST", 1.0)
        Instr("LOAD_CONST", object())

        # HAVE_ARGUMENT
        self.assertRaises(ValueError, Instr, "CALL_FUNCTION", -1)
        self.assertRaises(TypeError, Instr, "CALL_FUNCTION", 3.0)
        Instr("CALL_FUNCTION", 3)

        # test maximum argument
        self.assertRaises(ValueError, Instr, "CALL_FUNCTION", 2147483647 + 1)
        instr = Instr("CALL_FUNCTION", 2147483647)
        self.assertEqual(instr.arg, 2147483647)

        # not HAVE_ARGUMENT
        self.assertRaises(ValueError, Instr, "NOP", 0)
        Instr("NOP")

    def test_attr(self):
        instr = Instr("LOAD_CONST", 3, lineno=5)
        self.assertEqual(instr.name, 'LOAD_CONST')
        self.assertEqual(instr.opcode, 100)
        self.assertEqual(instr.arg, 3)
        self.assertEqual(instr.lineno, 5)

        # invalid values/types
        self.assertRaises(ValueError, setattr, instr, 'lineno', 0)
        self.assertRaises(TypeError, setattr, instr, 'lineno', 1.0)
        self.assertRaises(TypeError, setattr, instr, 'name', 5)
        self.assertRaises(TypeError, setattr, instr, 'opcode', 1.0)
        self.assertRaises(ValueError, setattr, instr, 'opcode', -1)
        self.assertRaises(ValueError, setattr, instr, 'opcode', 255)

        # arg can take any attribute but cannot be deleted
        instr.arg = -8
        instr.arg = object()
        self.assertRaises(AttributeError, delattr, instr, 'arg')

        # no argument
        instr = Instr("ROT_TWO")
        self.assertIs(instr.arg, UNSET)

    def test_modify_op(self):
        instr = Instr("LOAD_NAME", 'x')
        load_fast = opcode.opmap['LOAD_FAST']
        instr.opcode = load_fast
        self.assertEqual(instr.name, 'LOAD_FAST')
        self.assertEqual(instr.opcode, load_fast)

    def test_extended_arg(self):
        instr = Instr("LOAD_CONST", 0x1234abcd)
        self.assertEqual(instr.arg, 0x1234abcd)

    def test_slots(self):
        instr = Instr("NOP")
        with self.assertRaises(AttributeError):
            instr.myattr = 1

    def test_compare(self):
        instr = Instr("LOAD_CONST", 3, lineno=7)
        self.assertEqual(instr, Instr("LOAD_CONST", 3, lineno=7))

        # different lineno
        self.assertNotEqual(instr, Instr("LOAD_CONST", 3))
        self.assertNotEqual(instr, Instr("LOAD_CONST", 3, lineno=6))
        # different op
        self.assertNotEqual(instr, Instr("LOAD_FAST", 'x', lineno=7))
        # different arg
        self.assertNotEqual(instr, Instr("LOAD_CONST", 4, lineno=7))

    def test_has_jump(self):
        label = Label()
        jump = Instr("JUMP_ABSOLUTE", label)
        self.assertTrue(jump.has_jump())

        instr = Instr("LOAD_FAST", 'x')
        self.assertFalse(instr.has_jump())

    def test_is_cond_jump(self):
        label = Label()
        jump = Instr("POP_JUMP_IF_TRUE", label)
        self.assertTrue(jump.is_cond_jump())

        instr = Instr("LOAD_FAST", 'x')
        self.assertFalse(instr.is_cond_jump())

    def test_is_uncond_jump(self):
        label = Label()
        jump = Instr("JUMP_ABSOLUTE", label)
        self.assertTrue(jump.is_uncond_jump())

        instr = Instr("POP_JUMP_IF_TRUE", label)
        self.assertFalse(instr.is_uncond_jump())

    def test_const_key_not_equal(self):
        def check(value):
            self.assertEqual(Instr('LOAD_CONST', value),
                             Instr('LOAD_CONST', value))

        def func():
            pass

        check(None)
        check(0)
        check(0.0)
        check(b'bytes')
        check('text')
        check(Ellipsis)
        check((1, 2, 3))
        check(frozenset({1, 2, 3}))
        check(func.__code__)
        check(object())

    def test_const_key_equal(self):
        neg_zero = -0.0
        pos_zero = +0.0

        # int and float: 0 == 0.0
        self.assertNotEqual(Instr('LOAD_CONST', 0),
                            Instr('LOAD_CONST', 0.0))

        # float: -0.0 == +0.0
        self.assertNotEqual(Instr('LOAD_CONST', neg_zero),
                            Instr('LOAD_CONST', pos_zero))

        # complex
        self.assertNotEqual(Instr('LOAD_CONST', complex(neg_zero, 1.0)),
                            Instr('LOAD_CONST', complex(pos_zero, 1.0)))
        self.assertNotEqual(Instr('LOAD_CONST', complex(1.0, neg_zero)),
                            Instr('LOAD_CONST', complex(1.0, pos_zero)))

        # tuple
        self.assertNotEqual(Instr('LOAD_CONST', (0,)),
                            Instr('LOAD_CONST', (0.0,)))
        nested_tuple1 = (0,)
        nested_tuple1 = (nested_tuple1,)
        nested_tuple2 = (0.0,)
        nested_tuple2 = (nested_tuple2,)
        self.assertNotEqual(Instr('LOAD_CONST', nested_tuple1),
                            Instr('LOAD_CONST', nested_tuple2))

        # frozenset
        self.assertNotEqual(Instr('LOAD_CONST', frozenset({0})),
                            Instr('LOAD_CONST', frozenset({0.0})))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import opcode
import unittest
from bytecode import Instr, UNSET
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
            Instr(1, lineno=1)
        with self.assertRaises(ValueError):
            Instr("xxx", lineno=1)

    def test_attr(self):
        instr = Instr("LOAD_CONST", 3, lineno=5)
        self.assertEqual(instr.lineno, 5)
        self.assertEqual(instr.name, 'LOAD_CONST')
        self.assertEqual(instr.arg, 3)
        self.assertEqual(instr.op, opcode.opmap['LOAD_CONST'])
        self.assertRaises(ValueError, setattr, instr, 'lineno', 0)
        self.assertRaises(TypeError, setattr, instr, 'lineno', 1.0)
        self.assertRaises(TypeError, setattr, instr, 'name', 5)
        self.assertRaises(TypeError, setattr, instr, 'op', 1.0)
        self.assertRaises(ValueError, setattr, instr, 'op', -1)
        self.assertRaises(ValueError, setattr, instr, 'op', 255)

        # modify op
        op = opcode.opmap['LOAD_FAST']
        instr.op = op
        self.assertEqual(instr.op, op)
        self.assertEqual(instr.name, 'LOAD_FAST')

        instr = Instr("ROT_TWO", lineno=1)
        self.assertIs(instr.arg, UNSET)
        self.assertEqual(instr.op, opcode.opmap['ROT_TWO'])

    def test_extended_arg(self):
        instr = Instr("LOAD_CONST", 0x1234abcd)
        self.assertEqual(instr.arg, 0x1234abcd)

    def test_slots(self):
        instr = Instr("NOP", lineno=1)
        with self.assertRaises(AttributeError):
            instr.myattr = 1

    def test_compare(self):
        instr = Instr("LOAD_CONST", 3, lineno=7)
        self.assertEqual(instr, Instr("LOAD_CONST", 3, lineno=7))

        self.assertNotEqual(instr, Instr("LOAD_CONST", 3))
        self.assertNotEqual(instr, Instr("LOAD_CONST", 3, lineno=6))
        self.assertNotEqual(instr, Instr("LOAD_FAST", 3, lineno=7))
        self.assertNotEqual(instr, Instr("LOAD_CONST", 4, lineno=7))

    def test_is_jump(self):
        jump = Instr("JUMP_ABSOLUTE", 3)
        self.assertTrue(jump.is_jump())

        instr = Instr("LOAD_FAST", 2)
        self.assertFalse(instr.is_jump())

    def test_is_cond_jump(self):
        jump = Instr("POP_JUMP_IF_TRUE", 3)
        self.assertTrue(jump.is_cond_jump())

        instr = Instr("LOAD_FAST", 2)
        self.assertFalse(instr.is_cond_jump())


if __name__ == "__main__":
    unittest.main()

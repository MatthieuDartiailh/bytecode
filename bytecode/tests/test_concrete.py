#!/usr/bin/env python3
import types
import unittest
from bytecode import ConcreteInstr, ConcreteBytecode
from bytecode.tests import get_code, TestCase


class ConcreteInstrTests(TestCase):
    def test_constructor(self):
        # argument?
        with self.assertRaises(ValueError):
            ConcreteInstr(1, "LOAD_CONST")
        with self.assertRaises(ValueError):
            ConcreteInstr(1, "ROT_TWO", 33)

        # invalid argument
        with self.assertRaises(TypeError):
            ConcreteInstr(1, "LOAD_CONST", 1.0)
        with self.assertRaises(ValueError):
            ConcreteInstr(1, "LOAD_CONST", -1)
        with self.assertRaises(ValueError):
            ConcreteInstr(1, "LOAD_CONST", 2147483647+1)

        # test maximum argument
        instr = ConcreteInstr(1, "LOAD_CONST", 2147483647)
        self.assertEqual(instr.arg, 2147483647)

    def test_attr(self):
        instr = ConcreteInstr(1, "LOAD_CONST", 5)
        self.assertRaises(AttributeError, setattr, instr, 'name', 'LOAD_FAST')
        self.assertRaises(AttributeError, setattr, instr, 'lineno', 1)
        self.assertRaises(AttributeError, setattr, instr, 'arg', 2)

    def test_size(self):
        self.assertEqual(ConcreteInstr(1, 'ROT_TWO').size, 1)
        self.assertEqual(ConcreteInstr(1, 'LOAD_CONST', 3).size, 3)
        self.assertEqual(ConcreteInstr(1, 'LOAD_CONST', 0x1234abcd).size, 6)

    def test_disassemble(self):
        instr = ConcreteInstr.disassemble(1, b'\td\x03\x00', 0)
        self.assertEqual(instr, ConcreteInstr(1, "NOP"))

        instr = ConcreteInstr.disassemble(1, b'\td\x03\x00', 1)
        self.assertEqual(instr, ConcreteInstr(1, "LOAD_CONST", 3))

        code = b'\x904\x12d\xcd\xab'
        instr = ConcreteInstr.disassemble(1, code, 0)
        self.assertEqual(instr, ConcreteInstr(1, 'EXTENDED_ARG', 0x1234))

    def test_to_code(self):
        instr = ConcreteInstr(1, "NOP")
        self.assertEqual(instr.assemble(), b'\t')

        instr = ConcreteInstr(1, "LOAD_CONST", 3)
        self.assertEqual(instr.assemble(), b'd\x03\x00')

        instr = ConcreteInstr(1, "LOAD_CONST", 0x1234abcd)
        self.assertEqual(instr.assemble(), b'\x904\x12d\xcd\xab')

    def test_get_jump_target(self):
        jump_abs = ConcreteInstr(1, "JUMP_ABSOLUTE", 3)
        self.assertEqual(jump_abs.get_jump_target(100), 3)

        jump_forward = ConcreteInstr(1, "JUMP_FORWARD", 5)
        self.assertEqual(jump_forward.get_jump_target(10), 18)


class ConcreteBytecodeTests(TestCase):
    def test_attr(self):
        code = get_code("x = 5")
        bytecode = ConcreteBytecode.from_code(code)
        self.assertEqual(bytecode.consts, [5, None])
        self.assertEqual(bytecode.names, ['x'])
        self.assertEqual(bytecode.varnames, [])
        # FIXME: test other attributes

    def test_disassemble_concrete(self):
        code = get_code("x = 5")
        bytecode = ConcreteBytecode.from_code(code)
        expected = [ConcreteInstr(1, 'LOAD_CONST', 0),
                    ConcreteInstr(1, 'STORE_NAME', 0),
                    ConcreteInstr(1, 'LOAD_CONST', 1),
                    ConcreteInstr(1, 'RETURN_VALUE')]
        self.assertListEqual(list(bytecode), expected)
        self.assertEqual(bytecode.consts, [5, None])
        self.assertEqual(bytecode.names, ['x'])

    def test_disassemble_extended_arg(self):
        # Create a code object from arbitrary bytecode
        co_code = b'\x904\x12d\xcd\xab'
        code = get_code('x=1')
        code = types.CodeType(code.co_argcount,
                              code.co_kwonlyargcount,
                              code.co_nlocals,
                              code.co_stacksize,
                              code.co_flags,
                              co_code,
                              code.co_consts,
                              code.co_names,
                              code.co_varnames,
                              code.co_filename,
                              code.co_name,
                              code.co_firstlineno,
                              code.co_lnotab,
                              code.co_freevars,
                              code.co_cellvars)

        # without EXTENDED_ARG opcode
        bytecode = ConcreteBytecode.from_code(code)
        self.assertListEqual(list(bytecode),
                             [ConcreteInstr(1, "LOAD_CONST", 0x1234abcd)])

        # with EXTENDED_ARG opcode
        bytecode = ConcreteBytecode.from_code(code, extended_arg_op=True)
        self.assertListEqual(list(bytecode),
                             [ConcreteInstr(1, 'EXTENDED_ARG', 0x1234),
                              ConcreteInstr(1, 'LOAD_CONST', 0xabcd)])


if __name__ == "__main__":
    unittest.main()

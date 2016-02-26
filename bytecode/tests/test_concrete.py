#!/usr/bin/env python3
import types
import unittest
from bytecode import ConcreteInstr, ConcreteBytecode
from bytecode.tests import get_code, TestCase


class ConcreteInstrTests(TestCase):
    def test_constructor(self):
        # argument?
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", lineno=1)
        with self.assertRaises(ValueError):
            ConcreteInstr("ROT_TWO", 33, lineno=1)

        # invalid argument
        with self.assertRaises(TypeError):
            ConcreteInstr("LOAD_CONST", 1.0, lineno=1)
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", -1, lineno=1)

        # test maximum argument
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", 2147483647+1, lineno=1)

        instr = ConcreteInstr("LOAD_CONST", 2147483647, lineno=1)
        self.assertEqual(instr.arg, 2147483647)

    def test_attr(self):
        instr = ConcreteInstr("LOAD_CONST", 5, lineno=1)
        self.assertRaises(AttributeError, setattr, instr, 'name', 'LOAD_FAST')
        self.assertRaises(AttributeError, setattr, instr, 'lineno', 1)
        self.assertRaises(AttributeError, setattr, instr, 'arg', 2)

    def test_size(self):
        self.assertEqual(ConcreteInstr('ROT_TWO', lineno=1).size, 1)
        self.assertEqual(ConcreteInstr('LOAD_CONST', 3, lineno=1).size, 3)
        self.assertEqual(ConcreteInstr('LOAD_CONST', 0x1234abcd, lineno=1).size, 6)

    def test_disassemble(self):
        instr = ConcreteInstr.disassemble(1, b'\td\x03\x00', 0)
        self.assertEqual(instr, ConcreteInstr("NOP", lineno=1))

        instr = ConcreteInstr.disassemble(1, b'\td\x03\x00', 1)
        self.assertEqual(instr, ConcreteInstr("LOAD_CONST", 3, lineno=1))

        code = b'\x904\x12d\xcd\xab'
        instr = ConcreteInstr.disassemble(1, code, 0)
        self.assertEqual(instr, ConcreteInstr('EXTENDED_ARG', 0x1234, lineno=1))

    def test_to_code(self):
        instr = ConcreteInstr("NOP", lineno=1)
        self.assertEqual(instr.assemble(), b'\t')

        instr = ConcreteInstr("LOAD_CONST", 3, lineno=1)
        self.assertEqual(instr.assemble(), b'd\x03\x00')

        instr = ConcreteInstr("LOAD_CONST", 0x1234abcd, lineno=1)
        self.assertEqual(instr.assemble(), b'\x904\x12d\xcd\xab')

    def test_get_jump_target(self):
        jump_abs = ConcreteInstr("JUMP_ABSOLUTE", 3, lineno=1)
        self.assertEqual(jump_abs.get_jump_target(100), 3)

        jump_forward = ConcreteInstr("JUMP_FORWARD", 5, lineno=1)
        self.assertEqual(jump_forward.get_jump_target(10), 18)


class ConcreteBytecodeTests(TestCase):
    def test_attr(self):
        code = get_code("x = 5")
        bytecode = ConcreteBytecode.from_code(code)
        self.assertEqual(bytecode.consts, [5, None])
        self.assertEqual(bytecode.names, ['x'])
        self.assertEqual(bytecode.varnames, [])
        # FIXME: test other attributes

    def test_from_code(self):
        code = get_code("x = 5")
        bytecode = ConcreteBytecode.from_code(code)
        expected = [ConcreteInstr('LOAD_CONST', 0, lineno=1),
                    ConcreteInstr('STORE_NAME', 0, lineno=1),
                    ConcreteInstr('LOAD_CONST', 1, lineno=1),
                    ConcreteInstr('RETURN_VALUE', lineno=1)]
        self.assertListEqual(list(bytecode), expected)
        self.assertEqual(bytecode.consts, [5, None])
        self.assertEqual(bytecode.names, ['x'])

    def test_from_code_extended_arg(self):
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
                             [ConcreteInstr("LOAD_CONST", 0x1234abcd, lineno=1)])

        # with EXTENDED_ARG opcode
        bytecode = ConcreteBytecode.from_code(code, extended_arg_op=True)
        self.assertListEqual(list(bytecode),
                             [ConcreteInstr('EXTENDED_ARG', 0x1234, lineno=1),
                              ConcreteInstr('LOAD_CONST', 0xabcd, lineno=1)])


if __name__ == "__main__":
    unittest.main()

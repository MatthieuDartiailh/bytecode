#!/usr/bin/env python3
import types
import unittest
from bytecode import (Label, Instr, SetLineno, Bytecode,
                      ConcreteInstr, ConcreteBytecode)
from bytecode.tests import get_code, TestCase


class ConcreteInstrTests(TestCase):
    def test_constructor(self):
        with self.assertRaises(ValueError):
            # need an argument
            ConcreteInstr("LOAD_CONST")
        with self.assertRaises(ValueError):
            # must not have an argument
            ConcreteInstr("ROT_TWO", 33)

        # invalid argument
        with self.assertRaises(TypeError):
            ConcreteInstr("LOAD_CONST", 1.0)
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", -1)

        # test maximum argument
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", 2147483647+1)

        instr = ConcreteInstr("LOAD_CONST", 2147483647)
        self.assertEqual(instr.arg, 2147483647)

    def test_attr(self):
        instr = ConcreteInstr("LOAD_CONST", 5, lineno=12)
        self.assertEqual(instr.name, 'LOAD_CONST')
        self.assertEqual(instr.op, 100)
        self.assertEqual(instr.arg, 5)
        self.assertEqual(instr.lineno, 12)
        self.assertEqual(instr.size, 3)

        # attributes are read-only
        self.assertRaises(AttributeError, setattr, instr, 'name', 'LOAD_CONST')
        self.assertRaises(AttributeError, setattr, instr, 'op', 100)
        self.assertRaises(AttributeError, setattr, instr, 'arg', 5)
        self.assertRaises(AttributeError, setattr, instr, 'lineno', 12)
        self.assertRaises(AttributeError, setattr, instr, 'size', 3)

    def test_size(self):
        self.assertEqual(ConcreteInstr('ROT_TWO').size, 1)
        self.assertEqual(ConcreteInstr('LOAD_CONST', 3).size, 3)
        self.assertEqual(ConcreteInstr('LOAD_CONST', 0x1234abcd).size, 6)

    def test_disassemble(self):
        instr = ConcreteInstr.disassemble(1, b'\td\x03\x00', 0)
        self.assertEqual(instr, ConcreteInstr("NOP", lineno=1))

        instr = ConcreteInstr.disassemble(1, b'\td\x03\x00', 1)
        self.assertEqual(instr, ConcreteInstr("LOAD_CONST", 3, lineno=1))

        code = b'\x904\x12d\xcd\xab'
        instr = ConcreteInstr.disassemble(1, code, 0)
        self.assertEqual(instr, ConcreteInstr('EXTENDED_ARG', 0x1234, lineno=1))

    def test_assemble(self):
        instr = ConcreteInstr("NOP")
        self.assertEqual(instr.assemble(), b'\t')

        instr = ConcreteInstr("LOAD_CONST", 3)
        self.assertEqual(instr.assemble(), b'd\x03\x00')

        instr = ConcreteInstr("LOAD_CONST", 0x1234abcd)
        self.assertEqual(instr.assemble(), b'\x904\x12d\xcd\xab')

    def test_get_jump_target(self):
        jump_abs = ConcreteInstr("JUMP_ABSOLUTE", 3)
        self.assertEqual(jump_abs.get_jump_target(100), 3)

        jump_forward = ConcreteInstr("JUMP_FORWARD", 5)
        self.assertEqual(jump_forward.get_jump_target(10), 18)


class ConcreteBytecodeTests(TestCase):
    def test_attr(self):
        code_obj = get_code("x = 5")
        code = ConcreteBytecode.from_code(code_obj)
        self.assertEqual(code.consts, [5, None])
        self.assertEqual(code.names, ['x'])
        self.assertEqual(code.varnames, [])
        self.assertListEqual(list(code),
                             [ConcreteInstr('LOAD_CONST', 0, lineno=1),
                              ConcreteInstr('STORE_NAME', 0, lineno=1),
                              ConcreteInstr('LOAD_CONST', 1, lineno=1),
                              ConcreteInstr('RETURN_VALUE', lineno=1)])
        # FIXME: test other attributes

    def test_to_code_lnotab(self):
        # x = 7
        # y = 8
        # z = 9
        code = ConcreteBytecode()
        code.consts = [7, 8, 9]
        code.names = ['x', 'y', 'z']
        code.extend([ConcreteInstr("LOAD_CONST", 0, lineno=1),
                     ConcreteInstr("STORE_NAME", 0, lineno=1),
                     ConcreteInstr("LOAD_CONST", 1, lineno=2),
                     ConcreteInstr("STORE_NAME", 1, lineno=2),
                     ConcreteInstr("LOAD_CONST", 2, lineno=3),
                     ConcreteInstr("STORE_NAME", 2, lineno=3)])

        code_obj = code.to_code()
        expected = (b'd\x00\x00'
                    b'Z\x00\x00'
                    b'd\x01\x00'
                    b'Z\x01\x00'
                    b'd\x02\x00'
                    b'Z\x02\x00')
        self.assertEqual(code_obj.co_code, expected)
        self.assertEqual(code_obj.co_lnotab, b'\x06\x01\x06\x01')


class ConcreteFromCodeTests(TestCase):
    def test_extended_arg(self):
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

    def test_extended_arg_make_function(self):
        code_obj = get_code('''
            def foo(x: int, y: int):
                pass
        ''')

        # without EXTENDED_ARG
        concrete = ConcreteBytecode.from_code(code_obj)
        func_code = concrete.consts[1]
        self.assertEqual(concrete.names, ['int', 'foo'])
        self.assertEqual(concrete.consts, [('x', 'y'), func_code, 'foo', None])
        self.assertListEqual(list(concrete),
                         [ConcreteInstr("LOAD_NAME", 0, lineno=1),
                          ConcreteInstr("LOAD_NAME", 0, lineno=1),
                          ConcreteInstr("LOAD_CONST", 0, lineno=1),
                          ConcreteInstr("LOAD_CONST", 1, lineno=1),
                          ConcreteInstr("LOAD_CONST", 2, lineno=1),
                          ConcreteInstr("MAKE_FUNCTION", 3 << 16, lineno=1),
                          ConcreteInstr("STORE_NAME", 1, lineno=1),
                          ConcreteInstr("LOAD_CONST", 3, lineno=1),
                          ConcreteInstr("RETURN_VALUE", lineno=1)])

        # with EXTENDED_ARG
        concrete = ConcreteBytecode.from_code(code_obj, extended_arg_op=True)
        func_code = concrete.consts[1]
        self.assertEqual(concrete.names, ['int', 'foo'])
        self.assertEqual(concrete.consts, [('x', 'y'), func_code, 'foo', None])
        self.assertListEqual(list(concrete),
                         [ConcreteInstr("LOAD_NAME", 0, lineno=1),
                          ConcreteInstr("LOAD_NAME", 0, lineno=1),
                          ConcreteInstr("LOAD_CONST", 0, lineno=1),
                          ConcreteInstr("LOAD_CONST", 1, lineno=1),
                          ConcreteInstr("LOAD_CONST", 2, lineno=1),
                          ConcreteInstr("EXTENDED_ARG", 3, lineno=1),
                          ConcreteInstr("MAKE_FUNCTION", 0, lineno=1),
                          ConcreteInstr("STORE_NAME", 1, lineno=1),
                          ConcreteInstr("LOAD_CONST", 3, lineno=1),
                          ConcreteInstr("RETURN_VALUE", lineno=1)])


class BytecodeToConcreteTests(TestCase):
    def test_label(self):
        code = Bytecode()
        label = Label()
        code.extend([Instr('LOAD_CONST', 'hello', lineno=1),
                     Instr('JUMP_FORWARD', label, lineno=1),
                     label,
                         Instr('POP_TOP', lineno=1)])

        code = code.to_concrete_bytecode()
        expected = [ConcreteInstr('LOAD_CONST', 0, lineno=1),
                    ConcreteInstr('JUMP_FORWARD', 0, lineno=1),
                    ConcreteInstr('POP_TOP', lineno=1)]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, ['hello'])

    def test_setlineno(self):
        # x = 7
        # y = 8
        # z = 9
        code = Bytecode()
        code.extend([Instr("LOAD_CONST", 7),
                     Instr("STORE_NAME", 'x'),
                     SetLineno(2),
                     Instr("LOAD_CONST", 8),
                     Instr("STORE_NAME", 'y'),
                     SetLineno(3),
                     Instr("LOAD_CONST", 9),
                     Instr("STORE_NAME", 'z')])

        concrete = code.to_concrete_bytecode()
        self.assertEqual(concrete.consts, [7, 8, 9])
        self.assertEqual(concrete.names, ['x', 'y', 'z'])
        code.extend([ConcreteInstr("LOAD_CONST", 0, lineno=1),
                     ConcreteInstr("STORE_NAME", 0, lineno=1),
                     ConcreteInstr("LOAD_CONST", 1, lineno=2),
                     ConcreteInstr("STORE_NAME", 1, lineno=2),
                     ConcreteInstr("LOAD_CONST", 2, lineno=3),
                     ConcreteInstr("STORE_NAME", 2, lineno=3)])



    def test_simple(self):
        bytecode = Bytecode()
        label = Label()
        bytecode.extend([Instr('LOAD_NAME', 'test', lineno=1),
                         Instr('POP_JUMP_IF_FALSE', label),
                         Instr('LOAD_CONST', 5, lineno=2),
                         Instr('STORE_NAME', 'x'),
                         Instr('JUMP_FORWARD', label),
                         Instr('LOAD_CONST', 7, lineno=4),
                         Instr('STORE_NAME', 'x'),
                         label,
                             Instr('LOAD_CONST', None),
                             Instr('RETURN_VALUE')])

        concrete = bytecode.to_concrete_bytecode()
        expected = [ConcreteInstr('LOAD_NAME', 0, lineno=1),
                    ConcreteInstr('POP_JUMP_IF_FALSE', 21, lineno=1),
                    ConcreteInstr('LOAD_CONST', 0, lineno=2),
                    ConcreteInstr('STORE_NAME', 1, lineno=2),
                    ConcreteInstr('JUMP_FORWARD', 6, lineno=2),
                    ConcreteInstr('LOAD_CONST', 1, lineno=4),
                    ConcreteInstr('STORE_NAME', 1, lineno=4),
                    ConcreteInstr('LOAD_CONST', 2, lineno=4),
                    ConcreteInstr('RETURN_VALUE', lineno=4)]
        self.assertListEqual(list(concrete), expected)
        self.assertListEqual(concrete.consts, [5, 7, None])
        self.assertListEqual(concrete.names, ['test', 'x'])
        self.assertListEqual(concrete.varnames, [])

    def test_jumps(self):
        # if test:
        #     x = 12
        # else:
        #     x = 37
        code = Bytecode()
        label_else = Label()
        label_return = Label()
        code.extend([Instr('LOAD_NAME', 'test', lineno=1),
                     Instr('POP_JUMP_IF_FALSE', label_else),
                     Instr('LOAD_CONST', 12, lineno=2),
                     Instr('STORE_NAME', 'x'),
                     Instr('JUMP_FORWARD', label_return),
                     label_else,
                         Instr('LOAD_CONST', 37, lineno=4),
                         Instr('STORE_NAME', 'x'),
                     label_return,
                         Instr('LOAD_CONST', None, lineno=4),
                         Instr('RETURN_VALUE')])

        code = code.to_concrete_bytecode()
        expected = [ConcreteInstr('LOAD_NAME', 0, lineno=1),
                    ConcreteInstr('POP_JUMP_IF_FALSE', 15, lineno=1),
                    ConcreteInstr('LOAD_CONST', 0, lineno=2),
                    ConcreteInstr('STORE_NAME', 1, lineno=2),
                    ConcreteInstr('JUMP_FORWARD', 6, lineno=2),
                    ConcreteInstr('LOAD_CONST', 1, lineno=4),
                    ConcreteInstr('STORE_NAME', 1, lineno=4),
                    ConcreteInstr('LOAD_CONST', 2, lineno=4),
                    ConcreteInstr('RETURN_VALUE', lineno=4)]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, [12, 37, None])
        self.assertListEqual(code.names, ['test', 'x'])
        self.assertListEqual(code.varnames, [])

    def test_dont_merge_constants(self):
        # test two constants which are equal but have a different type
        code = Bytecode()
        code.extend([Instr('LOAD_CONST', 5, lineno=1),
                     Instr('LOAD_CONST', 5.0, lineno=1)])
                     # FIXME: float -0.0, +0.0
                     # FIXME: complex
                     # FIXME: tuple, nested tuple
                     # FIXME: frozenset, nested frozenset

        code = code.to_concrete_bytecode()
        expected = [ConcreteInstr('LOAD_CONST', 0, lineno=1),
                    ConcreteInstr('LOAD_CONST', 1, lineno=1)]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, [5, 5.0])


if __name__ == "__main__":
    unittest.main()

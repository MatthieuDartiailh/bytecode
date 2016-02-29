#!/usr/bin/env python3
import opcode
import types
import unittest
from bytecode import (UNSET, Label, Instr, SetLineno, Bytecode,
                      ConcreteInstr, ConcreteBytecode)
from bytecode.concrete import ARG_MAX
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
        with self.assertRaises(TypeError):
            ConcreteInstr("LOAD_CONST", 5, lineno=1.0)
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", 5, lineno=-1)

        # test maximum argument
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", ARG_MAX + 1)
        instr = ConcreteInstr("LOAD_CONST", ARG_MAX)
        self.assertEqual(instr.arg, ARG_MAX)

    def test_attr(self):
        instr = ConcreteInstr("LOAD_CONST", 5, lineno=12)
        self.assertEqual(instr.name, 'LOAD_CONST')
        self.assertEqual(instr.op, 100)
        self.assertEqual(instr.arg, 5)
        self.assertEqual(instr.lineno, 12)
        self.assertEqual(instr.size, 3)

    def test_set(self):
        instr = ConcreteInstr('LOAD_CONST', 5, lineno=3)

        instr.set('NOP')
        self.assertEqual(instr.name, 'NOP')
        self.assertIs(instr.arg, UNSET)
        self.assertIsNone(instr.lineno)

        instr.set('LOAD_FAST', 8, lineno=9)
        self.assertEqual(instr.name, 'LOAD_FAST')
        self.assertEqual(instr.arg, 8)
        self.assertEqual(instr.lineno, 9)

        # invalid
        with self.assertRaises(ValueError):
            instr.set('LOAD_CONST')
        with self.assertRaises(ValueError):
            instr.set('NOP', 5)
        with self.assertRaises(ValueError):
            instr.set('LOAD_CONST', 5, lineno=-1)

    def test_set_attr(self):
        instr = ConcreteInstr("LOAD_CONST", 5, lineno=12)

        # operator name
        instr.name = 'LOAD_FAST'
        self.assertEqual(instr.name, 'LOAD_FAST')
        self.assertEqual(instr.op, 124)
        self.assertRaises(TypeError, setattr, instr, 'name', 3)
        self.assertRaises(ValueError, setattr, instr, 'name', 'xxx')

        # operator code
        instr.op = 100
        self.assertEqual(instr.name, 'LOAD_CONST')
        self.assertEqual(instr.op, 100)
        self.assertRaises(ValueError, setattr, instr, 'op', -12)
        self.assertRaises(TypeError, setattr, instr, 'op', 'abc')

        # extended argument
        instr.arg = 0x1234abcd
        self.assertEqual(instr.arg, 0x1234abcd)
        self.assertEqual(instr.size, 6)

        # small argument
        instr.arg = 0
        self.assertEqual(instr.arg, 0)
        self.assertEqual(instr.size, 3)

        # invalid argument
        self.assertRaises(ValueError, setattr, instr, 'arg', -1)
        self.assertRaises(ValueError, setattr, instr, 'arg', ARG_MAX + 1)

        # size attribute is read-only
        self.assertRaises(AttributeError, setattr, instr, 'size', 3)

        # lineno
        instr.lineno = 33
        self.assertEqual(instr.lineno, 33)
        self.assertRaises(TypeError, setattr, instr, 'lineno', 1.0)
        self.assertRaises(ValueError, setattr, instr, 'lineno', -1)

    def test_size(self):
        self.assertEqual(ConcreteInstr('ROT_TWO').size, 1)
        self.assertEqual(ConcreteInstr('LOAD_CONST', 3).size, 3)
        self.assertEqual(ConcreteInstr('LOAD_CONST', 0x1234abcd).size, 6)

    def test_disassemble(self):
        instr = ConcreteInstr.disassemble(1, b'\td\x03\x00', 0)
        self.assertEqual(instr, ConcreteInstr("NOP", lineno=1))

        instr = ConcreteInstr.disassemble(2, b'\td\x03\x00', 1)
        self.assertEqual(instr, ConcreteInstr("LOAD_CONST", 3, lineno=2))

        code = b'\x904\x12d\xcd\xab'
        instr = ConcreteInstr.disassemble(3, code, 0)
        self.assertEqual(instr,
                         ConcreteInstr('EXTENDED_ARG', 0x1234, lineno=3))

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
        self.assertEqual(code.freevars, [])
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

    def test_to_bytecode_consts(self):
        # x = -0.0
        # x = +0.0
        #
        # code optimized by the CPython 3.6 peephole optimizer which emits
        # duplicated constants (0.0 is twice in consts).
        code = ConcreteBytecode()
        code.consts = [0.0, None, -0.0, 0.0]
        code.names = ['x', 'y']
        code.extend([ConcreteInstr('LOAD_CONST', 2, lineno=1),
                     ConcreteInstr('STORE_NAME', 0, lineno=1),
                     ConcreteInstr('LOAD_CONST', 3, lineno=2),
                     ConcreteInstr('STORE_NAME', 1, lineno=2),
                     ConcreteInstr('LOAD_CONST', 1, lineno=2),
                     ConcreteInstr('RETURN_VALUE', lineno=2)])

        code = code.to_bytecode().to_concrete_bytecode()
        # the conversion changes the constant order: the order comes from
        # the order of LOAD_CONST instructions
        self.assertEqual(code.consts, [-0.0, 0.0, None])
        code.names = ['x', 'y']
        self.assertListEqual(list(code),
                             [ConcreteInstr('LOAD_CONST', 0, lineno=1),
                              ConcreteInstr('STORE_NAME', 0, lineno=1),
                              ConcreteInstr('LOAD_CONST', 1, lineno=2),
                              ConcreteInstr('STORE_NAME', 1, lineno=2),
                              ConcreteInstr('LOAD_CONST', 2, lineno=2),
                              ConcreteInstr('RETURN_VALUE', lineno=2)])

    def test_cellvar(self):
        concrete = ConcreteBytecode()
        concrete.cellvars = ['x']
        concrete.append(ConcreteInstr('LOAD_DEREF', 0))
        code = concrete.to_code()

        concrete = ConcreteBytecode.from_code(code)
        self.assertEqual(concrete.cellvars, ['x'])
        self.assertEqual(concrete.freevars, [])
        self.assertEqual(list(concrete),
                         [ConcreteInstr('LOAD_DEREF', 0, lineno=1)])

        bytecode = concrete.to_bytecode()
        self.assertEqual(bytecode.cellvars, ['x'])
        self.assertEqual(list(bytecode),
                         [Instr('LOAD_DEREF', 'x', lineno=1)])

    def test_freevar(self):
        concrete = ConcreteBytecode()
        concrete.freevars = ['x']
        concrete.append(ConcreteInstr('LOAD_DEREF', 0))
        code = concrete.to_code()

        concrete = ConcreteBytecode.from_code(code)
        self.assertEqual(concrete.cellvars, [])
        self.assertEqual(concrete.freevars, ['x'])
        self.assertEqual(list(concrete),
                         [ConcreteInstr('LOAD_DEREF', 0, lineno=1)])

        bytecode = concrete.to_bytecode()
        self.assertEqual(bytecode.cellvars, [])
        self.assertEqual(list(bytecode),
                         [Instr('LOAD_DEREF', 'x', lineno=1)])

    def test_cellvar_freevar(self):
        concrete = ConcreteBytecode()
        concrete.cellvars = ['cell']
        concrete.freevars = ['free']
        concrete.append(ConcreteInstr('LOAD_DEREF', 0))
        concrete.append(ConcreteInstr('LOAD_DEREF', 1))
        code = concrete.to_code()

        concrete = ConcreteBytecode.from_code(code)
        self.assertEqual(concrete.cellvars, ['cell'])
        self.assertEqual(concrete.freevars, ['free'])
        self.assertEqual(list(concrete),
                         [ConcreteInstr('LOAD_DEREF', 0, lineno=1),
                          ConcreteInstr('LOAD_DEREF', 1, lineno=1)])

        bytecode = concrete.to_bytecode()
        self.assertEqual(bytecode.cellvars, ['cell'])
        self.assertEqual(list(bytecode),
                         [Instr('LOAD_DEREF', 'cell', lineno=1),
                          Instr('LOAD_DEREF', 'free', lineno=1)])


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
        bytecode = ConcreteBytecode.from_code(code, extended_arg=True)
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
        concrete = ConcreteBytecode.from_code(code_obj, extended_arg=True)
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

    def test_label2(self):
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

    def test_extended_jump(self):
        NOP = bytes((opcode.opmap['NOP'],))

        class BigInstr(ConcreteInstr):
            def __init__(self, size):
                super().__init__('NOP')
                self._size = size

            def copy(self):
                return self

            def assemble(self):
                return NOP * self._size

        # (invalid) code using jumps > 0xffff to test extended arg
        label = Label()
        nb_nop = 2**16
        code = Bytecode([Instr("JUMP_ABSOLUTE", label),
                         BigInstr(nb_nop),
                         label])

        code_obj = code.to_code()
        expected = (b'\x90\x01\x00q\x06\x00' + NOP * nb_nop)
        self.assertEqual(code_obj.co_code, expected)

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
                     Instr('LOAD_CONST', 5.0, lineno=1),
                     Instr('LOAD_CONST', -0.0, lineno=1),
                     Instr('LOAD_CONST', +0.0, lineno=1)])

        code = code.to_concrete_bytecode()
        expected = [ConcreteInstr('LOAD_CONST', 0, lineno=1),
                    ConcreteInstr('LOAD_CONST', 1, lineno=1),
                    ConcreteInstr('LOAD_CONST', 2, lineno=1),
                    ConcreteInstr('LOAD_CONST', 3, lineno=1)]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, [5, 5.0, -0.0, +0.0])

    def test_cellvars(self):
        code = Bytecode()
        code.cellvars = ['x']
        code.freevars = ['y']
        code.extend([Instr('LOAD_DEREF', 'x', lineno=1),
                     Instr('LOAD_DEREF', 'y', lineno=1)])
        concrete = code.to_concrete_bytecode()
        self.assertEqual(concrete.cellvars, ['x'])
        self.assertEqual(concrete.freevars, ['y'])
        code.extend([ConcreteInstr("LOAD_DEREF", 0, lineno=1),
                     ConcreteInstr("LOAD_DEREF", 1, lineno=1)])


if __name__ == "__main__":
    unittest.main()

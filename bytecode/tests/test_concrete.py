#!/usr/bin/env python3
import opcode
import sys
import types
import unittest
import textwrap
from bytecode import (UNSET, Label, Instr, SetLineno, Bytecode,
                      CellVar, FreeVar,
                      ConcreteInstr, ConcreteBytecode)
from bytecode.tests import get_code, TestCase, WORDCODE


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
            ConcreteInstr("LOAD_CONST", 2147483647 + 1)
        instr = ConcreteInstr("LOAD_CONST", 2147483647)
        self.assertEqual(instr.arg, 2147483647)

        # test meaningless extended args
        instr = ConcreteInstr('LOAD_FAST', 8, lineno=3, extended_args=1)
        self.assertEqual(instr.name, 'LOAD_FAST')
        self.assertEqual(instr.arg, 8)
        self.assertEqual(instr.lineno, 3)
        self.assertEqual(instr.size, 4)

    def test_attr(self):
        instr = ConcreteInstr("LOAD_CONST", 5, lineno=12)
        self.assertEqual(instr.name, 'LOAD_CONST')
        self.assertEqual(instr.opcode, 100)
        self.assertEqual(instr.arg, 5)
        self.assertEqual(instr.lineno, 12)
        self.assertEqual(instr.size, 2 if WORDCODE else 3)

    def test_set(self):
        instr = ConcreteInstr('LOAD_CONST', 5, lineno=3)

        instr.set('NOP')
        self.assertEqual(instr.name, 'NOP')
        self.assertIs(instr.arg, UNSET)
        self.assertEqual(instr.lineno, 3)

        instr.set('LOAD_FAST', 8)
        self.assertEqual(instr.name, 'LOAD_FAST')
        self.assertEqual(instr.arg, 8)
        self.assertEqual(instr.lineno, 3)

        # invalid
        with self.assertRaises(ValueError):
            instr.set('LOAD_CONST')
        with self.assertRaises(ValueError):
            instr.set('NOP', 5)

    def test_set_attr(self):
        instr = ConcreteInstr("LOAD_CONST", 5, lineno=12)

        # operator name
        instr.name = 'LOAD_FAST'
        self.assertEqual(instr.name, 'LOAD_FAST')
        self.assertEqual(instr.opcode, 124)
        self.assertRaises(TypeError, setattr, instr, 'name', 3)
        self.assertRaises(ValueError, setattr, instr, 'name', 'xxx')

        # operator code
        instr.opcode = 100
        self.assertEqual(instr.name, 'LOAD_CONST')
        self.assertEqual(instr.opcode, 100)
        self.assertRaises(ValueError, setattr, instr, 'opcode', -12)
        self.assertRaises(TypeError, setattr, instr, 'opcode', 'abc')

        # extended argument
        instr.arg = 0x1234abcd
        self.assertEqual(instr.arg, 0x1234abcd)
        self.assertEqual(instr.size, 8 if WORDCODE else 6)

        # small argument
        instr.arg = 0
        self.assertEqual(instr.arg, 0)
        self.assertEqual(instr.size, 2 if WORDCODE else 3)

        # invalid argument
        self.assertRaises(ValueError, setattr, instr, 'arg', -1)
        self.assertRaises(ValueError, setattr, instr, 'arg', 2147483647 + 1)

        # size attribute is read-only
        self.assertRaises(AttributeError, setattr, instr, 'size', 3)

        # lineno
        instr.lineno = 33
        self.assertEqual(instr.lineno, 33)
        self.assertRaises(TypeError, setattr, instr, 'lineno', 1.0)
        self.assertRaises(ValueError, setattr, instr, 'lineno', -1)

    def test_size(self):
        self.assertEqual(ConcreteInstr('ROT_TWO').size, 2 if WORDCODE else 1)
        self.assertEqual(ConcreteInstr('LOAD_CONST', 3).size,
                         2 if WORDCODE else 3)
        self.assertEqual(ConcreteInstr(
            'LOAD_CONST', 0x1234abcd).size, 8 if WORDCODE else 6)

    def test_disassemble(self):
        code = b'\t\x00d\x03' if WORDCODE else b'\td\x03\x00'
        instr = ConcreteInstr.disassemble(1, code, 0)
        self.assertEqual(instr, ConcreteInstr("NOP", lineno=1))

        instr = ConcreteInstr.disassemble(2, code, 2 if WORDCODE else 1)
        self.assertEqual(instr, ConcreteInstr("LOAD_CONST", 3, lineno=2))

        code = (b'\x90\x12\x904\x90\xabd\xcd' if WORDCODE else
                b'\x904\x12d\xcd\xab')

        instr = ConcreteInstr.disassemble(3, code, 0)
        self.assertEqual(instr,
                         ConcreteInstr('EXTENDED_ARG',
                                       0x12 if WORDCODE else 0x1234, lineno=3))

    def test_assemble(self):
        instr = ConcreteInstr("NOP")
        self.assertEqual(instr.assemble(), b'\t\x00' if WORDCODE else b'\t')

        instr = ConcreteInstr("LOAD_CONST", 3)
        self.assertEqual(instr.assemble(),
                         b'd\x03' if WORDCODE else b'd\x03\x00')

        instr = ConcreteInstr("LOAD_CONST", 0x1234abcd)
        self.assertEqual(instr.assemble(),
                         (b'\x90\x12\x904\x90\xabd\xcd' if WORDCODE else
                          b'\x904\x12d\xcd\xab'))

        instr = ConcreteInstr("LOAD_CONST", 3, extended_args=1)
        self.assertEqual(instr.assemble(),
                         (b'\x90\x00d\x03' if WORDCODE else
                          b'\x90\x00\x00d\x03\x00'))

    def test_get_jump_target(self):
        jump_abs = ConcreteInstr("JUMP_ABSOLUTE", 3)
        self.assertEqual(jump_abs.get_jump_target(100), 3)

        jump_forward = ConcreteInstr("JUMP_FORWARD", 5)
        self.assertEqual(jump_forward.get_jump_target(10),
                         17 if WORDCODE else 18)


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

    def test_invalid_types(self):
        code = ConcreteBytecode()
        code.append(Label())
        with self.assertRaises(ValueError):
            list(code)
        with self.assertRaises(ValueError):
            code.legalize()
        with self.assertRaises(ValueError):
            ConcreteBytecode([Label()])

    def test_to_code_lnotab(self):
        # x = 7
        # y = 8
        # z = 9
        concrete = ConcreteBytecode()
        concrete.consts = [7, 8, 9]
        concrete.names = ['x', 'y', 'z']
        concrete.first_lineno = 3
        concrete.extend([ConcreteInstr("LOAD_CONST", 0),
                         ConcreteInstr("STORE_NAME", 0),
                         SetLineno(4),
                         ConcreteInstr("LOAD_CONST", 1),
                         ConcreteInstr("STORE_NAME", 1),
                         SetLineno(5),
                         ConcreteInstr("LOAD_CONST", 2),
                         ConcreteInstr("STORE_NAME", 2)])

        code = concrete.to_code()
        if WORDCODE:
            expected = b'd\x00Z\x00d\x01Z\x01d\x02Z\x02'
        else:
            expected = (b'd\x00\x00'
                        b'Z\x00\x00'
                        b'd\x01\x00'
                        b'Z\x01\x00'
                        b'd\x02\x00'
                        b'Z\x02\x00')
        self.assertEqual(code.co_code, expected)
        self.assertEqual(code.co_firstlineno, 3)
        self.assertEqual(
            code.co_lnotab,
            b'\x04\x01\x04\x01' if WORDCODE else b'\x06\x01\x06\x01')

    def test_negative_lnotab(self):
        # x = 7
        # y = 8
        concrete = ConcreteBytecode([
            ConcreteInstr("LOAD_CONST", 0),
            ConcreteInstr("STORE_NAME", 0),
            # line number goes backward!
            SetLineno(2),
            ConcreteInstr("LOAD_CONST", 1),
            ConcreteInstr("STORE_NAME", 1)
        ])
        concrete.consts = [7, 8]
        concrete.names = ['x', 'y']
        concrete.first_lineno = 5

        if sys.version_info >= (3, 6):
            code = concrete.to_code()
            expected = b'd\x00Z\x00d\x01Z\x01'
            self.assertEqual(code.co_code, expected)
            self.assertEqual(code.co_firstlineno, 5)
            self.assertEqual(code.co_lnotab, b'\x04\xfd')
        else:
            with self.assertRaises(ValueError) as cm:
                code = concrete.to_code()
            self.assertEqual(str(cm.exception),
                             "negative line number delta is not supported "
                             "on Python < 3.6")

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
                         [Instr('LOAD_DEREF', CellVar('x'), lineno=1)])

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
                         [Instr('LOAD_DEREF', FreeVar('x'), lineno=1)])

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
                         [Instr('LOAD_DEREF', CellVar('cell'), lineno=1),
                          Instr('LOAD_DEREF', FreeVar('free'), lineno=1)])

    def test_load_classderef(self):
        concrete = ConcreteBytecode()
        concrete.cellvars = ['__class__']
        concrete.freevars = ['__class__']
        concrete.extend([ConcreteInstr('LOAD_CLASSDEREF', 1),
                         ConcreteInstr('STORE_DEREF', 1)])

        bytecode = concrete.to_bytecode()
        self.assertEqual(bytecode.freevars, ['__class__'])
        self.assertEqual(bytecode.cellvars, ['__class__'])
        self.assertEqual(list(bytecode),
                         [Instr('LOAD_CLASSDEREF', FreeVar('__class__'),
                                lineno=1),
                          Instr('STORE_DEREF', FreeVar('__class__'), lineno=1)]
                         )

        concrete = bytecode.to_concrete_bytecode()
        self.assertEqual(concrete.freevars, ['__class__'])
        self.assertEqual(concrete.cellvars, ['__class__'])
        self.assertEqual(list(concrete),
                         [ConcreteInstr('LOAD_CLASSDEREF', 1, lineno=1),
                          ConcreteInstr('STORE_DEREF', 1, lineno=1)])

        code = concrete.to_code()
        self.assertEqual(code.co_freevars, ('__class__',))
        self.assertEqual(code.co_cellvars, ('__class__',))
        self.assertEqual(
            code.co_code,
            b'\x94\x01\x89\x01' if WORDCODE else b'\x94\x01\x00\x89\x01\x00')

    def test_explicit_stacksize(self):
        # Passing stacksize=... to ConcreteBytecode.to_code should result in a
        # code object with the specified stacksize.  We pass some silly values
        # and assert that they are honored.
        code_obj = get_code("print('%s' % (a,b,c))")
        original_stacksize = code_obj.co_stacksize
        concrete = ConcreteBytecode.from_code(code_obj)

        # First with something bigger than necessary.
        explicit_stacksize = original_stacksize + 42
        new_code_obj = concrete.to_code(stacksize=explicit_stacksize)
        self.assertEqual(new_code_obj.co_stacksize, explicit_stacksize)

        # Then with something bogus.  We probably don't want to advertise this
        # in the documentation.  If this fails then decide if it's for good
        # reason, and remove if so.
        explicit_stacksize = 0
        new_code_obj = concrete.to_code(stacksize=explicit_stacksize)
        self.assertEqual(new_code_obj.co_stacksize, explicit_stacksize)

    def test_legalize(self):
        concrete = ConcreteBytecode()
        concrete.first_lineno = 3
        concrete.consts = [7, 8, 9]
        concrete.names = ['x', 'y', 'z']
        concrete.extend([ConcreteInstr("LOAD_CONST", 0),
                         ConcreteInstr("STORE_NAME", 0),
                         ConcreteInstr("LOAD_CONST", 1, lineno=4),
                         ConcreteInstr("STORE_NAME", 1),
                         SetLineno(5),
                         ConcreteInstr("LOAD_CONST", 2, lineno=6),
                         ConcreteInstr("STORE_NAME", 2)])

        concrete.legalize()
        self.assertListEqual(list(concrete), [ConcreteInstr("LOAD_CONST", 0, lineno=3),
                                              ConcreteInstr("STORE_NAME", 0, lineno=3),
                                              ConcreteInstr("LOAD_CONST", 1, lineno=4),
                                              ConcreteInstr("STORE_NAME", 1, lineno=4),
                                              ConcreteInstr("LOAD_CONST", 2, lineno=5),
                                              ConcreteInstr("STORE_NAME", 2, lineno=5)])

    def test_slice(self):
        concrete = ConcreteBytecode()
        concrete.first_lineno = 3
        concrete.consts = [7, 8, 9]
        concrete.names = ['x', 'y', 'z']
        concrete.extend([ConcreteInstr("LOAD_CONST", 0),
                         ConcreteInstr("STORE_NAME", 0),
                         SetLineno(4),
                         ConcreteInstr("LOAD_CONST", 1),
                         ConcreteInstr("STORE_NAME", 1),
                         SetLineno(5),
                         ConcreteInstr("LOAD_CONST", 2),
                         ConcreteInstr("STORE_NAME", 2)])
        self.assertEqual(concrete, concrete[:])

    def test_copy(self):
        concrete = ConcreteBytecode()
        concrete.first_lineno = 3
        concrete.consts = [7, 8, 9]
        concrete.names = ['x', 'y', 'z']
        concrete.extend([ConcreteInstr("LOAD_CONST", 0),
                         ConcreteInstr("STORE_NAME", 0),
                         SetLineno(4),
                         ConcreteInstr("LOAD_CONST", 1),
                         ConcreteInstr("STORE_NAME", 1),
                         SetLineno(5),
                         ConcreteInstr("LOAD_CONST", 2),
                         ConcreteInstr("STORE_NAME", 2)])
        self.assertEqual(concrete, concrete.copy())

    def test_offset_index(self):
        concrete = ConcreteBytecode()
        concrete[:] = [
            ConcreteInstr('LOAD_FAST', 0),
            ConcreteInstr('LOAD_FAST', 1),
            SetLineno(2),
            ConcreteInstr('BINARY_ADD'),
            ConcreteInstr('RETURN_VALUE')
        ]
        # simple cases
        self.assertEqual(concrete.index_at_code_offset(0), 0)
        self.assertEqual(concrete.instr_at_code_offset(0), concrete[0])
        self.assertEqual(concrete.index_at_code_offset(3), 1)
        self.assertEqual(concrete.instr_at_code_offset(3), concrete[1])
        self.assertEqual(concrete.index_at_code_offset(7), 4)
        self.assertEqual(concrete.instr_at_code_offset(7), concrete[4])

        # these indices are deliberately different
        # the index returns the lower bound, the SetLineno
        # the instruction returns the actual instruction
        self.assertEqual(concrete.index_at_code_offset(6), 2)
        self.assertEqual(concrete.instr_at_code_offset(6), concrete[3])

        # asking for the index at the end is OK, but not the instruction
        self.assertEqual(concrete.index_at_code_offset(8), 5)
        self.assertRaisesRegex(IndexError, 'out of range', concrete.instr_at_code_offset, 8)

        # other disallowed things
        self.assertRaisesRegex(IndexError, 'within', concrete.instr_at_code_offset, 1)
        self.assertRaisesRegex(IndexError, 'within', concrete.instr_at_code_offset, 1)
        self.assertRaisesRegex(IndexError, 'within', concrete.index_at_code_offset, 5)
        self.assertRaisesRegex(IndexError, 'within', concrete.instr_at_code_offset, 5)
        self.assertRaisesRegex(IndexError, 'out of range', concrete.index_at_code_offset, -1)
        self.assertRaisesRegex(IndexError, 'out of range', concrete.instr_at_code_offset, -1)
        self.assertRaisesRegex(IndexError, 'out of range', concrete.index_at_code_offset, 9)
        self.assertRaisesRegex(IndexError, 'out of range', concrete.instr_at_code_offset, 9)


class ConcreteFromCodeTests(TestCase):

    def test_extended_arg(self):
        # Create a code object from arbitrary bytecode
        co_code = (b'\x90\x12\x904\x90\xabd\xcd' if WORDCODE else
                   b'\x904\x12d\xcd\xab')
        code = get_code('x=1')
        args = ((code.co_argcount,)
                if sys.version_info < (3, 8) else
                (code.co_argcount, code.co_posonlyargcount))
        args += (code.co_kwonlyargcount,
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

        code = types.CodeType(*args)

        # without EXTENDED_ARG opcode
        bytecode = ConcreteBytecode.from_code(code)
        self.assertListEqual(list(bytecode),
                             [ConcreteInstr("LOAD_CONST", 0x1234abcd,
                                            lineno=1)])

        # with EXTENDED_ARG opcode
        bytecode = ConcreteBytecode.from_code(code, extended_arg=True)
        if WORDCODE:
            expected = [ConcreteInstr('EXTENDED_ARG', 0x12, lineno=1),
                        ConcreteInstr('EXTENDED_ARG', 0x34, lineno=1),
                        ConcreteInstr('EXTENDED_ARG', 0xab, lineno=1),
                        ConcreteInstr('LOAD_CONST', 0xcd, lineno=1)]
        else:
            expected = [ConcreteInstr('EXTENDED_ARG', 0x1234, lineno=1),
                        ConcreteInstr('LOAD_CONST', 0xabcd, lineno=1)]
        self.assertListEqual(list(bytecode), expected)

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
        if WORDCODE:
            expected = [ConcreteInstr("LOAD_NAME", 0, lineno=1),
                        ConcreteInstr("LOAD_NAME", 0, lineno=1),
                        ConcreteInstr("LOAD_CONST", 0, lineno=1),
                        ConcreteInstr("BUILD_CONST_KEY_MAP", 2, lineno=1),
                        ConcreteInstr("LOAD_CONST", 1, lineno=1),
                        ConcreteInstr("LOAD_CONST", 2, lineno=1),
                        ConcreteInstr("MAKE_FUNCTION", 4, lineno=1),
                        ConcreteInstr("STORE_NAME", 1, lineno=1),
                        ConcreteInstr("LOAD_CONST", 3, lineno=1),
                        ConcreteInstr("RETURN_VALUE", lineno=1)]
        else:
            expected = [ConcreteInstr("LOAD_NAME", 0, lineno=1),
                        ConcreteInstr("LOAD_NAME", 0, lineno=1),
                        ConcreteInstr("LOAD_CONST", 0, lineno=1),
                        ConcreteInstr("LOAD_CONST", 1, lineno=1),
                        ConcreteInstr("LOAD_CONST", 2, lineno=1),
                        ConcreteInstr("MAKE_FUNCTION", 3 << 16, lineno=1),
                        ConcreteInstr("STORE_NAME", 1, lineno=1),
                        ConcreteInstr("LOAD_CONST", 3, lineno=1),
                        ConcreteInstr("RETURN_VALUE", lineno=1)]
        self.assertListEqual(list(concrete), expected)

        # with EXTENDED_ARG
        concrete = ConcreteBytecode.from_code(code_obj, extended_arg=True)
        func_code = concrete.consts[1]
        self.assertEqual(concrete.names, ['int', 'foo'])
        self.assertEqual(concrete.consts, [('x', 'y'), func_code, 'foo', None])
        if not WORDCODE:
            expected = [ConcreteInstr("LOAD_NAME", 0, lineno=1),
                        ConcreteInstr("LOAD_NAME", 0, lineno=1),
                        ConcreteInstr("LOAD_CONST", 0, lineno=1),
                        ConcreteInstr("LOAD_CONST", 1, lineno=1),
                        ConcreteInstr("LOAD_CONST", 2, lineno=1),
                        ConcreteInstr("EXTENDED_ARG", 3, lineno=1),
                        ConcreteInstr("MAKE_FUNCTION", 0, lineno=1),
                        ConcreteInstr("STORE_NAME", 1, lineno=1),
                        ConcreteInstr("LOAD_CONST", 3, lineno=1),
                        ConcreteInstr("RETURN_VALUE", lineno=1)]
        self.assertListEqual(list(concrete), expected)


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
                    ConcreteInstr('POP_JUMP_IF_FALSE',
                                  14 if WORDCODE else 21, lineno=1),
                    ConcreteInstr('LOAD_CONST', 0, lineno=2),
                    ConcreteInstr('STORE_NAME', 1, lineno=2),
                    ConcreteInstr('JUMP_FORWARD',
                                  4 if WORDCODE else 6, lineno=2),
                    ConcreteInstr('LOAD_CONST', 1, lineno=4),
                    ConcreteInstr('STORE_NAME', 1, lineno=4),
                    ConcreteInstr('LOAD_CONST', 2, lineno=4),
                    ConcreteInstr('RETURN_VALUE', lineno=4)]
        self.assertListEqual(list(concrete), expected)
        self.assertListEqual(concrete.consts, [5, 7, None])
        self.assertListEqual(concrete.names, ['test', 'x'])
        self.assertListEqual(concrete.varnames, [])

    def test_label3(self):
        """
        CPython generates useless EXTENDED_ARG 0 in some cases. We need to
        properly track them as otherwise we can end up with broken offset for
        jumps.
        """
        source = """
            def func(x):
                if x == 1:
                    return x + 0
                elif x == 2:
                    return x + 1
                elif x == 3:
                    return x + 2
                elif x == 4:
                    return x + 3
                elif x == 5:
                    return x + 4
                elif x == 6:
                    return x + 5
                elif x == 7:
                    return x + 6
                elif x == 8:
                    return x + 7
                elif x == 9:
                    return x + 8
                elif x == 10:
                    return x + 9
                elif x == 11:
                    return x + 10
                elif x == 12:
                    return x + 11
                elif x == 13:
                    return x + 12
                elif x == 14:
                    return x + 13
                elif x == 15:
                    return x + 14
                elif x == 16:
                    return x + 15
                elif x == 17:
                    return x + 16
                return -1
        """
        code = get_code(source, function=True)
        bcode = Bytecode.from_code(code)
        concrete = bcode.to_concrete_bytecode()
        self.assertIsInstance(concrete, ConcreteBytecode)

        # Ensure that we do not generate broken code
        loc = {}
        exec(textwrap.dedent(source), loc)
        func = loc['func']
        func.__code__ = bcode.to_code()
        for i, x in enumerate(range(1, 18)):
            self.assertEqual(func(x), x + i)
        self.assertEqual(func(18), -1)

        # Ensure that we properly round trip in such cases
        self.assertEqual(ConcreteBytecode.from_code(code).to_code().co_code,
                         code.co_code)

    def test_setlineno(self):
        # x = 7
        # y = 8
        # z = 9
        concrete = ConcreteBytecode()
        concrete.consts = [7, 8, 9]
        concrete.names = ['x', 'y', 'z']
        concrete.first_lineno = 3
        concrete.extend([ConcreteInstr("LOAD_CONST", 0),
                         ConcreteInstr("STORE_NAME", 0),
                         SetLineno(4),
                         ConcreteInstr("LOAD_CONST", 1),
                         ConcreteInstr("STORE_NAME", 1),
                         SetLineno(5),
                         ConcreteInstr("LOAD_CONST", 2),
                         ConcreteInstr("STORE_NAME", 2)])

        code = concrete.to_bytecode()
        self.assertEqual(code,
                         [Instr("LOAD_CONST", 7, lineno=3),
                          Instr("STORE_NAME", 'x', lineno=3),
                          Instr("LOAD_CONST", 8, lineno=4),
                          Instr("STORE_NAME", 'y', lineno=4),
                          Instr("LOAD_CONST", 9, lineno=5),
                          Instr("STORE_NAME", 'z', lineno=5)])

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
                         label,
                         Instr('LOAD_CONST', None),
                         Instr('RETURN_VALUE')])

        code_obj = code.to_code()
        if WORDCODE:
            expected = b'\x90\x01\x90\x00q\x06' + NOP * nb_nop + b'd\x00S\x00'
        else:
            expected = b'\x90\x01\x00q\x06\x00' + NOP * nb_nop + b'd\x00\x00S'
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
                    ConcreteInstr('POP_JUMP_IF_FALSE',
                                  10 if WORDCODE else 15, lineno=1),
                    ConcreteInstr('LOAD_CONST', 0, lineno=2),
                    ConcreteInstr('STORE_NAME', 1, lineno=2),
                    ConcreteInstr('JUMP_FORWARD',
                                  4 if WORDCODE else 6, lineno=2),
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
        code.extend([Instr('LOAD_DEREF', CellVar('x'), lineno=1),
                     Instr('LOAD_DEREF', FreeVar('y'), lineno=1)])
        concrete = code.to_concrete_bytecode()
        self.assertEqual(concrete.cellvars, ['x'])
        self.assertEqual(concrete.freevars, ['y'])
        code.extend([ConcreteInstr("LOAD_DEREF", 0, lineno=1),
                     ConcreteInstr("LOAD_DEREF", 1, lineno=1)])

    def test_compute_jumps_convergence(self):
        # Consider the following sequence of instructions:
        #
        #     JUMP_ABSOLUTE Label1
        #     JUMP_ABSOLUTE Label2
        #     ...126 instructions...
        #   Label1:                 Offset 254 on first pass, 256 second pass
        #     NOP
        #     ... many more instructions ...
        #   Label2:                 Offset > 256 on first pass
        #
        # On first pass of compute_jumps(), Label2 will be at address 254, so
        # that value encodes into the single byte arg of JUMP_ABSOLUTE.
        #
        # On second pass compute_jumps() the instr at Label1 will have offset
        # of 256 so will also be given an EXTENDED_ARG.
        #
        # Thus we need to make an additional pass.  This test only verifies
        # case where 2 passes is insufficient but three is enough.

        if not WORDCODE:
            # Could be done pre-WORDCODE, but that requires 2**16 bytes of
            # code.
            return

        # Create code from comment above.
        code = Bytecode()
        label1 = Label()
        label2 = Label()
        nop = 'UNARY_POSITIVE'   # don't use NOP, dis.stack_effect will raise
        code.append(Instr('JUMP_ABSOLUTE', label1))
        code.append(Instr('JUMP_ABSOLUTE', label2))
        for x in range(4, 254, 2):
            code.append(Instr(nop))
        code.append(label1)
        code.append(Instr(nop))
        for x in range(256, 300, 2):
            code.append(Instr(nop))
        code.append(label2)
        code.append(Instr(nop))

        # This should pass by default.
        code.to_code()

        # Try with max of two passes:  it should raise
        with self.assertRaises(RuntimeError):
            code.to_code(compute_jumps_passes=2)

    def test_extreme_compute_jumps_convergence(self):
        """Test of compute_jumps() requiring absurd number of passes.

        NOTE:  This test also serves to demonstrate that there is no worst
        case: the number of passes can be unlimited (or, actually, limited by
        the size of the provided code).

        This is an extension of test_compute_jumps_convergence.  Instead of
        two jumps, where the earlier gets extended after the latter, we
        instead generate a series of many jumps.  Each pass of compute_jumps()
        extends one more instruction, which in turn causes the one behind it
        to be extended on the next pass.
        """
        if not WORDCODE:
            return

        # N: the number of unextended instructions that can be squeezed into a
        # set of bytes adressable by the arg of an unextended instruction.
        # The answer is "128", but here's how we arrive at it (and it also
        # hints at how to make this work for pre-WORDCODE).
        max_unextended_offset = 1 << 8
        unextended_branch_instr_size = 2
        N = max_unextended_offset // unextended_branch_instr_size

        nop = 'UNARY_POSITIVE'   # don't use NOP, dis.stack_effect will raise

        # The number of jumps will be equal to the number of labels.  The
        # number of passes of compute_jumps() required will be one greater
        # than this.
        labels = [Label() for x in range(0, 3 * N)]

        code = Bytecode()
        code.extend(Instr('JUMP_FORWARD', labels[len(labels) - x - 1])
                    for x in range(0, len(labels)))
        end_of_jumps = len(code)
        code.extend(Instr(nop) for x in range(0, N))

        # Now insert the labels.  The first is N instructions (i.e. 256
        # bytes) after the last jump.  Then they proceed to earlier positions
        # 4 bytes at a time.  While the targets are in the range of the nop
        # instructions, 4 bytes is two instructions.  When the targets are in
        # the range of JUMP_FORWARD instructions we have to allow for the fact
        # that the instructions will have been extended to four bytes each, so
        # working backwards 4 bytes per label means just one instruction per
        # label.
        offset = end_of_jumps + N
        for l in range(0, len(labels)):
            code.insert(offset, labels[l])
            if offset <= end_of_jumps:
                offset -= 1
            else:
                offset -= 2

        code.insert(0, Instr("LOAD_CONST", 0))
        del end_of_jumps
        code.append(Instr('RETURN_VALUE'))

        code.to_code(compute_jumps_passes=(len(labels) + 1))

    def test_general_constants(self):
        """Test if general object could be linked as constants.

        """
        class CustomObject:
            pass

        class UnHashableCustomObject:
            __hash__ = None

        obj1 = [1, 2, 3]
        obj2 = {1, 2, 3}
        obj3 = CustomObject()
        obj4 = UnHashableCustomObject()
        code = Bytecode([Instr('LOAD_CONST', obj1, lineno=1),
                         Instr('LOAD_CONST', obj2, lineno=1),
                         Instr('LOAD_CONST', obj3, lineno=1),
                         Instr('LOAD_CONST', obj4, lineno=1),
                         Instr('BUILD_TUPLE', 4, lineno=1),
                         Instr('RETURN_VALUE', lineno=1)])
        self.assertEqual(code.to_code().co_consts,
                         (obj1, obj2, obj3, obj4))

        def f():
            return  # pragma: no cover

        f.__code__ = code.to_code()
        self.assertEqual(f(), (obj1, obj2, obj3, obj4))


if __name__ == "__main__":
    unittest.main()  # pragma: no cover

import bytecode
import contextlib
import io
import opcode
import sys
import textwrap
import types
import unittest
from bytecode import (
    Instr, ConcreteInstr, Label,
    Bytecode, BytecodeBlocks, ConcreteBytecode)
from test_utils import TestCase


def LOAD_CONST(arg):
    return Instr(1, 'LOAD_CONST', arg)

def STORE_NAME(arg):
    return Instr(1, 'STORE_NAME', arg)

def NOP():
    return Instr(1, 'NOP')

def RETURN_VALUE():
    return Instr(1, 'RETURN_VALUE')


def get_code(source, *, filename="<string>", function=False):
    source = textwrap.dedent(source).strip()
    code = compile(source, filename, "exec")
    if function:
        sub_code = [const for const in code.co_consts
                    if isinstance(const, types.CodeType)]
        if len(sub_code) != 1:
            raise ValueError("unable to find function code")
        code = sub_code[0]
    return code

def disassemble(source, *, filename="<string>", function=False,
                remove_last_return_none=False):
    code = get_code(source, filename=filename, function=function)

    bytecode = BytecodeBlocks.disassemble(code)
    if remove_last_return_none:
        # drop LOAD_CONST+RETURN_VALUE to only keep 2 instructions,
        # to make unit tests shorter
        block = bytecode[-1]
        test = (block[-2].name == "LOAD_CONST"
                and block[-2].arg is None
                and block[-1].name == "RETURN_VALUE")
        if not test:
            raise ValueError("unable to find implicit RETURN_VALUE <None>: %s"
                             % block[-2:])
        del block[-2:]
    return bytecode


class InstrTests(TestCase):
    def test_constructor(self):
        # invalid line number
        with self.assertRaises(TypeError):
            Instr("x", "NOP")
        with self.assertRaises(ValueError):
            Instr(0, "NOP")

        # invalid name
        with self.assertRaises(TypeError):
            Instr(1, 1)
        with self.assertRaises(ValueError):
            Instr(1, "xxx")

    def test_attr(self):
        instr = Instr(5, "LOAD_CONST", 3)
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

        instr = Instr(1, "ROT_TWO")
        self.assertIs(instr.arg, bytecode.UNSET)
        self.assertEqual(instr.op, opcode.opmap['ROT_TWO'])

    def test_extended_arg(self):
        instr = Instr(1, "LOAD_CONST", 0x1234abcd)
        self.assertEqual(instr.arg, 0x1234abcd)

    def test_slots(self):
        instr = Instr(1, "NOP")
        with self.assertRaises(AttributeError):
            instr.myattr = 1

    def test_compare(self):
        instr = Instr(7, "LOAD_CONST", 3)
        self.assertEqual(instr, Instr(7, "LOAD_CONST", 3))

        self.assertNotEqual(instr, Instr(6, "LOAD_CONST", 3))
        self.assertNotEqual(instr, Instr(7, "LOAD_FAST", 3))
        self.assertNotEqual(instr, Instr(7, "LOAD_CONST", 4))

    def test_is_jump(self):
        jump = Instr(1, "JUMP_ABSOLUTE", 3)
        self.assertTrue(jump.is_jump())

        instr = Instr(1, "LOAD_FAST", 2)
        self.assertFalse(instr.is_jump())

    def test_is_cond_jump(self):
        jump = Instr(1, "POP_JUMP_IF_TRUE", 3)
        self.assertTrue(jump.is_cond_jump())

        instr = Instr(1, "LOAD_FAST", 2)
        self.assertFalse(instr.is_cond_jump())


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

    def test_assemble(self):
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


class BytecodeBlocksTests(TestCase):
    def test_attr(self):
        source = """
            first_line = 1

            def func(arg1, arg2, *, arg3):
                x = 1
                y = 2
                return arg1
        """
        code = disassemble(source, filename="hello.py", function=True)
        self.assertEqual(code.argcount, 2)
        self.assertEqual(code.filename, "hello.py")
        self.assertEqual(code.first_lineno, 3)
        self.assertEqual(code.kw_only_argcount, 1)
        self.assertEqual(code.name, "func")
        self.assertEqual(code.freevars, [])
        self.assertEqual(code.cellvars, [])

        code.name = "name"
        code.filename = "filename"
        code.flags = 123
        self.assertEqual(code.name, "name")
        self.assertEqual(code.filename, "filename")
        self.assertEqual(code.flags, 123)

        # FIXME: test non-empty freevars
        # FIXME: test non-empty cellvars

    def test_constructor(self):
        code = BytecodeBlocks()
        self.assertEqual(code.name, "<module>")
        self.assertEqual(code.filename, "<string>")
        self.assertEqual(code.flags, 0)
        self.assertBlocksEqual(code, [])

    def test_add_del_block(self):
        code = BytecodeBlocks()
        code[0].append(LOAD_CONST(0))

        block = code.add_block()
        self.assertEqual(len(code), 2)
        self.assertIs(block, code[1])

        code[1].append(LOAD_CONST(2))
        self.assertBlocksEqual(code,
                               [LOAD_CONST(0)],
                               [LOAD_CONST(2)])

        del code[0]
        self.assertBlocksEqual(code,
                               [LOAD_CONST(2)])


class BytecodeBlocksFunctionalTests(TestCase):
    def sample_code(self):
        code = disassemble('x = 1', remove_last_return_none=True)
        self.assertBlocksEqual(code,
                               [LOAD_CONST(1), STORE_NAME('x')])
        return code

    def test_eq(self):
        # compare codes with multiple blocks and labels,
        # Code.__eq__() renumbers labels to get equal labels
        source = 'x = 1 if test else 2'
        code1 = disassemble(source)
        code2 = disassemble(source)
        self.assertEqual(code1, code2)

    def test_eq_labels(self):
        # equal
        code1 = BytecodeBlocks()
        label1 = Label()
        code1[0][:] = [Instr(1, "JUMP_FORWARD", label1),
                       Instr(1, "NOP"),
                       label1]
        code2 = BytecodeBlocks()
        label2 = Label()
        code2[0][:] = [Instr(1, "JUMP_FORWARD", label2),
                       Label(),   # unused label
                       Instr(1, "NOP"),
                       label2]
        self.assertEqual(code2, code1)

        # not equal
        code3 = BytecodeBlocks()
        label3 = Label()
        code3[0][:] = [Instr(1, "JUMP_FORWARD", label3),
                       label3,
                       Instr(1, "NOP")]
        self.assertNotEqual(code3, code1)

    def check_getitem(self, code):
        # check internal Code block indexes (index by index, index by label)
        for block_index, block in enumerate(code):
            self.assertIs(code[block_index], block)
            self.assertIs(code[block.label], block)

    def test_create_label_by_int_split(self):
        code = self.sample_code()
        code[0].append(NOP())

        label = code.create_label(0, 2)
        self.assertBlocksEqual(code,
                               [LOAD_CONST(1), STORE_NAME('x')],
                               [NOP()])
        self.assertEqual(label, code[1].label)
        self.check_getitem(code)

        label3 = code.create_label(0, 1)
        self.assertBlocksEqual(code,
                               [LOAD_CONST(1)],
                               [STORE_NAME('x')],
                               [NOP()])
        self.assertEqual(label, code[2].label)
        self.check_getitem(code)

    def test_create_label_by_label_split(self):
        code = self.sample_code()
        block_index = code[0].label

        label = code.create_label(block_index, 1)
        self.assertEqual(len(code), 2)
        self.assertBlocksEqual(code,
                               [LOAD_CONST(1), ],
                               [STORE_NAME('x')])
        self.assertEqual(label, code[1].label)
        self.check_getitem(code)

    def test_create_label_dont_split(self):
        code = self.sample_code()

        label = code.create_label(0, 0)
        self.assertBlocksEqual(code, [LOAD_CONST(1), STORE_NAME('x')])
        self.assertEqual(label, code[0].label)

    def test_create_label_error(self):
        code = self.sample_code()

        with self.assertRaises(ValueError):
            # cannot create a label at the end of a block,
            # only between instructions
            code.create_label(0, 2)

    def test_assemble(self):
        # test resolution of jump labels
        bytecode = disassemble("""
            first_line = 1

            def func(arg, arg2, arg3, *, kwonly=1, kwonly2=1):
                if x:
                    x = arg
                x = 3
                return x
        """, function=True)
        remove_jump_forward = sys.version_info >= (3, 5)
        label = bytecode[1].label
        if remove_jump_forward:
            blocks = [[Instr(4, 'LOAD_FAST', 'x'),
                       Instr(4, 'POP_JUMP_IF_FALSE', label),
                       Instr(5, 'LOAD_FAST', 'arg'),
                       Instr(5, 'STORE_FAST', 'x')],
                      [Instr(6, 'LOAD_CONST', 3),
                       Instr(6, 'STORE_FAST', 'x'),
                       Instr(7, 'LOAD_FAST', 'x'),
                       Instr(7, 'RETURN_VALUE')]]
            expected = (b'|\x05\x00'
                        b'r\x0c\x00'
                        b'|\x00\x00'
                        b'}\x05\x00'
                        b'd\x01\x00'
                        b'}\x05\x00'
                        b'|\x05\x00'
                        b'S')
        else:
            blocks = [[Instr(4, 'LOAD_FAST', 'x'),
                       Instr(4, 'POP_JUMP_IF_FALSE', bytecode[1].label),
                       Instr(5, 'LOAD_FAST', 'arg'),
                       Instr(5, 'STORE_FAST', 'x'),
                       Instr(5, 'JUMP_FORWARD', label)],
                      [Instr(6, 'LOAD_CONST', 3),
                       Instr(6, 'STORE_FAST', 'x'),
                       Instr(7, 'LOAD_FAST', 'x'),
                       Instr(7, 'RETURN_VALUE')]]
            expected = (b'|\x05\x00'
                        b'r\x0f\x00'
                        b'|\x00\x00'
                        b'}\x05\x00'
                        b'n\x00\x00'
                        b'd\x01\x00'
                        b'}\x05\x00'
                        b'|\x05\x00'
                        b'S')

        self.assertBlocksEqual(bytecode, *blocks)
        code = bytecode.assemble()
        self.assertEqual(code.co_argcount, 3)
        self.assertEqual(code.co_kwonlyargcount, 2)
        self.assertEqual(code.co_nlocals, 1)
        self.assertEqual(code.co_stacksize, 1)
        # FIXME: don't use hardcoded constants
        self.assertEqual(code.co_flags, 0x43)
        self.assertEqual(code.co_code, expected)
        self.assertEqual(code.co_names, ())
        self.assertEqual(code.co_varnames, ('arg', 'arg2', 'arg3', 'kwonly', 'kwonly2', 'x'))
        self.assertEqual(code.co_filename, '<string>')
        self.assertEqual(code.co_name, 'func')
        self.assertEqual(code.co_firstlineno, 3)

    def test_disassemble(self):
        code = disassemble("""
            if test:
                x = 1
            else:
                x = 2
        """)
        self.assertBlocksEqual(code,
                             [Instr(1, 'LOAD_NAME', 'test'),
                              Instr(1, 'POP_JUMP_IF_FALSE', code[1].label),
                              Instr(2, 'LOAD_CONST', 1),
                              Instr(2, 'STORE_NAME', 'x'),
                              Instr(2, 'JUMP_FORWARD', code[2].label)],

                             [Instr(4, 'LOAD_CONST', 2),
                              Instr(4, 'STORE_NAME', 'x')],

                             [Instr(4, 'LOAD_CONST', None),
                              Instr(4, 'RETURN_VALUE')])

    def test_load_fast(self):
        code = disassemble("""
            def func():
                x = 33
                y = x
        """, function=True, remove_last_return_none=True)
        self.assertBlocksEqual(code,
                             [Instr(2, 'LOAD_CONST', 33),
                              Instr(2, 'STORE_FAST', 'x'),
                              Instr(3, 'LOAD_FAST', 'x'),
                              Instr(3, 'STORE_FAST', 'y')])

    def test_lnotab(self):
        code = disassemble("""
            x = 1
            y = 2
            z = 3
        """, remove_last_return_none=True)
        self.assertEqual(len(code), 1)
        expected = [Instr(1, "LOAD_CONST", 1), Instr(1, "STORE_NAME", 'x'),
                    Instr(2, "LOAD_CONST", 2), Instr(2, "STORE_NAME", 'y'),
                    Instr(3, "LOAD_CONST", 3), Instr(3, "STORE_NAME", 'z')]
        self.assertBlocksEqual(code, expected)
        code_obj2 = code.assemble()

        self.assertEqual(code_obj2.co_lnotab, b'\x06\x01\x06\x01')

    @unittest.skipIf(True, 'FIXME')
    def test_extended_arg_make_function(self):
        source = '''
            def foo(x: int, y: int):
                pass
        '''
        code = disassemble(source, remove_last_return_none=True)
        self.assertEqual(len(code), 1)
        expected = [Instr(1, "LOAD_NAME", 'int'),
                    Instr(1, "LOAD_NAME", 'int'),
                    Instr(1, "LOAD_CONST", ('x', 'y')),
                    Instr(1, "LOAD_CONST", code.consts[1]),
                    Instr(1, "LOAD_CONST", 'foo'),
                    Instr(1, "MAKE_FUNCTION", 3 << 16),
                    Instr(1, "STORE_NAME", 'foo')]
        self.assertBlocksEqual(code, expected)

    def test_concrete_code(self):
        code = disassemble("""
            if test:
                x = 12
            else:
                x = 37
        """)
        code = code.concrete_code()
        expected = [ConcreteInstr(1, 'LOAD_NAME', 0),
                    ConcreteInstr(1, 'POP_JUMP_IF_FALSE', 15),
                    ConcreteInstr(2, 'LOAD_CONST', 0),
                    ConcreteInstr(2, 'STORE_NAME', 1),
                    ConcreteInstr(2, 'JUMP_FORWARD', 6),
                    ConcreteInstr(4, 'LOAD_CONST', 1),
                    ConcreteInstr(4, 'STORE_NAME', 1),
                    ConcreteInstr(4, 'LOAD_CONST', 2),
                    ConcreteInstr(4, 'RETURN_VALUE')]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, [12, 37, None])
        self.assertListEqual(code.names, ['test', 'x'])
        self.assertListEqual(code.varnames, [])

    def test_concrete_code_dont_merge_constants(self):
        # test two constants which are equal but have a different type
        code = BytecodeBlocks()
        block = code[0]
        block.append(Instr(1, 'LOAD_CONST', 5))
        block.append(Instr(1, 'LOAD_CONST', 5.0))

        code = code.concrete_code()
        expected = [ConcreteInstr(1, 'LOAD_CONST', 0),
                    ConcreteInstr(1, 'LOAD_CONST', 1)]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, [5, 5.0])

    def test_concrete_code_labels(self):
        code = BytecodeBlocks()
        label = Label()
        code[0].append(Instr(1, 'LOAD_CONST', 'hello'))
        code[0].append(Instr(1, 'JUMP_FORWARD', label))
        code[0].append(label)
        code[0].append(Instr(1, 'POP_TOP'))

        code = code.concrete_code()
        expected = [ConcreteInstr(1, 'LOAD_CONST', 0),
                    ConcreteInstr(1, 'JUMP_FORWARD', 0),
                    ConcreteInstr(1, 'POP_TOP')]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, ['hello'])


class ConcreteBytecodeTests(TestCase):
    def test_attr(self):
        code = get_code("x = 5")
        bytecode = ConcreteBytecode.disassemble(code)
        self.assertEqual(bytecode.consts, [5, None])
        self.assertEqual(bytecode.names, ['x'])
        self.assertEqual(bytecode.varnames, [])
        # FIXME: test other attributes

    def test_disassemble_concrete(self):
        code = get_code("x = 5")
        bytecode = ConcreteBytecode.disassemble(code)
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
        bytecode = ConcreteBytecode.disassemble(code)
        self.assertListEqual(list(bytecode),
                             [ConcreteInstr(1, "LOAD_CONST", 0x1234abcd)])

        # with EXTENDED_ARG opcode
        bytecode = ConcreteBytecode.disassemble(code, extended_arg_op=True)
        self.assertListEqual(list(bytecode),
                             [ConcreteInstr(1, 'EXTENDED_ARG', 0x1234),
                              ConcreteInstr(1, 'LOAD_CONST', 0xabcd)])


class BytecodeTests(unittest.TestCase):
    def test_disassemble(self):
        code = get_code("""
            if test:
                x = 1
            else:
                x = 2
        """)
        bytecode = Bytecode.disassemble(code)
        label = Label()
        self.assertEqual(bytecode,
                         [Instr(1, 'LOAD_NAME', 'test'),
                          Instr(1, 'POP_JUMP_IF_FALSE', label),
                          Instr(2, 'LOAD_CONST', 1),
                          Instr(2, 'STORE_NAME', 'x'),
                          Instr(2, 'JUMP_FORWARD', label),
                          label,
                          Instr(4, 'LOAD_CONST', 2),
                          Instr(4, 'STORE_NAME', 'x'),
                          Instr(4, 'LOAD_CONST', None),
                          Instr(4, 'RETURN_VALUE')])


class DumpCodeTests(unittest.TestCase):
    def check_dump_code(self, code, expected):
        with contextlib.redirect_stdout(io.StringIO()) as stderr:
            bytecode._dump_code(code)
            output = stderr.getvalue()

        self.assertEqual(output, expected)

    def test_bytecode_blocks(self):
        source = """
            def func(test):
                if test == 1:
                    return 1
                elif test == 2:
                    return 2
                return 3
        """
        code = disassemble(source, function=True)

        expected = textwrap.dedent("""
            label_block1:
                LOAD_FAST 'test'
                LOAD_CONST 1
                COMPARE_OP 2
                POP_JUMP_IF_FALSE <label_block2>
                LOAD_CONST 1
                RETURN_VALUE

            label_block2:
                LOAD_FAST 'test'
                LOAD_CONST 2
                COMPARE_OP 2
                POP_JUMP_IF_FALSE <label_block3>
                LOAD_CONST 2
                RETURN_VALUE

            label_block3:
                LOAD_CONST 3
                RETURN_VALUE

        """).lstrip()
        self.check_dump_code(code, expected)

    def test_concrete_bytecode(self):
        source = """
            def func(test):
                if test == 1:
                    return 1
                elif test == 2:
                    return 2
                return 3
        """
        code = disassemble(source, function=True)
        code = code.concrete_code()

        expected = """
  2  0    LOAD_FAST(0)
     3    LOAD_CONST(1)
     6    COMPARE_OP(2)
     9    POP_JUMP_IF_FALSE(16)
  3 12    LOAD_CONST(1)
    15    RETURN_VALUE
  4 16    LOAD_FAST(0)
    19    LOAD_CONST(2)
    22    COMPARE_OP(2)
    25    POP_JUMP_IF_FALSE(32)
  5 28    LOAD_CONST(2)
    31    RETURN_VALUE
  6 32    LOAD_CONST(3)
    35    RETURN_VALUE
""".lstrip("\n")
        self.check_dump_code(code, expected)


class MiscTests(unittest.TestCase):
    def test_version(self):
        import setup
        self.assertEqual(bytecode.__version__, setup.VERSION)


if __name__ == "__main__":
    unittest.main()

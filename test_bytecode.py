import bytecode
import opcode
import textwrap
import types
import unittest
from bytecode import Instr


def LOAD_CONST(arg):
    return Instr(1, 'LOAD_CONST', arg)

def STORE_NAME(arg):
    return Instr(1, 'STORE_NAME', arg)

def NOP():
    return Instr(1, 'NOP')

def RETURN_VALUE():
    return Instr(1, 'RETURN_VALUE')

def disassemble(source, *, filename="<string>", function=False):
    source = textwrap.dedent(source).strip()
    code_obj = compile(source, filename, "exec")
    if function:
        sub_code = [const for const in code_obj.co_consts
                    if isinstance(const, types.CodeType)]
        if len(sub_code) != 1:
            raise ValueError("unable to find function code")
        code_obj = sub_code[0]

    code = bytecode.Code.disassemble(code_obj)
    return code


class InstrTests(unittest.TestCase):
    def test_constructor(self):
        # invalid line number
        with self.assertRaises(TypeError):
            bytecode.Instr("x", "NOP")
        with self.assertRaises(ValueError):
            bytecode.Instr(0, "NOP")

        # invalid name
        with self.assertRaises(TypeError):
            bytecode.Instr(1, 1)
        with self.assertRaises(ValueError):
            bytecode.Instr(1, "xxx")

        # invalid argument
        with self.assertRaises(TypeError):
            bytecode.Instr(1, "LOAD_CONST", 1.0)
        with self.assertRaises(ValueError):
            bytecode.Instr(1, "LOAD_CONST", -1)
        with self.assertRaises(ValueError):
            bytecode.Instr(1, "LOAD_CONST", 0x1000000)

    def test_attr(self):
        instr = bytecode.Instr(5, "LOAD_CONST", 3)
        self.assertEqual(instr.lineno, 5)
        self.assertEqual(instr.name, 'LOAD_CONST')
        self.assertEqual(instr.arg, 3)
        self.assertEqual(instr.size, 3)
        self.assertEqual(instr.op, opcode.opmap['LOAD_CONST'])
        self.assertRaises(AttributeError, setattr, instr, 'lineno', 1)
        self.assertRaises(AttributeError, setattr, instr, 'name', 'LOAD_FAST')
        self.assertRaises(AttributeError, setattr, instr, 'arg', 2)

        instr = bytecode.Instr(1, "ROT_TWO")
        self.assertEqual(instr.size, 1)
        self.assertIsNone(instr.arg)
        self.assertEqual(instr.op, opcode.opmap['ROT_TWO'])

        # FIXME: test EXTENDED_ARG

    def test_slots(self):
        instr = bytecode.Instr(1, "NOP")
        with self.assertRaises(AttributeError):
            instr.myattr = 1

    def test_compare(self):
        instr = bytecode.Instr(7, "LOAD_CONST", 3)
        self.assertEqual(instr, bytecode.Instr(7, "LOAD_CONST", 3))

        self.assertNotEqual(instr, bytecode.Instr(6, "LOAD_CONST", 3))
        self.assertNotEqual(instr, bytecode.Instr(7, "LOAD_FAST", 3))
        self.assertNotEqual(instr, bytecode.Instr(7, "LOAD_CONST", 4))

    def test_get_jump_target(self):
        jump_abs = bytecode.Instr(1, "JUMP_ABSOLUTE", 3)
        self.assertEqual(jump_abs.get_jump_target(100), 3)

        jump_forward = bytecode.Instr(1, "JUMP_FORWARD", 5)
        self.assertEqual(jump_forward.get_jump_target(10), 18)

        label = bytecode.Label()
        jump_label = bytecode.Instr(1, "JUMP_FORWARD", label)
        with self.assertRaises(ValueError):
            jump_label.get_jump_target(10)

    def test_is_jump(self):
        jump = bytecode.Instr(1, "JUMP_ABSOLUTE", 3)
        self.assertTrue(jump.is_jump())

        instr = bytecode.Instr(1, "LOAD_FAST", 2)
        self.assertFalse(instr.is_jump())

    def test_is_cond_jump(self):
        jump = bytecode.Instr(1, "POP_JUMP_IF_TRUE", 3)
        self.assertTrue(jump.is_cond_jump())

        instr = bytecode.Instr(1, "LOAD_FAST", 2)
        self.assertFalse(instr.is_cond_jump())

    def test_assemble(self):
        instr = bytecode.Instr(1, "NOP")
        self.assertEqual(instr.assemble(), b'\t')

        instr = bytecode.Instr(1, "LOAD_CONST", 3)
        self.assertEqual(instr.assemble(), b'd\x03\x00')

    def test_disassemble(self):
        instr = bytecode.Instr.disassemble(1, b'\td\x03\x00', 0)
        self.assertEqual(instr, bytecode.Instr(1, "NOP"))

        instr = bytecode.Instr.disassemble(1, b'\td\x03\x00', 1)
        self.assertEqual(instr, bytecode.Instr(1, "LOAD_CONST", 3))


class CodeTests(unittest.TestCase):
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
        self.assertEqual(code.consts, [None, 1, 2])
        self.assertEqual(code.filename, "hello.py")
        self.assertEqual(code.first_lineno, 3)
        self.assertEqual(code.kw_only_argcount, 1)
        self.assertEqual(code.name, "func")
        self.assertEqual(code.varnames, ["arg1", "arg2", "arg3", "x", "y"])
        self.assertEqual(code.names, [])
        self.assertEqual(code.freevars, [])
        self.assertEqual(code.cellvars, [])

        code = disassemble("a = 1; b = 2")
        self.assertEqual(code.names, ["a", "b"])

        # FIXME: test non-empty freevars
        # FIXME: test non-empty cellvars

    def test_constructor(self):
        code = bytecode.Code("name", "filename", 123)
        self.assertEqual(code.name, "name")
        self.assertEqual(code.filename, "filename")
        self.assertEqual(code.flags, 123)
        self.assertEqual(len(code), 1)
        self.assertEqual(code[0], [])

    def test_add_del_block(self):
        code = bytecode.Code("name", "filename", 0)
        code[0].append(LOAD_CONST(0))

        block = code.add_block()
        self.assertEqual(len(code), 2)
        self.assertIs(block, code[1])

        code[1].append(LOAD_CONST(2))
        self.assertEqual(code[0], [LOAD_CONST(0)])
        self.assertEqual(code[1], [LOAD_CONST(2)])

        del code[0]
        self.assertEqual(len(code), 1)
        self.assertEqual(code[0], [LOAD_CONST(2)])


class FunctionalTests(unittest.TestCase):
    def sample_code(self):
        code = disassemble('x = 1')
        # drop LOAD_CONST+RETURN_VALUE to only keep 2 instructions,
        # to make unit tests shorter
        del code[0][2:]
        self.assertEqual(len(code), 1)
        self.assertListEqual(code[0], [LOAD_CONST(0), STORE_NAME(0)])
        return code

    def test_eq(self):
        # compare codes with multiple blocks and labels,
        # Code.__eq__() renumbers labels to get equal labels
        source = 'x = 1 if test else 2'
        code1 = disassemble(source)
        code2 = disassemble(source)
        self.assertEqual(code1, code2)

    def check_getitem(self, code):
        # check internal Code block indexes (index by index, index by label)
        for block_index, block in enumerate(code):
            self.assertIs(code[block_index], block)
            self.assertIs(code[block.label], block)

    def test_create_label_by_int_split(self):
        code = self.sample_code()
        code[0].append(NOP())

        label = code.create_label(0, 2)
        self.assertEqual(len(code), 2)
        self.assertListEqual(code[0], [LOAD_CONST(0), STORE_NAME(0)])
        self.assertListEqual(code[1], [NOP()])
        self.assertEqual(label, code[1].label)
        self.check_getitem(code)

        label3 = code.create_label(0, 1)
        self.assertEqual(len(code), 3)
        self.assertListEqual(code[0], [LOAD_CONST(0), ])
        self.assertListEqual(code[1], [STORE_NAME(0)])
        self.assertListEqual(code[2], [NOP()])
        self.assertEqual(label, code[2].label)
        self.check_getitem(code)

    def test_create_label_by_label_split(self):
        code = self.sample_code()
        block_index = code[0].label

        label = code.create_label(block_index, 1)
        self.assertEqual(len(code), 2)
        self.assertListEqual(code[0], [LOAD_CONST(0), ])
        self.assertListEqual(code[1], [STORE_NAME(0)])
        self.assertEqual(label, code[1].label)
        self.check_getitem(code)

    def test_create_label_dont_split(self):
        code = self.sample_code()

        label = code.create_label(0, 0)
        self.assertEqual(len(code), 1)
        self.assertListEqual(code[0], [LOAD_CONST(0), STORE_NAME(0)])
        self.assertEqual(label, code[0].label)

    def test_create_label_error(self):
        code = self.sample_code()

        with self.assertRaises(ValueError):
            # cannot create a label at the end of a block,
            # only between instructions
            code.create_label(0, 2)

    def test_assemble(self):
        # test resolution of jump labels
        code_obj = compile("if x: x=2\nx=3", "<string>", "exec")
        code = bytecode.Code.disassemble(code_obj)
        code2 = code.assemble()
        self.assertEqual(code2.co_code, code_obj.co_code)

    def test_disassemble(self):
        code_obj = compile("if test:\n x = 1\nelse:\n x = 2", "<string>", "exec")
        code = bytecode.Code.disassemble(code_obj)
        self.assertEqual(len(code), 3)
        expected = [Instr(1, 'LOAD_NAME', 0),
                    Instr(1, 'POP_JUMP_IF_FALSE', code[1].label),
                    Instr(2, 'LOAD_CONST', 0),
                    Instr(2, 'STORE_NAME', 1),
                    Instr(2, 'JUMP_FORWARD', code[2].label)]
        self.assertListEqual(code[0], expected)

        expected = [Instr(4, 'LOAD_CONST', 1),
                    Instr(4, 'STORE_NAME', 1)]
        self.assertListEqual(code[1], expected)

        expected = [Instr(4, 'LOAD_CONST', 2),
                    Instr(4, 'RETURN_VALUE')]
        self.assertListEqual(code[2], expected)

    def test_disassemble_no_label(self):
        code_obj = compile("if test:\n x = 1\nelse:\n x = 2", "<string>", "exec")
        code = bytecode.Code.disassemble(code_obj, use_labels=False)
        self.assertEqual(len(code), 1)
        expected = [Instr(1, 'LOAD_NAME', 0),
                    Instr(1, 'POP_JUMP_IF_FALSE', 15),
                    Instr(2, 'LOAD_CONST', 0),
                    Instr(2, 'STORE_NAME', 1),
                    Instr(2, 'JUMP_FORWARD', 6),
                    Instr(4, 'LOAD_CONST', 1),
                    Instr(4, 'STORE_NAME', 1),
                    Instr(4, 'LOAD_CONST', 2),
                    Instr(4, 'RETURN_VALUE')]
        self.assertListEqual(code[0], expected)

    def test_lnotab(self):
        code_obj = compile("x = 1\ny = 2\nz = 3", "<string>", "exec")
        code = bytecode.Code.disassemble(code_obj)
        self.assertEqual(len(code), 1)
        expected = [Instr(1, "LOAD_CONST", 0), Instr(1, "STORE_NAME", 0),
                    Instr(2, "LOAD_CONST", 1), Instr(2, "STORE_NAME", 1),
                    Instr(3, "LOAD_CONST", 2), Instr(3, "STORE_NAME", 2),
                    Instr(3, "LOAD_CONST", 3), Instr(3, "RETURN_VALUE")]
        self.assertListEqual(code[0], expected)
        code_obj2 = code.assemble()

        self.assertEqual(code_obj2.co_lnotab, b'\x06\x01\x06\x01')
        self.assertEqual(code_obj2.co_lnotab, code_obj.co_lnotab)


class MiscTests(unittest.TestCase):
    def test_version(self):
        import setup
        self.assertEqual(bytecode.__version__, setup.VERSION)


if __name__ == "__main__":
    unittest.main()

import bytecode
import sys
import unittest
from bytecode import Instr


def LOAD_CONST(arg):
    return Instr(1, 'LOAD_CONST', arg)

def STORE_NAME(arg):
    return Instr(1, 'STORE_NAME', arg)

def RETURN_VALUE():
    return Instr(1, 'RETURN_VALUE')


class InstrTests(unittest.TestCase):
    def test_instr(self):
        instr = bytecode.Instr(5, "LOAD_CONST", 3)
        self.assertEqual(instr.lineno, 5)
        self.assertEqual(instr.name, 'LOAD_CONST')
        self.assertEqual(instr.arg, 3)
        self.assertRaises(AttributeError, setattr, instr, 'lineno', 1)
        self.assertRaises(AttributeError, setattr, instr, 'name', 'LOAD_FAST')
        self.assertRaises(AttributeError, setattr, instr, 'arg', 2)

    def test_instr_cmp(self):
        instr1 = bytecode.Instr(5, "LOAD_CONST", 3)
        instr2 = bytecode.Instr(5, "LOAD_CONST", 3)
        self.assertEqual(instr1, instr2)

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


class CodeTests(unittest.TestCase):
    def setUp(self):
        if hasattr(sys, 'get_code_transformers'):
            # Python 3.6 and PEP 511
            transformers = sys.get_code_transformers()
            self.addCleanup(sys.set_code_transformers, transformers)
            sys.set_code_transformers([])

    def disassemble(self, source):
        code_obj = compile(source, "<string>", "exec")
        code = bytecode.Code.disassemble(code_obj)
        return code

    def sample_code(self):
        code = self.disassemble('x = 1')
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
        code1 = self.disassemble(source)
        code2 = self.disassemble(source)
        self.assertEqual(code1, code2)

    def test_create_label_by_int_split(self):
        code = self.sample_code()
        block_index = 0

        label = code.create_label(block_index, 1)
        self.assertEqual(len(code), 2)
        self.assertListEqual(code[0], [LOAD_CONST(0), ])
        self.assertListEqual(code[1], [STORE_NAME(0)])
        self.assertEqual(label, code[1].label)

    def test_create_label_by_label_split(self):
        code = self.sample_code()
        block_index = code[0].label

        label = code.create_label(block_index, 1)
        self.assertEqual(len(code), 2)
        self.assertListEqual(code[0], [LOAD_CONST(0), ])
        self.assertListEqual(code[1], [STORE_NAME(0)])
        self.assertEqual(label, code[1].label)

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
        code_obj = compile("x = 1", "<string>", "exec")
        code = bytecode.Code.disassemble(code_obj)
        self.assertEqual(len(code), 1)
        self.assertEqual(code[0],
                         [LOAD_CONST(0), STORE_NAME(0),
                          LOAD_CONST(1), RETURN_VALUE()])

    def test_disassemble(self):
        code_obj = compile("x = 1", "<string>", "exec")
        code = bytecode.Code.disassemble(code_obj)
        self.assertEqual(len(code), 1)
        self.assertEqual(code[0],
                         [LOAD_CONST(0), STORE_NAME(0),
                          LOAD_CONST(1), RETURN_VALUE()])

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


if __name__ == "__main__":
    unittest.main()

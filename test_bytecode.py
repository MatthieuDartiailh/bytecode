import bytecode
import sys
import unittest


def instr(name, arg=None):
    return bytecode.Instr(1, name, arg)

def LOAD_CONST(arg):
    return instr('LOAD_CONST', arg)

def STORE_NAME(arg):
    return instr('STORE_NAME', arg)


class TestInstr(unittest.TestCase):
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


class Tests(unittest.TestCase):
    def setUp(self):
        if hasattr(sys, 'get_code_transformers'):
            # Python 3.6 and PEP 511
            transformers = sys.get_code_transformers()
            self.addCleanup(sys.set_code_transformers, transformers)
            sys.set_code_transformers([])

    def test_resolve_jumps(self):
        code_obj = compile("if x: x=2\nx=3", "<string>", "exec")
        code = bytecode.Code.disassemble(code_obj)
        code2 = code.assemble()
        self.assertEqual(code2.co_code, code_obj.co_code)

    def sample_code(self):
        code_obj = compile("x = 1", "<string>", "exec")
        code = bytecode.Code.disassemble(code_obj)
        # drop LOAD_CONST+RETURN_VALUE to only keep 2 instructions,
        # to make unit tests shorter
        del code[0][2:]
        self.assertEqual(len(code), 1)
        self.assertListEqual(code[0], [LOAD_CONST(0), STORE_NAME(0)])
        return code

    def test_eq(self):
        code1 = self.sample_code()
        code2 = self.sample_code()
        self.assertEqual(code1, code2)
        # FIXME: test with labels

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


if __name__ == "__main__":
    unittest.main()

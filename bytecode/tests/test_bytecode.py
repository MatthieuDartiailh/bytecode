#!/usr/bin/env python3
import unittest
from bytecode import Label, Instr, Bytecode, ConcreteInstr
from bytecode.tests import TestCase, get_code, disassemble


class BytecodeTests(TestCase):
    maxDiff = 80 * 100

    def test_constructor(self):
        code = Bytecode()
        self.assertEqual(code.name, "<module>")
        self.assertEqual(code.filename, "<string>")
        self.assertEqual(code.flags, 0)
        self.assertEqual(code, [])

    def test_from_code(self):
        code = get_code("""
            if test:
                x = 1
            else:
                x = 2
        """)
        bytecode = Bytecode.from_code(code)
        label_else = Label()
        label_exit = Label()
        self.assertEqual(bytecode,
                         [Instr('LOAD_NAME', 'test', lineno=1),
                          Instr('POP_JUMP_IF_FALSE', label_else, lineno=1),
                          Instr('LOAD_CONST', 1, lineno=2),
                          Instr('STORE_NAME', 'x', lineno=2),
                          Instr('JUMP_FORWARD', label_exit, lineno=2),
                          label_else,
                          Instr('LOAD_CONST', 2, lineno=4),
                          Instr('STORE_NAME', 'x', lineno=4),
                          label_exit,
                          Instr('LOAD_CONST', None, lineno=4),
                          Instr('RETURN_VALUE', lineno=4)])

    def test_to_concrete_code(self):
        bytecode = Bytecode()
        label = Label()
        bytecode.extend([Instr('LOAD_NAME', 'test', lineno=1),
                         Instr('POP_JUMP_IF_FALSE', label, lineno=1),
                         Instr('LOAD_CONST', 5, lineno=2),
                         Instr('STORE_NAME', 'x', lineno=2),
                         Instr('JUMP_FORWARD', label, lineno=2),
                         Instr('LOAD_CONST', 7, lineno=4),
                         Instr('STORE_NAME', 'x', lineno=4),
                         label,
                         Instr('LOAD_CONST', None, lineno=4),
                         Instr('RETURN_VALUE', lineno=4)])

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

    def test_to_concrete_bytecode(self):
        code = disassemble("""
            if test:
                x = 12
            else:
                x = 37
        """)
        # FIXME: modify disassemble() to return directly Bytecode
        code = code.to_bytecode()

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

    def test_to_concrete_bytecode_dont_merge_constants(self):
        # test two constants which are equal but have a different type
        code = Bytecode()
        code.extend([Instr('LOAD_CONST', 5, lineno=1),
                     Instr('LOAD_CONST', 5.0, lineno=1)])

        code = code.to_concrete_bytecode()
        expected = [ConcreteInstr('LOAD_CONST', 0, lineno=1),
                    ConcreteInstr('LOAD_CONST', 1, lineno=1)]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, [5, 5.0])

    def test_to_concrete_bytecode_labels(self):
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


if __name__ == "__main__":
    unittest.main()

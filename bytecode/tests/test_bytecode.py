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

    def test_disassemble(self):
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
                         [Instr(1, 'LOAD_NAME', 'test'),
                          Instr(1, 'POP_JUMP_IF_FALSE', label_else),
                          Instr(2, 'LOAD_CONST', 1),
                          Instr(2, 'STORE_NAME', 'x'),
                          Instr(2, 'JUMP_FORWARD', label_exit),
                          label_else,
                          Instr(4, 'LOAD_CONST', 2),
                          Instr(4, 'STORE_NAME', 'x'),
                          label_exit,
                          Instr(4, 'LOAD_CONST', None),
                          Instr(4, 'RETURN_VALUE')])

    def test_to_concrete_code(self):
        bytecode = Bytecode()
        label = Label()
        bytecode.extend([Instr(1, 'LOAD_NAME', 'test'),
                         Instr(1, 'POP_JUMP_IF_FALSE', label),
                         Instr(2, 'LOAD_CONST', 5),
                         Instr(2, 'STORE_NAME', 'x'),
                         Instr(2, 'JUMP_FORWARD', label),
                         Instr(4, 'LOAD_CONST', 7),
                         Instr(4, 'STORE_NAME', 'x'),
                         label,
                         Instr(4, 'LOAD_CONST', None),
                         Instr(4, 'RETURN_VALUE')])

        concrete = bytecode.to_concrete_bytecode()
        expected = [ConcreteInstr(1, 'LOAD_NAME', 0),
                    ConcreteInstr(1, 'POP_JUMP_IF_FALSE', 21),
                    ConcreteInstr(2, 'LOAD_CONST', 0),
                    ConcreteInstr(2, 'STORE_NAME', 1),
                    ConcreteInstr(2, 'JUMP_FORWARD', 6),
                    ConcreteInstr(4, 'LOAD_CONST', 1),
                    ConcreteInstr(4, 'STORE_NAME', 1),
                    ConcreteInstr(4, 'LOAD_CONST', 2),
                    ConcreteInstr(4, 'RETURN_VALUE')]
        self.assertListEqual(list(concrete), expected)
        self.assertListEqual(concrete.consts, [5, 7, None])
        self.assertListEqual(concrete.names, ['test', 'x'])
        self.assertListEqual(concrete.varnames, [])

    def test_to_bytecode_blocks(self):
        bytecode = Bytecode()
        label = Label()
        bytecode.extend([Instr(1, 'LOAD_NAME', 'test'),
                         Instr(1, 'POP_JUMP_IF_FALSE', label),
                         Instr(2, 'LOAD_CONST', 5),
                         Instr(2, 'STORE_NAME', 'x'),
                         Instr(2, 'JUMP_FORWARD', label),
                         Instr(4, 'LOAD_CONST', 7),
                         Instr(4, 'STORE_NAME', 'x'),
                         Label(),  # unused label
                         label,
                         Label(),  # unused label
                         Instr(4, 'LOAD_CONST', None),
                         Instr(4, 'RETURN_VALUE')])

        blocks = bytecode.to_bytecode_blocks()
        label2 = blocks[1].label
        self.assertIsNot(label2, label)
        self.assertBlocksEqual(blocks,
                               [Instr(1, 'LOAD_NAME', 'test'),
                                Instr(1, 'POP_JUMP_IF_FALSE', label2),
                                Instr(2, 'LOAD_CONST', 5),
                                Instr(2, 'STORE_NAME', 'x'),
                                Instr(2, 'JUMP_FORWARD', label2),
                                Instr(4, 'LOAD_CONST', 7),
                                Instr(4, 'STORE_NAME', 'x')],
                               [Instr(4, 'LOAD_CONST', None),
                                Instr(4, 'RETURN_VALUE')])
        # FIXME: test other attributes

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

    def test_to_concrete_bytecode_dont_merge_constants(self):
        # test two constants which are equal but have a different type
        code = Bytecode()
        code.extend([Instr(1, 'LOAD_CONST', 5),
                     Instr(1, 'LOAD_CONST', 5.0)])

        code = code.to_concrete_bytecode()
        expected = [ConcreteInstr(1, 'LOAD_CONST', 0),
                    ConcreteInstr(1, 'LOAD_CONST', 1)]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, [5, 5.0])

    def test_to_concrete_bytecode_labels(self):
        code = Bytecode()
        label = Label()
        code.extend([Instr(1, 'LOAD_CONST', 'hello'),
                     Instr(1, 'JUMP_FORWARD', label),
                     label,
                     Instr(1, 'POP_TOP')])

        code = code.to_concrete_bytecode()
        expected = [ConcreteInstr(1, 'LOAD_CONST', 0),
                    ConcreteInstr(1, 'JUMP_FORWARD', 0),
                    ConcreteInstr(1, 'POP_TOP')]
        self.assertListEqual(list(code), expected)
        self.assertListEqual(code.consts, ['hello'])


if __name__ == "__main__":
    unittest.main()

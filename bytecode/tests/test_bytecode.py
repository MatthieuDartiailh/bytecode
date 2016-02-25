#!/usr/bin/env python3
import unittest
from bytecode import Label, Instr, Bytecode, ConcreteInstr
from bytecode.tests import TestCase, get_code


class BytecodeTests(TestCase):
    maxDiff = 80 * 100

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

    def test_concrete_code(self):
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


if __name__ == "__main__":
    unittest.main()

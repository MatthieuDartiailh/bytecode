#!/usr/bin/env python3
import sys
import unittest
from bytecode import Label, Instr, ConcreteInstr, BytecodeBlocks
from bytecode.tests import LOAD_CONST, STORE_NAME, NOP, disassemble, TestCase


class BytecodeBlocksTests(TestCase):
    def test_constructor(self):
        code = BytecodeBlocks()
        self.assertEqual(code.name, "<module>")
        self.assertEqual(code.filename, "<string>")
        self.assertEqual(code.flags, 0)
        self.assertBlocksEqual(code, [])

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

        del code[0]
        self.assertEqual(len(code), 0)

    def test_to_bytecode(self):
        blocks = BytecodeBlocks()
        label = blocks.add_block().label
        blocks[0].extend([Instr(1, 'LOAD_NAME', 'test'),
                          Instr(1, 'POP_JUMP_IF_FALSE', label),
                          Instr(2, 'LOAD_CONST', 5),
                          Instr(2, 'STORE_NAME', 'x'),
                          Instr(2, 'JUMP_FORWARD', label),
                          Instr(4, 'LOAD_CONST', 7),
                          Instr(4, 'STORE_NAME', 'x')])
        blocks[1].extend([Instr(4, 'LOAD_CONST', None),
                          Instr(4, 'RETURN_VALUE')])

        bytecode = blocks.to_bytecode()
        label = Label()
        self.assertEqual(bytecode,
                         [Instr(1, 'LOAD_NAME', 'test'),
                          Instr(1, 'POP_JUMP_IF_FALSE', label),
                          Instr(2, 'LOAD_CONST', 5),
                          Instr(2, 'STORE_NAME', 'x'),
                          Instr(2, 'JUMP_FORWARD', label),
                          Instr(4, 'LOAD_CONST', 7),
                          Instr(4, 'STORE_NAME', 'x'),
                          label,
                          Instr(4, 'LOAD_CONST', None),
                          Instr(4, 'RETURN_VALUE')])
        # FIXME: test other attributes


class BytecodeBlocksFunctionalTests(TestCase):
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

    def sample_code(self):
        code = disassemble('x = 1', remove_last_return_none=True)
        self.assertBlocksEqual(code,
                               [LOAD_CONST(1), STORE_NAME('x')])
        return code

    def test_create_label_by_int_split(self):
        code = self.sample_code()
        code[0].append(NOP())

        label = code.create_label(0, 2)
        self.assertBlocksEqual(code,
                               [LOAD_CONST(1), STORE_NAME('x')],
                               [NOP()])
        self.assertIs(label, code[1].label)
        self.check_getitem(code)

        label2 = code.create_label(0, 1)
        self.assertBlocksEqual(code,
                               [LOAD_CONST(1)],
                               [STORE_NAME('x')],
                               [NOP()])
        self.assertIs(label2, code[1].label)
        self.assertIs(label, code[2].label)
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
        code = bytecode.to_code()
        self.assertEqual(code.co_consts, (None, 3))
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
        code_obj2 = code.to_code()

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

    def test_to_concrete_bytecode(self):
        code = disassemble("""
            if test:
                x = 12
            else:
                x = 37
        """)
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


if __name__ == "__main__":
    unittest.main()

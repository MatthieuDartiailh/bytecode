#!/usr/bin/env python3
import unittest
from bytecode import Label, Instr, ConcreteInstr, Bytecode, BytecodeBlocks
from bytecode.tests import disassemble, TestCase, get_code


class BytecodeBlocksTests(TestCase):
    maxDiff = 80 * 100

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
        self.assertEqual(code.cellvars, [])

        code.name = "name"
        code.filename = "filename"
        code.flags = 123
        self.assertEqual(code.name, "name")
        self.assertEqual(code.filename, "filename")
        self.assertEqual(code.flags, 123)

        # FIXME: test non-empty cellvars

    def test_add_del_block(self):
        code = BytecodeBlocks()
        code[0].append(Instr('LOAD_CONST', 0))

        block = code.add_block()
        self.assertEqual(len(code), 2)
        self.assertIs(block, code[1])

        code[1].append(Instr('LOAD_CONST', 2))
        self.assertBlocksEqual(code,
                               [Instr('LOAD_CONST', 0)],
                               [Instr('LOAD_CONST', 2)])

        del code[0]
        self.assertBlocksEqual(code,
                               [Instr('LOAD_CONST', 2)])

        del code[0]
        self.assertEqual(len(code), 0)

    def test_to_bytecode(self):
        blocks = BytecodeBlocks()
        block1 = blocks.add_block()
        blocks[0].extend([Instr('LOAD_NAME', 'test', lineno=1),
                          Instr('POP_JUMP_IF_FALSE', block1, lineno=1),
                          Instr('LOAD_CONST', 5, lineno=2),
                          Instr('STORE_NAME', 'x', lineno=2),
                          Instr('JUMP_FORWARD', block1, lineno=2),
                          Instr('LOAD_CONST', 7, lineno=4),
                          Instr('STORE_NAME', 'x', lineno=4)])
        blocks[1].extend([Instr('LOAD_CONST', None, lineno=4),
                          Instr('RETURN_VALUE', lineno=4)])

        bytecode = blocks.to_bytecode()

        label = Label()
        self.assertEqual(bytecode,
                         [Instr('LOAD_NAME', 'test', lineno=1),
                          Instr('POP_JUMP_IF_FALSE', label, lineno=1),
                          Instr('LOAD_CONST', 5, lineno=2),
                          Instr('STORE_NAME', 'x', lineno=2),
                          Instr('JUMP_FORWARD', label, lineno=2),
                          Instr('LOAD_CONST', 7, lineno=4),
                          Instr('STORE_NAME', 'x', lineno=4),
                          label,
                          Instr('LOAD_CONST', None, lineno=4),
                          Instr('RETURN_VALUE', lineno=4)])
        # FIXME: test other attributes

    def test_to_bytecode_labels(self):
        blocks = BytecodeBlocks()
        label = Label()
        blocks[0].extend([Instr('LOAD_NAME', 'test'),
                          Instr('POP_JUMP_IF_FALSE', label),
                          label])

        with self.assertRaises(ValueError) as cm:
            blocks.to_bytecode()
        self.assertEqual(str(cm.exception), 'Label must not be used in blocks')


    def test_from_bytecode(self):
        bytecode = Bytecode()
        label = Label()
        bytecode.extend([Instr('LOAD_NAME', 'test', lineno=1),
                         Instr('POP_JUMP_IF_FALSE', label, lineno=1),
                         Instr('LOAD_CONST', 5, lineno=2),
                         Instr('STORE_NAME', 'x', lineno=2),
                         Instr('JUMP_FORWARD', label, lineno=2),
                             # dead code!
                             Instr('LOAD_CONST', 7, lineno=4),
                             Instr('STORE_NAME', 'x', lineno=4),
                             Label(),  # unused label
                         label,
                             Label(),  # unused label
                             Instr('LOAD_CONST', None, lineno=4),
                             Instr('RETURN_VALUE', lineno=4)])

        blocks = BytecodeBlocks.from_bytecode(bytecode)
        label2 = blocks[3]
        self.assertIsNot(label2, label)
        self.assertBlocksEqual(blocks,
                               [Instr('LOAD_NAME', 'test', lineno=1),
                                Instr('POP_JUMP_IF_FALSE', label2, lineno=1)],
                               [Instr('LOAD_CONST', 5, lineno=2),
                                Instr('STORE_NAME', 'x', lineno=2),
                                Instr('JUMP_FORWARD', label2, lineno=2)],
                               [Instr('LOAD_CONST', 7, lineno=4),
                                Instr('STORE_NAME', 'x', lineno=4)],
                               [Instr('LOAD_CONST', None, lineno=4),
                                Instr('RETURN_VALUE', lineno=4)])
        # FIXME: test other attributes

    def test_from_bytecode_loop(self):
        # for x in (1, 2, 3):
        #     if x == 2:
        #         break
        #     continue

        label_loop_start = Label()
        label_loop_exit = Label()
        label_loop_end = Label()

        code = Bytecode()
        code.extend((Instr('SETUP_LOOP', label_loop_end, lineno=1),
                     Instr('LOAD_CONST', (1, 2, 3), lineno=1),
                     Instr('GET_ITER', lineno=1),

                     label_loop_start,
                     Instr('FOR_ITER', label_loop_exit, lineno=1),
                     Instr('STORE_NAME', 'x', lineno=1),
                     Instr('LOAD_NAME', 'x', lineno=2),
                     Instr('LOAD_CONST', 2, lineno=2),
                     Instr('COMPARE_OP', 2, lineno=2),
                     Instr('POP_JUMP_IF_FALSE', label_loop_start, lineno=2),
                     Instr('BREAK_LOOP', lineno=3),
                     Instr('JUMP_ABSOLUTE', label_loop_start, lineno=4),

                     Instr('JUMP_ABSOLUTE', label_loop_start, lineno=4),

                     label_loop_exit,
                     Instr('POP_BLOCK', lineno=4),

                     label_loop_end,
                     Instr('LOAD_CONST', None, lineno=4),
                     Instr('RETURN_VALUE', lineno=4),
        ))
        blocks = BytecodeBlocks.from_bytecode(code)

        expected = [[Instr('SETUP_LOOP', blocks[6], lineno=1),
                     Instr('LOAD_CONST', (1, 2, 3), lineno=1),
                     Instr('GET_ITER', lineno=1)],

                    [Instr('FOR_ITER', blocks[5], lineno=1),
                     Instr('STORE_NAME', 'x', lineno=1),
                     Instr('LOAD_NAME', 'x', lineno=2),
                     Instr('LOAD_CONST', 2, lineno=2),
                     Instr('COMPARE_OP', 2, lineno=2),
                     Instr('POP_JUMP_IF_FALSE', blocks[1], lineno=2)],

                    [Instr('BREAK_LOOP', lineno=3)],

                    [Instr('JUMP_ABSOLUTE', blocks[1], lineno=4)],

                    [Instr('JUMP_ABSOLUTE', blocks[1], lineno=4)],

                    [Instr('POP_BLOCK', lineno=4)],

                    [Instr('LOAD_CONST', None, lineno=4),
                     Instr('RETURN_VALUE', lineno=4)]]
        self.assertBlocksEqual(blocks, *expected)


class BytecodeBlocksFunctionalTests(TestCase):
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
            self.assertIs(code[block], block)

    def sample_code(self):
        code = disassemble('x = 1', remove_last_return_none=True)
        self.assertBlocksEqual(code,
                               [Instr('LOAD_CONST', 1, lineno=1),
                                Instr('STORE_NAME', 'x', lineno=1)])
        return code

    def test_split_block_by_int_split(self):
        code = self.sample_code()
        code[0].append(Instr('NOP', lineno=1))

        label = code.split_block(code[0], 2)
        self.assertIs(label, code[1])
        self.assertBlocksEqual(code,
                               [Instr('LOAD_CONST', 1, lineno=1),
                                Instr('STORE_NAME', 'x', lineno=1)],
                               [Instr('NOP', lineno=1)])
        self.check_getitem(code)

        label2 = code.split_block(code[0], 1)
        self.assertIs(label2, code[1])
        self.assertBlocksEqual(code,
                               [Instr('LOAD_CONST', 1, lineno=1)],
                               [Instr('STORE_NAME', 'x', lineno=1)],
                               [Instr('NOP', lineno=1)])
        self.check_getitem(code)

    def test_split_block_dont_split(self):
        code = self.sample_code()

        # FIXME: is it really useful to support that?
        block = code.split_block(code[0], 0)
        self.assertIs(block, code[0])
        self.assertBlocksEqual(code,
                              [Instr('LOAD_CONST', 1, lineno=1),
                               Instr('STORE_NAME', 'x', lineno=1)])

    def test_split_block_error(self):
        code = self.sample_code()

        with self.assertRaises(ValueError):
            # cannot create a label at the end of a block,
            # only between instructions
            code.split_block(code[0], 2)

    def test_to_code(self):
        # test resolution of jump labels
        bytecode = BytecodeBlocks()
        bytecode.first_lineno = 3
        bytecode.argcount = 3
        bytecode.kw_only_argcount = 2
        bytecode._stacksize = 1
        bytecode.name = 'func'
        bytecode.filename = 'hello.py'
        bytecode.flags = 0x43
        bytecode.argnames = ('arg', 'arg2', 'arg3', 'kwonly', 'kwonly2')
        bytecode.docstring = None
        block0 = bytecode[0]
        block1 = bytecode.add_block()
        block0.extend([Instr('LOAD_FAST', 'x', lineno=4),
                       Instr('POP_JUMP_IF_FALSE', block1, lineno=4),
                       Instr('LOAD_FAST', 'arg', lineno=5),
                       Instr('STORE_FAST', 'x', lineno=5)])
        block1.extend([Instr('LOAD_CONST', 3, lineno=6),
                       Instr('STORE_FAST', 'x', lineno=6),
                       Instr('LOAD_FAST', 'x', lineno=7),
                       Instr('RETURN_VALUE', lineno=7)])

        expected = (b'|\x05\x00'
                    b'r\x0c\x00'
                    b'|\x00\x00'
                    b'}\x05\x00'
                    b'd\x01\x00'
                    b'}\x05\x00'
                    b'|\x05\x00'
                    b'S')

        code = bytecode.to_code()
        self.assertEqual(code.co_consts, (None, 3))
        self.assertEqual(code.co_argcount, 3)
        self.assertEqual(code.co_kwonlyargcount, 2)
        self.assertEqual(code.co_nlocals, 6)
        self.assertEqual(code.co_stacksize, 1)
        # FIXME: don't use hardcoded constants
        self.assertEqual(code.co_flags, 0x43)
        self.assertEqual(code.co_code, expected)
        self.assertEqual(code.co_names, ())
        self.assertEqual(code.co_varnames, ('arg', 'arg2', 'arg3', 'kwonly', 'kwonly2', 'x'))
        self.assertEqual(code.co_filename, 'hello.py')
        self.assertEqual(code.co_name, 'func')
        self.assertEqual(code.co_firstlineno, 3)



if __name__ == "__main__":
    unittest.main()

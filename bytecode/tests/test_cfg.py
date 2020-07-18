#!/usr/bin/env python3
import io
import sys
import unittest
import contextlib
from bytecode import (
    Label,
    Compare,
    SetLineno,
    Instr,
    Bytecode,
    ConcreteBytecode,
    BasicBlock,
    ControlFlowGraph,
)
from bytecode.tests import disassemble as _disassemble, TestCase, WORDCODE


def disassemble(
    source, *, filename="<string>", function=False, remove_last_return_none=False
):
    code = _disassemble(source, filename=filename, function=function)
    blocks = ControlFlowGraph.from_bytecode(code)
    if remove_last_return_none:
        # drop LOAD_CONST+RETURN_VALUE to only keep 2 instructions,
        # to make unit tests shorter
        block = blocks[-1]
        test = (
            block[-2].name == "LOAD_CONST"
            and block[-2].arg is None
            and block[-1].name == "RETURN_VALUE"
        )
        if not test:
            raise ValueError(
                "unable to find implicit RETURN_VALUE <None>: %s" % block[-2:]
            )
        del block[-2:]
    return blocks


class BlockTests(unittest.TestCase):
    def test_iter_invalid_types(self):
        # Labels are not allowed in basic blocks
        block = BasicBlock()
        block.append(Label())
        with self.assertRaises(ValueError):
            list(block)
        with self.assertRaises(ValueError):
            block.legalize(1)

        # Only one jump allowed and only at the end
        block = BasicBlock()
        block2 = BasicBlock()
        block.extend([Instr("JUMP_ABSOLUTE", block2), Instr("NOP")])
        with self.assertRaises(ValueError):
            list(block)
        with self.assertRaises(ValueError):
            block.legalize(1)

        # jump target must be a BasicBlock
        block = BasicBlock()
        label = Label()
        block.extend([Instr("JUMP_ABSOLUTE", label)])
        with self.assertRaises(ValueError):
            list(block)
        with self.assertRaises(ValueError):
            block.legalize(1)

    def test_slice(self):
        block = BasicBlock([Instr("NOP")])
        next_block = BasicBlock()
        block.next_block = next_block
        self.assertEqual(block, block[:])
        self.assertIs(next_block, block[:].next_block)

    def test_copy(self):
        block = BasicBlock([Instr("NOP")])
        next_block = BasicBlock()
        block.next_block = next_block
        self.assertEqual(block, block.copy())
        self.assertIs(next_block, block.copy().next_block)


class BytecodeBlocksTests(TestCase):
    maxDiff = 80 * 100

    def test_constructor(self):
        code = ControlFlowGraph()
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
        if sys.version_info > (3, 8):
            self.assertEqual(code.posonlyargcount, 0)
        self.assertEqual(code.kwonlyargcount, 1)
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
        code = ControlFlowGraph()
        code[0].append(Instr("LOAD_CONST", 0))

        block = code.add_block()
        self.assertEqual(len(code), 2)
        self.assertIs(block, code[1])

        code[1].append(Instr("LOAD_CONST", 2))
        self.assertBlocksEqual(code, [Instr("LOAD_CONST", 0)], [Instr("LOAD_CONST", 2)])

        del code[0]
        self.assertBlocksEqual(code, [Instr("LOAD_CONST", 2)])

        del code[0]
        self.assertEqual(len(code), 0)

    def test_setlineno(self):
        # x = 7
        # y = 8
        # z = 9
        code = Bytecode()
        code.first_lineno = 3
        code.extend(
            [
                Instr("LOAD_CONST", 7),
                Instr("STORE_NAME", "x"),
                SetLineno(4),
                Instr("LOAD_CONST", 8),
                Instr("STORE_NAME", "y"),
                SetLineno(5),
                Instr("LOAD_CONST", 9),
                Instr("STORE_NAME", "z"),
            ]
        )

        blocks = ControlFlowGraph.from_bytecode(code)
        self.assertBlocksEqual(
            blocks,
            [
                Instr("LOAD_CONST", 7),
                Instr("STORE_NAME", "x"),
                SetLineno(4),
                Instr("LOAD_CONST", 8),
                Instr("STORE_NAME", "y"),
                SetLineno(5),
                Instr("LOAD_CONST", 9),
                Instr("STORE_NAME", "z"),
            ],
        )

    def test_legalize(self):
        code = Bytecode()
        code.first_lineno = 3
        code.extend(
            [
                Instr("LOAD_CONST", 7),
                Instr("STORE_NAME", "x"),
                Instr("LOAD_CONST", 8, lineno=4),
                Instr("STORE_NAME", "y"),
                SetLineno(5),
                Instr("LOAD_CONST", 9, lineno=6),
                Instr("STORE_NAME", "z"),
            ]
        )

        blocks = ControlFlowGraph.from_bytecode(code)
        blocks.legalize()
        self.assertBlocksEqual(
            blocks,
            [
                Instr("LOAD_CONST", 7, lineno=3),
                Instr("STORE_NAME", "x", lineno=3),
                Instr("LOAD_CONST", 8, lineno=4),
                Instr("STORE_NAME", "y", lineno=4),
                Instr("LOAD_CONST", 9, lineno=5),
                Instr("STORE_NAME", "z", lineno=5),
            ],
        )

    def test_repr(self):
        r = repr(ControlFlowGraph())
        self.assertIn("ControlFlowGraph", r)
        self.assertIn("1", r)

    def test_to_bytecode(self):
        # if test:
        #     x = 2
        # x = 5
        blocks = ControlFlowGraph()
        blocks.add_block()
        blocks.add_block()
        blocks[0].extend(
            [
                Instr("LOAD_NAME", "test", lineno=1),
                Instr("POP_JUMP_IF_FALSE", blocks[2], lineno=1),
            ]
        )

        blocks[1].extend(
            [
                Instr("LOAD_CONST", 5, lineno=2),
                Instr("STORE_NAME", "x", lineno=2),
                Instr("JUMP_FORWARD", blocks[2], lineno=2),
            ]
        )

        blocks[2].extend(
            [
                Instr("LOAD_CONST", 7, lineno=3),
                Instr("STORE_NAME", "x", lineno=3),
                Instr("LOAD_CONST", None, lineno=3),
                Instr("RETURN_VALUE", lineno=3),
            ]
        )

        bytecode = blocks.to_bytecode()
        label = Label()
        self.assertEqual(
            bytecode,
            [
                Instr("LOAD_NAME", "test", lineno=1),
                Instr("POP_JUMP_IF_FALSE", label, lineno=1),
                Instr("LOAD_CONST", 5, lineno=2),
                Instr("STORE_NAME", "x", lineno=2),
                Instr("JUMP_FORWARD", label, lineno=2),
                label,
                Instr("LOAD_CONST", 7, lineno=3),
                Instr("STORE_NAME", "x", lineno=3),
                Instr("LOAD_CONST", None, lineno=3),
                Instr("RETURN_VALUE", lineno=3),
            ],
        )
        # FIXME: test other attributes

    def test_label_at_the_end(self):
        label = Label()
        code = Bytecode(
            [
                Instr("LOAD_NAME", "x"),
                Instr("UNARY_NOT"),
                Instr("POP_JUMP_IF_FALSE", label),
                Instr("LOAD_CONST", 9),
                Instr("STORE_NAME", "y"),
                label,
            ]
        )

        cfg = ControlFlowGraph.from_bytecode(code)
        self.assertBlocksEqual(
            cfg,
            [
                Instr("LOAD_NAME", "x"),
                Instr("UNARY_NOT"),
                Instr("POP_JUMP_IF_FALSE", cfg[2]),
            ],
            [Instr("LOAD_CONST", 9), Instr("STORE_NAME", "y")],
            [],
        )

    def test_from_bytecode(self):
        bytecode = Bytecode()
        label = Label()
        bytecode.extend(
            [
                Instr("LOAD_NAME", "test", lineno=1),
                Instr("POP_JUMP_IF_FALSE", label, lineno=1),
                Instr("LOAD_CONST", 5, lineno=2),
                Instr("STORE_NAME", "x", lineno=2),
                Instr("JUMP_FORWARD", label, lineno=2),
                # dead code!
                Instr("LOAD_CONST", 7, lineno=4),
                Instr("STORE_NAME", "x", lineno=4),
                Label(),  # unused label
                label,
                Label(),  # unused label
                Instr("LOAD_CONST", None, lineno=4),
                Instr("RETURN_VALUE", lineno=4),
            ]
        )

        blocks = ControlFlowGraph.from_bytecode(bytecode)
        label2 = blocks[3]
        self.assertBlocksEqual(
            blocks,
            [
                Instr("LOAD_NAME", "test", lineno=1),
                Instr("POP_JUMP_IF_FALSE", label2, lineno=1),
            ],
            [
                Instr("LOAD_CONST", 5, lineno=2),
                Instr("STORE_NAME", "x", lineno=2),
                Instr("JUMP_FORWARD", label2, lineno=2),
            ],
            [Instr("LOAD_CONST", 7, lineno=4), Instr("STORE_NAME", "x", lineno=4)],
            [Instr("LOAD_CONST", None, lineno=4), Instr("RETURN_VALUE", lineno=4)],
        )
        # FIXME: test other attributes

    def test_from_bytecode_loop(self):
        # for x in (1, 2, 3):
        #     if x == 2:
        #         break
        #     continue

        if sys.version_info < (3, 8):
            label_loop_start = Label()
            label_loop_exit = Label()
            label_loop_end = Label()

            code = Bytecode()
            code.extend(
                (
                    Instr("SETUP_LOOP", label_loop_end, lineno=1),
                    Instr("LOAD_CONST", (1, 2, 3), lineno=1),
                    Instr("GET_ITER", lineno=1),
                    label_loop_start,
                    Instr("FOR_ITER", label_loop_exit, lineno=1),
                    Instr("STORE_NAME", "x", lineno=1),
                    Instr("LOAD_NAME", "x", lineno=2),
                    Instr("LOAD_CONST", 2, lineno=2),
                    Instr("COMPARE_OP", Compare.EQ, lineno=2),
                    Instr("POP_JUMP_IF_FALSE", label_loop_start, lineno=2),
                    Instr("BREAK_LOOP", lineno=3),
                    Instr("JUMP_ABSOLUTE", label_loop_start, lineno=4),
                    Instr("JUMP_ABSOLUTE", label_loop_start, lineno=4),
                    label_loop_exit,
                    Instr("POP_BLOCK", lineno=4),
                    label_loop_end,
                    Instr("LOAD_CONST", None, lineno=4),
                    Instr("RETURN_VALUE", lineno=4),
                )
            )
            blocks = ControlFlowGraph.from_bytecode(code)

            expected = [
                [Instr("SETUP_LOOP", blocks[8], lineno=1)],
                [Instr("LOAD_CONST", (1, 2, 3), lineno=1), Instr("GET_ITER", lineno=1)],
                [Instr("FOR_ITER", blocks[7], lineno=1)],
                [
                    Instr("STORE_NAME", "x", lineno=1),
                    Instr("LOAD_NAME", "x", lineno=2),
                    Instr("LOAD_CONST", 2, lineno=2),
                    Instr("COMPARE_OP", Compare.EQ, lineno=2),
                    Instr("POP_JUMP_IF_FALSE", blocks[2], lineno=2),
                ],
                [Instr("BREAK_LOOP", lineno=3)],
                [Instr("JUMP_ABSOLUTE", blocks[2], lineno=4)],
                [Instr("JUMP_ABSOLUTE", blocks[2], lineno=4)],
                [Instr("POP_BLOCK", lineno=4)],
                [Instr("LOAD_CONST", None, lineno=4), Instr("RETURN_VALUE", lineno=4)],
            ]
            self.assertBlocksEqual(blocks, *expected)
        else:
            label_loop_start = Label()
            label_loop_exit = Label()

            code = Bytecode()
            code.extend(
                (
                    Instr("LOAD_CONST", (1, 2, 3), lineno=1),
                    Instr("GET_ITER", lineno=1),
                    label_loop_start,
                    Instr("FOR_ITER", label_loop_exit, lineno=1),
                    Instr("STORE_NAME", "x", lineno=1),
                    Instr("LOAD_NAME", "x", lineno=2),
                    Instr("LOAD_CONST", 2, lineno=2),
                    Instr("COMPARE_OP", Compare.EQ, lineno=2),
                    Instr("POP_JUMP_IF_FALSE", label_loop_start, lineno=2),
                    Instr("JUMP_ABSOLUTE", label_loop_exit, lineno=3),
                    Instr("JUMP_ABSOLUTE", label_loop_start, lineno=4),
                    Instr("JUMP_ABSOLUTE", label_loop_start, lineno=4),
                    label_loop_exit,
                    Instr("LOAD_CONST", None, lineno=4),
                    Instr("RETURN_VALUE", lineno=4),
                )
            )
            blocks = ControlFlowGraph.from_bytecode(code)

            expected = [
                [Instr("LOAD_CONST", (1, 2, 3), lineno=1), Instr("GET_ITER", lineno=1)],
                [Instr("FOR_ITER", blocks[6], lineno=1)],
                [
                    Instr("STORE_NAME", "x", lineno=1),
                    Instr("LOAD_NAME", "x", lineno=2),
                    Instr("LOAD_CONST", 2, lineno=2),
                    Instr("COMPARE_OP", Compare.EQ, lineno=2),
                    Instr("POP_JUMP_IF_FALSE", blocks[1], lineno=2),
                ],
                [Instr("JUMP_ABSOLUTE", blocks[6], lineno=3)],
                [Instr("JUMP_ABSOLUTE", blocks[1], lineno=4)],
                [Instr("JUMP_ABSOLUTE", blocks[1], lineno=4)],
                [Instr("LOAD_CONST", None, lineno=4), Instr("RETURN_VALUE", lineno=4)],
            ]
            self.assertBlocksEqual(blocks, *expected)


class BytecodeBlocksFunctionalTests(TestCase):
    def test_eq(self):
        # compare codes with multiple blocks and labels,
        # Code.__eq__() renumbers labels to get equal labels
        source = "x = 1 if test else 2"
        code1 = disassemble(source)
        code2 = disassemble(source)
        self.assertEqual(code1, code2)

        # Type mismatch
        self.assertFalse(code1 == 1)

        # argnames mismatch
        cfg = ControlFlowGraph()
        cfg.argnames = 10
        self.assertFalse(code1 == cfg)

        # instr mismatch
        cfg = ControlFlowGraph()
        cfg.argnames = code1.argnames
        self.assertFalse(code1 == cfg)

    def check_getitem(self, code):
        # check internal Code block indexes (index by index, index by label)
        for block_index, block in enumerate(code):
            self.assertIs(code[block_index], block)
            self.assertIs(code[block], block)
            self.assertEqual(code.get_block_index(block), block_index)

    def test_delitem(self):
        cfg = ControlFlowGraph()
        b = cfg.add_block()
        del cfg[b]
        self.assertEqual(len(cfg.get_instructions()), 0)

    def sample_code(self):
        code = disassemble("x = 1", remove_last_return_none=True)
        self.assertBlocksEqual(
            code, [Instr("LOAD_CONST", 1, lineno=1), Instr("STORE_NAME", "x", lineno=1)]
        )
        return code

    def test_split_block(self):
        code = self.sample_code()
        code[0].append(Instr("NOP", lineno=1))

        label = code.split_block(code[0], 2)
        self.assertIs(label, code[1])
        self.assertBlocksEqual(
            code,
            [Instr("LOAD_CONST", 1, lineno=1), Instr("STORE_NAME", "x", lineno=1)],
            [Instr("NOP", lineno=1)],
        )
        self.check_getitem(code)

        label2 = code.split_block(code[0], 1)
        self.assertIs(label2, code[1])
        self.assertBlocksEqual(
            code,
            [Instr("LOAD_CONST", 1, lineno=1)],
            [Instr("STORE_NAME", "x", lineno=1)],
            [Instr("NOP", lineno=1)],
        )
        self.check_getitem(code)

        with self.assertRaises(TypeError):
            code.split_block(1, 1)

        with self.assertRaises(ValueError) as e:
            code.split_block(code[0], -2)
        self.assertIn("positive", e.exception.args[0])

    def test_split_block_end(self):
        code = self.sample_code()

        # split at the end of the last block requires to add a new empty block
        label = code.split_block(code[0], 2)
        self.assertIs(label, code[1])
        self.assertBlocksEqual(
            code,
            [Instr("LOAD_CONST", 1, lineno=1), Instr("STORE_NAME", "x", lineno=1)],
            [],
        )
        self.check_getitem(code)

        # split at the end of a block which is not the end doesn't require to
        # add a new block
        label = code.split_block(code[0], 2)
        self.assertIs(label, code[1])
        self.assertBlocksEqual(
            code,
            [Instr("LOAD_CONST", 1, lineno=1), Instr("STORE_NAME", "x", lineno=1)],
            [],
        )

    def test_split_block_dont_split(self):
        code = self.sample_code()

        # FIXME: is it really useful to support that?
        block = code.split_block(code[0], 0)
        self.assertIs(block, code[0])
        self.assertBlocksEqual(
            code, [Instr("LOAD_CONST", 1, lineno=1), Instr("STORE_NAME", "x", lineno=1)]
        )

    def test_split_block_error(self):
        code = self.sample_code()

        with self.assertRaises(ValueError):
            # invalid index
            code.split_block(code[0], 3)

    def test_to_code(self):
        # test resolution of jump labels
        bytecode = ControlFlowGraph()
        bytecode.first_lineno = 3
        bytecode.argcount = 3
        if sys.version_info > (3, 8):
            bytecode.posonlyargcount = 0
        bytecode.kwonlyargcount = 2
        bytecode.name = "func"
        bytecode.filename = "hello.py"
        bytecode.flags = 0x43
        bytecode.argnames = ("arg", "arg2", "arg3", "kwonly", "kwonly2")
        bytecode.docstring = None
        block0 = bytecode[0]
        block1 = bytecode.add_block()
        block2 = bytecode.add_block()
        block0.extend(
            [
                Instr("LOAD_FAST", "x", lineno=4),
                Instr("POP_JUMP_IF_FALSE", block2, lineno=4),
            ]
        )
        block1.extend(
            [Instr("LOAD_FAST", "arg", lineno=5), Instr("STORE_FAST", "x", lineno=5)]
        )
        block2.extend(
            [
                Instr("LOAD_CONST", 3, lineno=6),
                Instr("STORE_FAST", "x", lineno=6),
                Instr("LOAD_FAST", "x", lineno=7),
                Instr("RETURN_VALUE", lineno=7),
            ]
        )

        if WORDCODE:
            expected = (
                b"|\x05" b"r\x08" b"|\x00" b"}\x05" b"d\x01" b"}\x05" b"|\x05" b"S\x00"
            )
        else:
            expected = (
                b"|\x05\x00"
                b"r\x0c\x00"
                b"|\x00\x00"
                b"}\x05\x00"
                b"d\x01\x00"
                b"}\x05\x00"
                b"|\x05\x00"
                b"S"
            )

        code = bytecode.to_code()
        self.assertEqual(code.co_consts, (None, 3))
        self.assertEqual(code.co_argcount, 3)
        if sys.version_info > (3, 8):
            self.assertEqual(code.co_posonlyargcount, 0)
        self.assertEqual(code.co_kwonlyargcount, 2)
        self.assertEqual(code.co_nlocals, 6)
        self.assertEqual(code.co_stacksize, 1)
        # FIXME: don't use hardcoded constants
        self.assertEqual(code.co_flags, 0x43)
        self.assertEqual(code.co_code, expected)
        self.assertEqual(code.co_names, ())
        self.assertEqual(
            code.co_varnames, ("arg", "arg2", "arg3", "kwonly", "kwonly2", "x")
        )
        self.assertEqual(code.co_filename, "hello.py")
        self.assertEqual(code.co_name, "func")
        self.assertEqual(code.co_firstlineno, 3)

        # verify stacksize argument is honored
        explicit_stacksize = code.co_stacksize + 42
        code = bytecode.to_code(stacksize=explicit_stacksize)
        self.assertEqual(code.co_stacksize, explicit_stacksize)

    def test_get_block_index(self):
        blocks = ControlFlowGraph()
        block0 = blocks[0]
        block1 = blocks.add_block()
        block2 = blocks.add_block()
        self.assertEqual(blocks.get_block_index(block0), 0)
        self.assertEqual(blocks.get_block_index(block1), 1)
        self.assertEqual(blocks.get_block_index(block2), 2)

        other_block = BasicBlock()
        self.assertRaises(ValueError, blocks.get_block_index, other_block)


class CFGStacksizeComputationTests(TestCase):
    def check_stack_size(self, func):
        code = func.__code__
        bytecode = Bytecode.from_code(code)
        cfg = ControlFlowGraph.from_bytecode(bytecode)
        self.assertEqual(code.co_stacksize, cfg.compute_stacksize())

    def test_empty_code(self):
        cfg = ControlFlowGraph()
        del cfg[0]
        self.assertEqual(cfg.compute_stacksize(), 0)

    def test_handling_of_set_lineno(self):
        code = Bytecode()
        code.first_lineno = 3
        code.extend(
            [
                Instr("LOAD_CONST", 7),
                Instr("STORE_NAME", "x"),
                SetLineno(4),
                Instr("LOAD_CONST", 8),
                Instr("STORE_NAME", "y"),
                SetLineno(5),
                Instr("LOAD_CONST", 9),
                Instr("STORE_NAME", "z"),
            ]
        )
        self.assertEqual(code.compute_stacksize(), 1)

    def test_handling_of_extended_arg(self):
        code = Bytecode()
        code.first_lineno = 3
        code.extend(
            [
                Instr("LOAD_CONST", 7),
                Instr("STORE_NAME", "x"),
                Instr("EXTENDED_ARG", 1),
                Instr("LOAD_CONST", 8),
                Instr("STORE_NAME", "y"),
            ]
        )
        self.assertEqual(code.compute_stacksize(), 1)

    def test_invalid_stacksize(self):
        code = Bytecode()
        code.extend([Instr("STORE_NAME", "x")])
        with self.assertRaises(RuntimeError):
            code.compute_stacksize()

    def test_stack_size_computation_and(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            return arg1 and args  # Test JUMP_IF_FALSE_OR_POP

        self.check_stack_size(test)

    def test_stack_size_computation_or(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            return arg1 or args  # Test JUMP_IF_TRUE_OR_POP

        self.check_stack_size(test)

    def test_stack_size_computation_if_else(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            if args:
                return 0
            elif kwargs:
                return 1
            else:
                return 2

        self.check_stack_size(test)

    def test_stack_size_computation_for_loop_continue(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            for k in kwargs:
                if k in args:
                    continue
            else:
                return 1

        self.check_stack_size(test)

    def test_stack_size_computation_while_loop_break(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            while True:
                if arg1:
                    break

        self.check_stack_size(test)

    def test_stack_size_computation_with(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            with open(arg1) as f:
                return f.read()

        self.check_stack_size(test)

    def test_stack_size_computation_try_except(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            try:
                return args[0]
            except Exception:
                return 2

        self.check_stack_size(test)

    def test_stack_size_computation_try_finally(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            try:
                return args[0]
            finally:
                return 2

        self.check_stack_size(test)

    def test_stack_size_computation_try_except_finally(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            try:
                return args[0]
            except Exception:
                return 2
            finally:
                print("Interrupt")

        self.check_stack_size(test)

    def test_stack_size_computation_try_except_else_finally(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            try:
                return args[0]
            except Exception:
                return 2
            else:
                return arg1
            finally:
                print("Interrupt")

        self.check_stack_size(test)

    def test_stack_size_computation_nested_try_except_finally(self):
        def test(arg1, *args, **kwargs):  # pragma: no cover
            k = 1
            try:
                getattr(arg1, k)
            except AttributeError:
                pass
            except Exception:
                try:
                    assert False
                except Exception:
                    return 2
                finally:
                    print("unexpected")
            finally:
                print("attempted to get {}".format(k))

        self.check_stack_size(test)

    def test_stack_size_computation_nested_try_except_else_finally(self):
        def test(*args, **kwargs):
            try:
                v = args[1]
            except IndexError:
                try:
                    w = kwargs["value"]
                except KeyError:
                    return -1
                else:
                    return w
                finally:
                    print("second finally")
            else:
                return v
            finally:
                print("first finally")

        # A direct comparison of the stack depth fails because CPython
        # generate dead code that is used in stack computation.
        cpython_stacksize = test.__code__.co_stacksize
        test.__code__ = Bytecode.from_code(test.__code__).to_code()
        self.assertLessEqual(test.__code__.co_stacksize, cpython_stacksize)
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(test(1, 4), 4)
            self.assertEqual(stdout.getvalue(), "first finally\n")

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(test([], value=3), 3)
            self.assertEqual(stdout.getvalue(), "second finally\nfirst finally\n")

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(test([], name=None), -1)
            self.assertEqual(stdout.getvalue(), "second finally\nfirst finally\n")

    def test_stack_size_with_dead_code(self):
        # Simply demonstrate more directly the previously mentioned issue.
        def test(*args):  # pragma: no cover
            return 0
            try:
                a = args[0]
            except IndexError:
                return -1
            else:
                return a

        test.__code__ = Bytecode.from_code(test.__code__).to_code()
        self.assertEqual(test.__code__.co_stacksize, 1)
        self.assertEqual(test(1), 0)

    def test_huge_code_with_numerous_blocks(self):
        def base_func(x):
            pass

        def mk_if_then_else(depth):
            instructions = []
            for i in range(depth):
                label_else = Label()
                instructions.extend(
                    [
                        Instr("LOAD_FAST", "x"),
                        Instr("POP_JUMP_IF_FALSE", label_else),
                        Instr("LOAD_GLOBAL", "f{}".format(i)),
                        Instr("RETURN_VALUE"),
                        label_else,
                    ]
                )
            instructions.extend([Instr("LOAD_CONST", None), Instr("RETURN_VALUE")])
            return instructions

        bytecode = Bytecode(mk_if_then_else(5000))
        bytecode.compute_stacksize()

    def test_extended_arg_unpack_ex(self):
        def test():
            p = [1, 2, 3, 4, 5, 6]
            q, r, *s, t = p
            return q, r, s, t

        test.__code__ = ConcreteBytecode.from_code(test.__code__, extended_arg=True).to_code()
        self.assertEqual(test.__code__.co_stacksize, 6)
        self.assertEqual(test(), (1, 2, [3, 4, 5], 6))

    def test_expected_arg_with_many_consts(self):
        def test():
            var = 0
            var = 1
            var = 2
            var = 3
            var = 4
            var = 5
            var = 6
            var = 7
            var = 8
            var = 9
            var = 10
            var = 11
            var = 12
            var = 13
            var = 14
            var = 15
            var = 16
            var = 17
            var = 18
            var = 19
            var = 20
            var = 21
            var = 22
            var = 23
            var = 24
            var = 25
            var = 26
            var = 27
            var = 28
            var = 29
            var = 30
            var = 31
            var = 32
            var = 33
            var = 34
            var = 35
            var = 36
            var = 37
            var = 38
            var = 39
            var = 40
            var = 41
            var = 42
            var = 43
            var = 44
            var = 45
            var = 46
            var = 47
            var = 48
            var = 49
            var = 50
            var = 51
            var = 52
            var = 53
            var = 54
            var = 55
            var = 56
            var = 57
            var = 58
            var = 59
            var = 60
            var = 61
            var = 62
            var = 63
            var = 64
            var = 65
            var = 66
            var = 67
            var = 68
            var = 69
            var = 70
            var = 71
            var = 72
            var = 73
            var = 74
            var = 75
            var = 76
            var = 77
            var = 78
            var = 79
            var = 80
            var = 81
            var = 82
            var = 83
            var = 84
            var = 85
            var = 86
            var = 87
            var = 88
            var = 89
            var = 90
            var = 91
            var = 92
            var = 93
            var = 94
            var = 95
            var = 96
            var = 97
            var = 98
            var = 99
            var = 100
            var = 101
            var = 102
            var = 103
            var = 104
            var = 105
            var = 106
            var = 107
            var = 108
            var = 109
            var = 110
            var = 111
            var = 112
            var = 113
            var = 114
            var = 115
            var = 116
            var = 117
            var = 118
            var = 119
            var = 120
            var = 121
            var = 122
            var = 123
            var = 124
            var = 125
            var = 126
            var = 127
            var = 128
            var = 129
            var = 130
            var = 131
            var = 132
            var = 133
            var = 134
            var = 135
            var = 136
            var = 137
            var = 138
            var = 139
            var = 140
            var = 141
            var = 142
            var = 143
            var = 144
            var = 145
            var = 146
            var = 147
            var = 148
            var = 149
            var = 150
            var = 151
            var = 152
            var = 153
            var = 154
            var = 155
            var = 156
            var = 157
            var = 158
            var = 159
            var = 160
            var = 161
            var = 162
            var = 163
            var = 164
            var = 165
            var = 166
            var = 167
            var = 168
            var = 169
            var = 170
            var = 171
            var = 172
            var = 173
            var = 174
            var = 175
            var = 176
            var = 177
            var = 178
            var = 179
            var = 180
            var = 181
            var = 182
            var = 183
            var = 184
            var = 185
            var = 186
            var = 187
            var = 188
            var = 189
            var = 190
            var = 191
            var = 192
            var = 193
            var = 194
            var = 195
            var = 196
            var = 197
            var = 198
            var = 199
            var = 200
            var = 201
            var = 202
            var = 203
            var = 204
            var = 205
            var = 206
            var = 207
            var = 208
            var = 209
            var = 210
            var = 211
            var = 212
            var = 213
            var = 214
            var = 215
            var = 216
            var = 217
            var = 218
            var = 219
            var = 220
            var = 221
            var = 222
            var = 223
            var = 224
            var = 225
            var = 226
            var = 227
            var = 228
            var = 229
            var = 230
            var = 231
            var = 232
            var = 233
            var = 234
            var = 235
            var = 236
            var = 237
            var = 238
            var = 239
            var = 240
            var = 241
            var = 242
            var = 243
            var = 244
            var = 245
            var = 246
            var = 247
            var = 248
            var = 249
            var = 250
            var = 251
            var = 252
            var = 253
            var = 254
            var = 255
            var = 256
            var = 257
            var = 258
            var = 259

            return var

        test.__code__ = ConcreteBytecode.from_code(test.__code__, extended_arg=True).to_code()
        self.assertEqual(test.__code__.co_stacksize, 1)
        self.assertEqual(test(), 259)

    if sys.version_info > (3, 5):
        @unittest.expectedFailure
        def test_fail_extended_arg_jump(self):
            def test():
                var = None
                for _ in range(0, 1):
                    var = 0
                    var = 1
                    var = 2
                    var = 3
                    var = 4
                    var = 5
                    var = 6
                    var = 7
                    var = 8
                    var = 9
                    var = 10
                    var = 11
                    var = 12
                    var = 13
                    var = 14
                    var = 15
                    var = 16
                    var = 17
                    var = 18
                    var = 19
                    var = 20
                    var = 21
                    var = 22
                    var = 23
                    var = 24
                    var = 25
                    var = 26
                    var = 27
                    var = 28
                    var = 29
                    var = 30
                    var = 31
                    var = 32
                    var = 33
                    var = 34
                    var = 35
                    var = 36
                    var = 37
                    var = 38
                    var = 39
                    var = 40
                    var = 41
                    var = 42
                    var = 43
                    var = 44
                    var = 45
                    var = 46
                    var = 47
                    var = 48
                    var = 49
                    var = 50
                    var = 51
                    var = 52
                    var = 53
                    var = 54
                    var = 55
                    var = 56
                    var = 57
                    var = 58
                    var = 59
                    var = 60
                    var = 61
                    var = 62
                    var = 63
                    var = 64
                    var = 65
                    var = 66
                    var = 67
                    var = 68
                    var = 69
                    var = 70
                return var

            # Generate the bytecode with extended arguments
            bytecode = ConcreteBytecode.from_code(test.__code__, extended_arg=True)
            # This is where computation fails
            # It seems like it is caused by the split of blocks and a wrong start size
            # for one block.
            bytecode.to_code()


if __name__ == "__main__":
    unittest.main()  # pragma: no cover

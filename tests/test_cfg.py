#!/usr/bin/env python3
import asyncio
import contextlib
import inspect
import io
import opcode
import sys
import textwrap
import types
import unittest

from bytecode import (
    BasicBlock,
    Bytecode,
    Compare,
    ControlFlowGraph,
    Instr,
    Label,
    SetLineno,
    dump_bytecode,
)
from bytecode.concrete import OFFSET_AS_INSTRUCTION
from bytecode.utils import PY311, PY313

from . import TestCase, disassemble as _disassemble


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
            (block[-1].name == "RETURN_CONST" and block[-1].arg is None)
            if sys.version_info >= (3, 12)
            else (
                block[-2].name == "LOAD_CONST"
                and block[-2].arg is None
                and block[-1].name == "RETURN_VALUE"
            )
        )
        if not test:
            raise ValueError(
                "unable to find implicit RETURN_VALUE <None>: %s" % block[-2:]
            )
        if sys.version_info >= (3, 12):
            del block[-1]
        else:
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
        block.extend(
            [
                Instr(
                    "JUMP_FORWARD" if sys.version_info >= (3, 11) else "JUMP_ABSOLUTE",
                    block2,
                ),
                Instr("NOP"),
            ]
        )
        with self.assertRaises(ValueError):
            list(block)
        with self.assertRaises(ValueError):
            block.legalize(1)

        # jump target must be a BasicBlock
        block = BasicBlock()
        label = Label()
        block.extend(
            [
                Instr(
                    "JUMP_FORWARD" if sys.version_info >= (3, 11) else "JUMP_ABSOLUTE",
                    label,
                )
            ]
        )
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
                Instr(
                    "POP_JUMP_FORWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    blocks[2],
                    lineno=1,
                ),
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
                Instr(
                    "POP_JUMP_FORWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    label,
                    lineno=1,
                ),
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
                Instr(
                    "POP_JUMP_FORWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    label,
                ),
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
                Instr(
                    "POP_JUMP_FORWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    cfg[2],
                ),
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
                Instr(
                    "POP_JUMP_FORWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    label,
                    lineno=1,
                ),
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
                Instr(
                    "POP_JUMP_FORWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    label2,
                    lineno=1,
                ),
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
                Instr(
                    "POP_JUMP_BACKWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    label_loop_start,
                    lineno=2,
                ),
                Instr(
                    "JUMP_FORWARD" if sys.version_info >= (3, 11) else "JUMP_ABSOLUTE",
                    label_loop_exit,
                    lineno=3,
                ),
                Instr(
                    "JUMP_BACKWARD" if sys.version_info >= (3, 11) else "JUMP_ABSOLUTE",
                    label_loop_start,
                    lineno=4,
                ),
                Instr(
                    "JUMP_BACKWARD" if sys.version_info >= (3, 11) else "JUMP_ABSOLUTE",
                    label_loop_start,
                    lineno=4,
                ),
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
                Instr(
                    "POP_JUMP_BACKWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    blocks[1],
                    lineno=2,
                ),
            ],
            [
                Instr(
                    "JUMP_FORWARD" if sys.version_info >= (3, 11) else "JUMP_ABSOLUTE",
                    blocks[6],
                    lineno=3,
                )
            ],
            [
                Instr(
                    "JUMP_BACKWARD" if sys.version_info >= (3, 11) else "JUMP_ABSOLUTE",
                    blocks[1],
                    lineno=4,
                )
            ],
            [
                Instr(
                    "JUMP_BACKWARD" if sys.version_info >= (3, 11) else "JUMP_ABSOLUTE",
                    blocks[1],
                    lineno=4,
                )
            ],
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

    def test_eq_with_try_except(self):
        source = "try:\n  x = 1\nexcept Exception:\n  pass\nfinally:\n  print()"
        code1 = disassemble(source)
        code2 = disassemble(source)
        self.assertEqual(code1, code2)

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
        self.assertEqual(len(cfg._get_instructions()), 0)

    def sample_code(self):
        code = disassemble("x = 1", remove_last_return_none=True)
        self.assertBlocksEqual(
            code,
            ([Instr("RESUME", 0, lineno=0)] if sys.version_info >= (3, 11) else [])
            + [Instr("LOAD_CONST", 1, lineno=1), Instr("STORE_NAME", "x", lineno=1)],
        )
        if sys.version_info >= (3, 11):
            del code[0][0]
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
                *([Instr("TO_BOOL", lineno=4)] if PY313 else []),
                Instr(
                    "POP_JUMP_FORWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    block2,
                    lineno=4,
                ),
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

        if PY313:
            expected = bytes(
                (
                    opcode.opmap["LOAD_FAST"],
                    5,
                    opcode.opmap["TO_BOOL"],
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    opcode.opmap["POP_JUMP_IF_FALSE"],
                    2,
                    0,
                    0,
                    opcode.opmap["LOAD_FAST"],
                    0,
                    opcode.opmap["STORE_FAST"],
                    5,
                    opcode.opmap["LOAD_CONST"],
                    1,
                    opcode.opmap["STORE_FAST"],
                    5,
                    opcode.opmap["LOAD_FAST"],
                    5,
                    opcode.opmap["RETURN_VALUE"],
                    0,
                )
            )
        elif PY311:
            # jump is relative not absolute
            expected = b"|\x05r\x02|\x00}\x05d\x01}\x05|\x05S\x00"
        elif OFFSET_AS_INSTRUCTION:
            # The argument of the jump is divided by 2
            expected = b"|\x05r\x04|\x00}\x05d\x01}\x05|\x05S\x00"
        else:
            expected = b"|\x05r\x08|\x00}\x05d\x01}\x05|\x05S\x00"

        code = bytecode.to_code()
        self.assertEqual(code.co_consts, (None, 3))
        self.assertEqual(code.co_argcount, 3)
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
        code = bytecode.to_code(
            stacksize=explicit_stacksize, compute_exception_stack_depths=False
        )
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

    def test_get_dead_blocks(self):
        def condition():
            pass

        def test():
            if condition():
                print("1")
            else:
                print("2")

        bytecode = Bytecode.from_code(test.__code__)
        cfg = ControlFlowGraph.from_bytecode(bytecode)
        assert len(cfg.get_dead_blocks()) == 0


class CFGStacksizeComputationTests(TestCase):
    def check_stack_size(self, func):
        code = func.__code__
        bytecode = Bytecode.from_code(code)
        cfg = ControlFlowGraph.from_bytecode(bytecode)
        as_code = cfg.to_code(check_pre_and_post=False)
        self.assertCodeObjectEqual(code, as_code)
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
                return 2  # noqa

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
                    raise RuntimeError
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
            a = 0
            return a
            try:
                a = args[0]
            except IndexError:
                return -1
            else:
                return a

        test.__code__ = Bytecode.from_code(test.__code__).to_code()
        self.assertEqual(test.__code__.co_stacksize, 1)
        self.assertEqual(test(1), 0)

    def test_stack_size_with_dead_code2(self):
        # See GH #118
        source = """
        try:
            pass
        except Exception as e:
            pass
        """
        source = textwrap.dedent(source).strip()
        code = compile(source, "<string>", "exec")
        bytecode = Bytecode.from_code(code)
        cfg = ControlFlowGraph.from_bytecode(bytecode)
        cfg.to_bytecode()

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
                        Instr(
                            "POP_JUMP_FORWARD_IF_FALSE"
                            if (3, 12) > sys.version_info >= (3, 11)
                            else "POP_JUMP_IF_FALSE",
                            label_else,
                        ),
                        Instr(
                            "LOAD_GLOBAL",
                            (False, f"f{i}")
                            if sys.version_info >= (3, 11)
                            else f"f{i}",
                        ),
                        Instr("RETURN_VALUE"),
                        label_else,
                    ]
                )
            instructions.extend([Instr("LOAD_CONST", None), Instr("RETURN_VALUE")])
            return instructions

        bytecode = Bytecode(mk_if_then_else(5000))
        bytecode.compute_stacksize()


class CFGRoundTripTests(TestCase):
    def test_roundtrip_exception_handling(self):
        from . import exception_handling_cases as ehc

        for f in ehc.TEST_CASES:
            # 3.12 use one less exception table entry causing to optimize this case
            # less than we could otherwise
            if sys.version_info >= (3, 12) and f.__name__ == "try_except_finally":
                continue
            print(f.__name__)
            with self.subTest(f.__name__):
                origin = f.__code__
                print("Bytecode:")
                bytecode = Bytecode.from_code(
                    f.__code__, conserve_exception_block_stackdepth=True
                )
                dump_bytecode(bytecode)
                print()
                print("CFG:")
                cfg = ControlFlowGraph.from_bytecode(bytecode)
                dump_bytecode(cfg)
                as_code = cfg.to_code()
                self.assertCodeObjectEqual(origin, as_code)
                if inspect.iscoroutinefunction(f):
                    if sys.version_info >= (3, 10):
                        asyncio.run(f())
                else:
                    f()

    def test_cellvar_freevar_roundtrip(self):
        from . import cell_free_vars_cases as cfc

        def recompile_code_and_inner(code):
            cfg = ControlFlowGraph.from_bytecode(Bytecode.from_code(code))
            for block in cfg:
                for instr in block:
                    if isinstance(instr.arg, types.CodeType):
                        instr.arg = recompile_code_and_inner(instr.arg)
            as_code = cfg.to_code()
            self.assertCodeObjectEqual(code, as_code)
            return as_code

        for f in cfc.TEST_CASES:
            print(f.__name__)
            with self.subTest(f.__name__):
                origin = f.__code__
                f.__code__ = recompile_code_and_inner(origin)
                while callable(f := f()):
                    pass


if __name__ == "__main__":
    unittest.main()  # pragma: no cover

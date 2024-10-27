#!/usr/bin/env python3
import asyncio
import dis
import inspect
import opcode
import sys
import textwrap
import types
import unittest

from bytecode import (
    UNSET,
    Bytecode,
    CellVar,
    CompilerFlags,
    ConcreteBytecode,
    ConcreteInstr,
    FreeVar,
    Instr,
    Label,
    SetLineno,
)
from bytecode.concrete import OFFSET_AS_INSTRUCTION, ExceptionTableEntry
from bytecode.utils import PY313

from . import TestCase, get_code


class ConcreteInstrTests(TestCase):
    def test_constructor(self):
        with self.assertRaises(ValueError):
            # need an argument
            ConcreteInstr("LOAD_CONST")
        with self.assertRaises(ValueError):
            # must not have an argument
            ConcreteInstr("ROT_TWO", 33)

        # invalid argument
        with self.assertRaises(TypeError):
            ConcreteInstr("LOAD_CONST", 1.0)
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", -1)
        with self.assertRaises(TypeError):
            ConcreteInstr("LOAD_CONST", 5, lineno=1.0)
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", 5, lineno=-1)

        # test maximum argument
        with self.assertRaises(ValueError):
            ConcreteInstr("LOAD_CONST", 2147483647 + 1)
        instr = ConcreteInstr("LOAD_CONST", 2147483647)
        self.assertEqual(instr.arg, 2147483647)

        # test meaningless extended args
        instr = ConcreteInstr("LOAD_FAST", 8, lineno=3, extended_args=1)
        self.assertEqual(instr.name, "LOAD_FAST")
        self.assertEqual(instr.arg, 8)
        self.assertEqual(instr.lineno, 3)
        self.assertEqual(instr.size, 4)

    def test_attr(self):
        instr = ConcreteInstr("LOAD_CONST", 5, lineno=12)
        self.assertEqual(instr.name, "LOAD_CONST")
        self.assertEqual(instr.opcode, opcode.opmap["LOAD_CONST"])
        self.assertEqual(instr.arg, 5)
        self.assertEqual(instr.lineno, 12)
        self.assertEqual(instr.size, 2)

    def test_set(self):
        instr = ConcreteInstr("LOAD_CONST", 5, lineno=3)

        instr.set("NOP")
        self.assertEqual(instr.name, "NOP")
        self.assertIs(instr.arg, UNSET)
        self.assertEqual(instr.lineno, 3)

        instr.set("LOAD_FAST", 8)
        self.assertEqual(instr.name, "LOAD_FAST")
        self.assertEqual(instr.arg, 8)
        self.assertEqual(instr.lineno, 3)

        # invalid
        with self.assertRaises(ValueError):
            instr.set("LOAD_CONST")
        with self.assertRaises(ValueError):
            instr.set("NOP", 5)

    def test_set_attr(self):
        instr = ConcreteInstr("LOAD_CONST", 5, lineno=12)

        # operator name
        instr.name = "LOAD_FAST"
        self.assertEqual(instr.name, "LOAD_FAST")
        self.assertEqual(instr.opcode, opcode.opmap["LOAD_FAST"])
        self.assertRaises(TypeError, setattr, instr, "name", 3)
        self.assertRaises(ValueError, setattr, instr, "name", "xxx")

        # operator code
        instr.opcode = opcode.opmap["LOAD_CONST"]
        self.assertEqual(instr.name, "LOAD_CONST")
        self.assertEqual(instr.opcode, opcode.opmap["LOAD_CONST"])
        self.assertRaises(ValueError, setattr, instr, "opcode", -12)
        self.assertRaises(TypeError, setattr, instr, "opcode", "abc")

        # extended argument
        instr.arg = 0x1234ABCD
        self.assertEqual(instr.arg, 0x1234ABCD)
        self.assertEqual(instr.size, 8)

        # small argument
        instr.arg = 0
        self.assertEqual(instr.arg, 0)
        self.assertEqual(instr.size, 2)

        # invalid argument
        self.assertRaises(ValueError, setattr, instr, "arg", -1)
        self.assertRaises(ValueError, setattr, instr, "arg", 2147483647 + 1)

        # size attribute is read-only
        self.assertRaises(AttributeError, setattr, instr, "size", 3)

        # lineno
        instr.lineno = 33
        self.assertEqual(instr.lineno, 33)
        self.assertRaises(TypeError, setattr, instr, "lineno", 1.0)
        self.assertRaises(ValueError, setattr, instr, "lineno", -1)

    def test_size(self):
        self.assertEqual(ConcreteInstr("LOAD_CONST", 3).size, 2)
        self.assertEqual(ConcreteInstr("LOAD_CONST", 0x1234ABCD).size, 8)

    def test_disassemble(self):
        code = bytes((opcode.opmap["NOP"], 0, opcode.opmap["LOAD_CONST"], 3))
        instr = ConcreteInstr.disassemble(1, code, 0)
        self.assertEqual(instr, ConcreteInstr("NOP", lineno=1))

        instr = ConcreteInstr.disassemble(2, code, 1 if OFFSET_AS_INSTRUCTION else 2)
        self.assertEqual(instr, ConcreteInstr("LOAD_CONST", 3, lineno=2))

        code = bytes(
            (
                opcode.EXTENDED_ARG,
                0x12,
                opcode.EXTENDED_ARG,
                0x34,
                opcode.EXTENDED_ARG,
                0xAB,
                instr.opcode,
                0xCD,
            )
        )

        instr = ConcreteInstr.disassemble(3, code, 0)
        self.assertEqual(instr, ConcreteInstr("EXTENDED_ARG", 0x12, lineno=3))

    def test_assemble(self):
        instr = ConcreteInstr("NOP")
        self.assertEqual(instr.assemble(), bytes((instr.opcode, 0)))

        instr = ConcreteInstr("LOAD_CONST", 3)
        self.assertEqual(instr.assemble(), bytes((instr.opcode, 3)))

        instr = ConcreteInstr("LOAD_CONST", 0x1234ABCD)
        self.assertEqual(
            instr.assemble(),
            bytes(
                (
                    opcode.EXTENDED_ARG,
                    0x12,
                    opcode.EXTENDED_ARG,
                    0x34,
                    opcode.EXTENDED_ARG,
                    0xAB,
                    instr.opcode,
                    0xCD,
                )
            ),
        )

        instr = ConcreteInstr("LOAD_CONST", 3, extended_args=1)
        self.assertEqual(
            instr.assemble(),
            bytes((opcode.EXTENDED_ARG, 0, instr.opcode, 3)),
        )

    def test_get_jump_target(self):
        if sys.version_info < (3, 11):
            jump_abs = ConcreteInstr("JUMP_ABSOLUTE", 3)
            self.assertEqual(jump_abs.get_jump_target(100), 3)

        jump_forward = ConcreteInstr("JUMP_FORWARD", 5)
        self.assertEqual(
            jump_forward.get_jump_target(10), 16 if OFFSET_AS_INSTRUCTION else 17
        )


class ConcreteBytecodeTests(TestCase):
    def test_repr(self):
        r = repr(ConcreteBytecode())
        self.assertIn("ConcreteBytecode", r)
        self.assertIn("0", r)

    def test_exception_table_repr(self):
        t = ExceptionTableEntry(0, 1, 2, 3, True)
        self.assertSequenceEqual(
            repr(t),
            (
                "ExceptionTableEntry("
                "start_offset=0, "
                "stop_offset=1, "
                "target=2, "
                "stack_depth=3, "
                "push_lasti=True"
            ),
        )

    def test_eq(self):
        code = ConcreteBytecode()
        self.assertFalse(code == 1)

        for name, val in (
            ("names", ["a"]),
            ("varnames", ["a"]),
            ("consts", [1]),
            ("argcount", 1),
            ("kwonlyargcount", 2),
            ("flags", CompilerFlags(CompilerFlags.GENERATOR)),
            ("first_lineno", 10),
            ("filename", "xxxx.py"),
            ("name", "__x"),
            ("docstring", "x-x-x"),
            ("cellvars", [CellVar("x")]),
            ("freevars", [FreeVar("x")]),
        ):
            c = ConcreteBytecode()
            setattr(c, name, val)
            # For obscure reasons using assertNotEqual here fail
            self.assertFalse(code == c)

        c = ConcreteBytecode()
        c.posonlyargcount = 10
        self.assertFalse(code == c)

        c = ConcreteBytecode()
        c.consts = [1]
        code.consts = [1]
        c.append(ConcreteInstr("LOAD_CONST", 0))
        self.assertFalse(code == c)

    def test_attr(self):
        code_obj = get_code("x = 5")
        code = ConcreteBytecode.from_code(code_obj)
        self.assertEqual(code.consts, [5, None])
        self.assertEqual(code.names, ["x"])
        self.assertEqual(code.varnames, [])
        self.assertEqual(code.freevars, [])
        self.assertInstructionListEqual(
            list(code),
            (
                [ConcreteInstr("RESUME", 0, lineno=0)]
                if sys.version_info >= (3, 11)
                else []
            )
            + [
                ConcreteInstr("LOAD_CONST", 0, lineno=1),
                ConcreteInstr("STORE_NAME", 0, lineno=1),
            ]
            + (
                [ConcreteInstr("RETURN_CONST", 1, lineno=1)]
                if sys.version_info >= (3, 12)
                else [
                    ConcreteInstr("LOAD_CONST", 1, lineno=1),
                    ConcreteInstr("RETURN_VALUE", lineno=1),
                ]
            ),
        )
        # FIXME: test other attributes

    def test_invalid_types(self):
        code = ConcreteBytecode()
        code.append(Label())
        with self.assertRaises(ValueError):
            list(code)
        with self.assertRaises(ValueError):
            code.legalize()
        with self.assertRaises(ValueError):
            ConcreteBytecode([Label()])

    def test_to_code_lnotab(self):
        # We use an actual function for the simple case to
        # ensure we get lnotab right
        def f():
            #
            #
            x = 7  # noqa
            y = 8  # noqa
            z = 9  # noqa

        fl = f.__code__.co_firstlineno
        concrete = ConcreteBytecode()
        concrete.consts = [None, 7, 8, 9]
        concrete.varnames = ["x", "y", "z"]
        concrete.first_lineno = fl
        concrete.extend(
            (
                [ConcreteInstr("RESUME", 0), SetLineno(1)]
                if sys.version_info >= (3, 11)
                else []
            )
            + [
                SetLineno(fl + 3),
                ConcreteInstr("LOAD_CONST", 1),
                ConcreteInstr("STORE_FAST", 0),
                SetLineno(fl + 4),
                ConcreteInstr("LOAD_CONST", 2),
                ConcreteInstr("STORE_FAST", 1),
                SetLineno(fl + 5),
                ConcreteInstr("LOAD_CONST", 3),
                ConcreteInstr("STORE_FAST", 2),
            ]
            + (
                [ConcreteInstr("RETURN_CONST", 0)]
                if sys.version_info >= (3, 12)
                else [
                    ConcreteInstr("LOAD_CONST", 0),
                    ConcreteInstr("RETURN_VALUE"),
                ]
            )
        )

        code = concrete.to_code()
        self.assertSequenceEqual(code.co_code, f.__code__.co_code)
        if sys.version_info >= (3, 11):
            # Offset cannot be right so only check the lines
            self.assertSequenceEqual(
                list(dis.findlinestarts(code)), list(dis.findlinestarts(f.__code__))
            )
        else:
            self.assertEqual(code.co_lnotab, f.__code__.co_lnotab)
            if sys.version_info >= (3, 10):
                self.assertEqual(code.co_linetable, f.__code__.co_linetable)

    def test_negative_lnotab(self):
        # x = 7
        # y = 8
        concrete = ConcreteBytecode(
            [
                ConcreteInstr("LOAD_CONST", 0),
                ConcreteInstr("STORE_NAME", 0),
                # line number goes backward!
                SetLineno(2),
                ConcreteInstr("LOAD_CONST", 1),
                ConcreteInstr("STORE_NAME", 1),
            ]
        )
        concrete.consts = [7, 8]
        concrete.names = ["x", "y"]
        concrete.first_lineno = 5

        code = concrete.to_code()
        expected = bytes(
            (
                opcode.opmap["LOAD_CONST"],
                0,
                opcode.opmap["STORE_NAME"],
                0,
                opcode.opmap["LOAD_CONST"],
                1,
                opcode.opmap["STORE_NAME"],
                1,
            )
        )
        self.assertEqual(code.co_code, expected)
        self.assertEqual(code.co_firstlineno, 5)
        if sys.version_info >= (3, 12):
            self.skipTest("lnotab is deprecated in Python 3.12+")
        self.assertEqual(code.co_lnotab, b"\x04\xfd")

    def test_extended_lnotab(self):
        # x = 7
        # 200 blank lines
        # y = 8
        concrete = ConcreteBytecode(
            [
                ConcreteInstr("LOAD_CONST", 0),
                SetLineno(1 + 128),
                ConcreteInstr("STORE_NAME", 0),
                # line number goes backward!
                SetLineno(1 + 129),
                ConcreteInstr("LOAD_CONST", 1),
                SetLineno(1),
                ConcreteInstr("STORE_NAME", 1),
            ]
        )
        concrete.consts = [7, 8]
        concrete.names = ["x", "y"]
        concrete.first_lineno = 1

        code = concrete.to_code()
        expected = bytes(
            (
                opcode.opmap["LOAD_CONST"],
                0,
                opcode.opmap["STORE_NAME"],
                0,
                opcode.opmap["LOAD_CONST"],
                1,
                opcode.opmap["STORE_NAME"],
                1,
            )
        )
        self.assertEqual(code.co_code, expected)
        self.assertEqual(code.co_firstlineno, 1)
        if sys.version_info >= (3, 11):
            self.assertSequenceEqual(
                list(code.co_positions()),
                [
                    (1, 1, None, None),
                    (129, 129, None, None),
                    (130, 130, None, None),
                    (1, 1, None, None),
                ],
            )
        else:
            self.assertEqual(
                code.co_lnotab, b"\x02\x7f\x00\x01\x02\x01\x02\x80\x00\xff"
            )

    def test_extended_lnotab2(self):
        # x = 7
        # 200 blank lines
        # y = 8
        base_code = compile("x = 7" + "\n" * 200 + "y = 8", "", "exec")
        concrete = ConcreteBytecode(
            (
                [ConcreteInstr("RESUME", 0, lineno=0), SetLineno(1)]
                if sys.version_info >= (3, 11)
                else []
            )
            + [
                ConcreteInstr("LOAD_CONST", 0),
                ConcreteInstr("STORE_NAME", 0),
                SetLineno(201),
                ConcreteInstr("LOAD_CONST", 1),
                ConcreteInstr("STORE_NAME", 1),
            ]
            + (
                [ConcreteInstr("RETURN_CONST", 2)]
                if sys.version_info >= (3, 12)
                else [
                    ConcreteInstr("LOAD_CONST", 2),
                    ConcreteInstr("RETURN_VALUE"),
                ]
            )
        )
        concrete.consts = [None, 7, 8]
        concrete.names = ["x", "y"]
        concrete.first_lineno = 1

        code = concrete.to_code()
        self.assertSequenceEqual(code.co_code, base_code.co_code)
        self.assertEqual(code.co_firstlineno, base_code.co_firstlineno)
        if sys.version_info >= (3, 11):
            # Offset cannot be right so only check the lines
            self.assertSequenceEqual(
                list(dis.findlinestarts(code)), list(dis.findlinestarts(base_code))
            )
        else:
            self.assertSequenceEqual(code.co_lnotab, base_code.co_lnotab)
            if sys.version_info >= (3, 10):
                self.assertSequenceEqual(code.co_linetable, base_code.co_linetable)

    def test_to_bytecode_consts(self):
        # x = -0.0
        # x = +0.0
        #
        # code optimized by the CPython 3.6 peephole optimizer which emits
        # duplicated constants (0.0 is twice in consts).
        code = ConcreteBytecode()
        code.consts = [0.0, None, -0.0, 0.0]
        code.names = ["x", "y"]
        code.extend(
            [
                ConcreteInstr("LOAD_CONST", 2, lineno=1),
                ConcreteInstr("STORE_NAME", 0, lineno=1),
                ConcreteInstr("LOAD_CONST", 3, lineno=2),
                ConcreteInstr("STORE_NAME", 1, lineno=2),
                ConcreteInstr("LOAD_CONST", 1, lineno=2),
                ConcreteInstr("RETURN_VALUE", lineno=2),
            ]
        )

        code = code.to_bytecode().to_concrete_bytecode()
        # the conversion changes the constant order: the order comes from
        # the order of LOAD_CONST instructions
        self.assertEqual(code.consts, [-0.0, 0.0, None])
        code.names = ["x", "y"]
        self.assertListEqual(
            list(code),
            [
                ConcreteInstr("LOAD_CONST", 0, lineno=1),
                ConcreteInstr("STORE_NAME", 0, lineno=1),
                ConcreteInstr("LOAD_CONST", 1, lineno=2),
                ConcreteInstr("STORE_NAME", 1, lineno=2),
                ConcreteInstr("LOAD_CONST", 2, lineno=2),
                ConcreteInstr("RETURN_VALUE", lineno=2),
            ],
        )

    def test_cellvar(self):
        concrete = ConcreteBytecode()
        concrete.cellvars = ["x"]
        concrete.append(ConcreteInstr("LOAD_DEREF", 0))
        code = concrete.to_code()

        concrete = ConcreteBytecode.from_code(code)
        self.assertEqual(concrete.cellvars, ["x"])
        self.assertEqual(concrete.freevars, [])
        self.assertInstructionListEqual(
            list(concrete), [ConcreteInstr("LOAD_DEREF", 0, lineno=1)]
        )

        bytecode = concrete.to_bytecode()
        self.assertEqual(bytecode.cellvars, ["x"])
        self.assertInstructionListEqual(
            list(bytecode), [Instr("LOAD_DEREF", CellVar("x"), lineno=1)]
        )

    def test_freevar(self):
        concrete = ConcreteBytecode()
        concrete.freevars = ["x"]
        concrete.append(ConcreteInstr("LOAD_DEREF", 0))
        code = concrete.to_code()

        concrete = ConcreteBytecode.from_code(code)
        self.assertEqual(concrete.cellvars, [])
        self.assertEqual(concrete.freevars, ["x"])
        self.assertInstructionListEqual(
            list(concrete), [ConcreteInstr("LOAD_DEREF", 0, lineno=1)]
        )

        bytecode = concrete.to_bytecode()
        self.assertEqual(bytecode.cellvars, [])
        self.assertInstructionListEqual(
            list(bytecode), [Instr("LOAD_DEREF", FreeVar("x"), lineno=1)]
        )

    def test_cellvar_freevar(self):
        concrete = ConcreteBytecode()
        concrete.cellvars = ["cell"]
        concrete.freevars = ["free"]
        concrete.append(ConcreteInstr("LOAD_DEREF", 0))
        concrete.append(ConcreteInstr("LOAD_DEREF", 1))
        code = concrete.to_code()

        concrete = ConcreteBytecode.from_code(code)
        self.assertEqual(concrete.cellvars, ["cell"])
        self.assertEqual(concrete.freevars, ["free"])
        self.assertInstructionListEqual(
            list(concrete),
            [
                ConcreteInstr("LOAD_DEREF", 0, lineno=1),
                ConcreteInstr("LOAD_DEREF", 1, lineno=1),
            ],
        )

        bytecode = concrete.to_bytecode()
        self.assertEqual(bytecode.cellvars, ["cell"])
        self.assertInstructionListEqual(
            list(bytecode),
            [
                Instr("LOAD_DEREF", CellVar("cell"), lineno=1),
                Instr("LOAD_DEREF", FreeVar("free"), lineno=1),
            ],
        )

    def test_load_classderef(self):
        i_name = (
            "LOAD_FROM_DICT_OR_DEREF"
            if sys.version_info >= (3, 12)
            else "LOAD_CLASSDEREF"
        )
        i_arg = 2 if sys.version_info >= (3, 11) else 1
        concrete = ConcreteBytecode()
        concrete.varnames = ["a"]
        concrete.cellvars = ["__class__"]
        concrete.freevars = ["__class__"]
        concrete.extend(
            [
                ConcreteInstr("LOAD_FAST", 0, lineno=1),
                ConcreteInstr(i_name, i_arg, lineno=1),
                ConcreteInstr("STORE_DEREF", i_arg, lineno=1),
            ]
        )

        bytecode = concrete.to_bytecode()
        self.assertEqual(bytecode.freevars, ["__class__"])
        self.assertEqual(bytecode.cellvars, ["__class__"])
        self.assertInstructionListEqual(
            list(bytecode),
            [
                Instr("LOAD_FAST", "a", lineno=1),
                Instr(i_name, FreeVar("__class__"), lineno=1),
                Instr("STORE_DEREF", FreeVar("__class__"), lineno=1),
            ],
        )

        concrete = bytecode.to_concrete_bytecode()
        self.assertEqual(concrete.freevars, ["__class__"])
        self.assertEqual(concrete.cellvars, ["__class__"])
        self.assertInstructionListEqual(
            list(concrete),
            [
                ConcreteInstr("LOAD_FAST", 1, lineno=1),
                ConcreteInstr(i_name, i_arg, lineno=1),
                ConcreteInstr("STORE_DEREF", i_arg, lineno=1),
            ],
        )

        code = concrete.to_code()
        self.assertEqual(code.co_freevars, ("__class__",))
        self.assertEqual(code.co_cellvars, ("__class__",))
        self.assertEqual(
            code.co_code,
            bytes(
                [
                    opcode.opmap["LOAD_FAST"],
                    0,
                    opcode.opmap[i_name],
                    i_arg,
                    opcode.opmap["STORE_DEREF"],
                    i_arg,
                ]
            ),
        )

    def test_explicit_stacksize(self):
        # Passing stacksize=... to ConcreteBytecode.to_code should result in a
        # code object with the specified stacksize.  We pass some silly values
        # and assert that they are honored.
        code_obj = get_code("print('%s' % (a,b,c))")
        original_stacksize = code_obj.co_stacksize
        concrete = ConcreteBytecode.from_code(code_obj)

        # First with something bigger than necessary.
        explicit_stacksize = original_stacksize + 42
        new_code_obj = concrete.to_code(
            stacksize=explicit_stacksize, compute_exception_stack_depths=False
        )
        self.assertEqual(new_code_obj.co_stacksize, explicit_stacksize)

        # Then with something bogus.  We probably don't want to advertise this
        # in the documentation.  If this fails then decide if it's for good
        # reason, and remove if so.
        explicit_stacksize = code_obj.co_stacksize - 1
        new_code_obj = concrete.to_code(
            stacksize=explicit_stacksize, compute_exception_stack_depths=False
        )
        self.assertEqual(new_code_obj.co_stacksize, explicit_stacksize)

    def test_legalize(self):
        concrete = ConcreteBytecode()
        concrete.first_lineno = 3
        concrete.consts = [7, 8, 9]
        concrete.names = ["x", "y", "z"]
        concrete.extend(
            [
                ConcreteInstr("LOAD_CONST", 0),
                ConcreteInstr("STORE_NAME", 0),
                ConcreteInstr("LOAD_CONST", 1, lineno=4),
                ConcreteInstr("STORE_NAME", 1),
                SetLineno(5),
                ConcreteInstr("LOAD_CONST", 2, lineno=6),
                ConcreteInstr("STORE_NAME", 2),
            ]
        )

        concrete.legalize()
        self.assertInstructionListEqual(
            list(concrete),
            [
                ConcreteInstr("LOAD_CONST", 0, lineno=3),
                ConcreteInstr("STORE_NAME", 0, lineno=3),
                ConcreteInstr("LOAD_CONST", 1, lineno=4),
                ConcreteInstr("STORE_NAME", 1, lineno=4),
                ConcreteInstr("LOAD_CONST", 2, lineno=5),
                ConcreteInstr("STORE_NAME", 2, lineno=5),
            ],
        )

    def test_slice(self):
        concrete = ConcreteBytecode()
        concrete.first_lineno = 3
        concrete.consts = [7, 8, 9]
        concrete.names = ["x", "y", "z"]
        concrete.extend(
            [
                ConcreteInstr("LOAD_CONST", 0),
                ConcreteInstr("STORE_NAME", 0),
                SetLineno(4),
                ConcreteInstr("LOAD_CONST", 1),
                ConcreteInstr("STORE_NAME", 1),
                SetLineno(5),
                ConcreteInstr("LOAD_CONST", 2),
                ConcreteInstr("STORE_NAME", 2),
            ]
        )
        self.assertInstructionListEqual(concrete, concrete[:])

    def test_copy(self):
        concrete = ConcreteBytecode()
        concrete.first_lineno = 3
        concrete.consts = [7, 8, 9]
        concrete.names = ["x", "y", "z"]
        concrete.extend(
            [
                ConcreteInstr("LOAD_CONST", 0),
                ConcreteInstr("STORE_NAME", 0),
                SetLineno(4),
                ConcreteInstr("LOAD_CONST", 1),
                ConcreteInstr("STORE_NAME", 1),
                SetLineno(5),
                ConcreteInstr("LOAD_CONST", 2),
                ConcreteInstr("STORE_NAME", 2),
            ]
        )
        self.assertInstructionListEqual(concrete, concrete.copy())

    def test_encode_varint(self):
        self.assertListEqual(list(ConcreteBytecode._encode_varint(0)), [0])
        self.assertListEqual(list(ConcreteBytecode._encode_varint(0, True)), [128])
        self.assertListEqual(list(ConcreteBytecode._encode_varint(64, False)), [65, 0])


class ConcreteFromCodeTests(TestCase):
    def test_extended_arg(self):
        # Create a code object from arbitrary bytecode
        co_code = b"\x90\x12\x904\x90\xabd\xcd"
        code = get_code("x=1")
        if sys.version_info >= (3, 11):
            self.skipTest("Under Python 3.11 we cannot easily disassemble invalid code")
        else:
            args = (
                code.co_argcount,
                code.co_posonlyargcount,
                code.co_kwonlyargcount,
                code.co_nlocals,
                code.co_stacksize,
                code.co_flags,
                co_code,
                code.co_consts,
                code.co_names,
                code.co_varnames,
                code.co_filename,
                code.co_name,
                code.co_firstlineno,
                code.co_linetable if sys.version_info >= (3, 10) else code.co_lnotab,
                code.co_freevars,
                code.co_cellvars,
            )

        new_code = types.CodeType(*args)

        # without EXTENDED_ARG opcode
        bytecode = ConcreteBytecode.from_code(new_code)
        self.assertInstructionListEqual(
            list(bytecode), [ConcreteInstr("LOAD_CONST", 0x1234ABCD, lineno=1)]
        )

        # with EXTENDED_ARG opcode
        bytecode = ConcreteBytecode.from_code(new_code, extended_arg=True)
        expected = [
            ConcreteInstr("EXTENDED_ARG", 0x12, lineno=1),
            ConcreteInstr("EXTENDED_ARG", 0x34, lineno=1),
            ConcreteInstr("EXTENDED_ARG", 0xAB, lineno=1),
            ConcreteInstr("LOAD_CONST", 0xCD, lineno=1),
        ]
        self.assertInstructionListEqual(list(bytecode), expected)

    def test_extended_arg_make_function(self):
        if (3, 9) <= sys.version_info < (3, 10):
            from .util_annotation import get_code as get_code_future

            code_obj = get_code_future(
                """
                def foo(x: int, y: int):
                    pass
                """
            )
        else:
            code_obj = get_code(
                """
                def foo(x: int, y: int):
                    pass
                """
            )

        # without EXTENDED_ARG
        concrete = ConcreteBytecode.from_code(code_obj)
        if sys.version_info >= (3, 11):
            func_code = concrete.consts[2]
            names = ["int", "foo"]
            consts = ["x", "y", func_code, None]
            const_offset = 1
            name_offset = 1
            first_instrs = [
                ConcreteInstr("LOAD_CONST", 0, lineno=1),
                ConcreteInstr("LOAD_NAME", 0, lineno=1),
                ConcreteInstr("LOAD_CONST", 1, lineno=1),
                ConcreteInstr("LOAD_NAME", 0, lineno=1),
                ConcreteInstr("BUILD_TUPLE", 4, lineno=1),
            ]
        elif sys.version_info >= (3, 10):
            func_code = concrete.consts[2]
            names = ["int", "foo"]
            consts = ["x", "y", func_code, "foo", None]
            const_offset = 1
            name_offset = 1
            first_instrs = [
                ConcreteInstr("LOAD_CONST", 0, lineno=1),
                ConcreteInstr("LOAD_NAME", 0, lineno=1),
                ConcreteInstr("LOAD_CONST", 1, lineno=1),
                ConcreteInstr("LOAD_NAME", 0, lineno=1),
                ConcreteInstr("BUILD_TUPLE", 4, lineno=1),
            ]
        elif (
            sys.version_info >= (3, 7)
            and concrete.flags & CompilerFlags.FUTURE_ANNOTATIONS
        ):
            func_code = concrete.consts[2]
            names = ["foo"]
            consts = ["int", ("x", "y"), func_code, "foo", None]
            const_offset = 1
            name_offset = 0
            first_instrs = [
                ConcreteInstr("LOAD_CONST", 0, lineno=1),
                ConcreteInstr("LOAD_CONST", 0, lineno=1),
                ConcreteInstr("LOAD_CONST", 0 + const_offset, lineno=1),
                ConcreteInstr("BUILD_CONST_KEY_MAP", 2, lineno=1),
            ]
        else:
            func_code = concrete.consts[1]
            names = ["int", "foo"]
            consts = [("x", "y"), func_code, "foo", None]
            const_offset = 0
            name_offset = 1
            first_instrs = [
                ConcreteInstr("LOAD_NAME", 0, lineno=1),
                ConcreteInstr("LOAD_NAME", 0, lineno=1),
                ConcreteInstr("LOAD_CONST", 0 + const_offset, lineno=1),
                ConcreteInstr("BUILD_CONST_KEY_MAP", 2, lineno=1),
            ]

        self.assertSequenceEqual(concrete.names, names)
        self.assertSequenceEqual(concrete.consts, consts)
        expected = (
            first_instrs
            + [
                ConcreteInstr("LOAD_CONST", 1 + const_offset, lineno=1),
                ConcreteInstr("LOAD_CONST", 2 + const_offset, lineno=1),
                *(
                    [
                        ConcreteInstr("MAKE_FUNCTION", lineno=1),
                        ConcreteInstr("SET_FUNCTION_ATTRIBUTE", 4, lineno=1),
                    ]
                    if PY313
                    else [ConcreteInstr("MAKE_FUNCTION", 4, lineno=1)]
                ),
                ConcreteInstr("STORE_NAME", name_offset, lineno=1),
            ]
            + (
                [ConcreteInstr("RETURN_CONST", 3 + const_offset, lineno=1)]
                if sys.version_info >= (3, 12)
                else [
                    ConcreteInstr("LOAD_CONST", 3 + const_offset, lineno=1),
                    ConcreteInstr("RETURN_VALUE", lineno=1),
                ]
            )
        )
        self.assertInstructionListEqual(list(concrete), expected)

        # with EXTENDED_ARG
        concrete = ConcreteBytecode.from_code(code_obj, extended_arg=True)
        # With future annotation the int annotation is stringified and
        # stored as constant this the default behavior under Python 3.10
        if sys.version_info >= (3, 11):
            func_code = concrete.consts[2]
            names = ["int", "foo"]
            consts = ["x", "y", func_code, None]
        elif sys.version_info >= (3, 10):
            func_code = concrete.consts[2]
            names = ["int", "foo"]
            consts = ["x", "y", func_code, "foo", None]
        elif concrete.flags & CompilerFlags.FUTURE_ANNOTATIONS:
            func_code = concrete.consts[2]
            names = ["foo"]
            consts = ["int", ("x", "y"), func_code, "foo", None]
        else:
            func_code = concrete.consts[1]
            names = ["int", "foo"]
            consts = [("x", "y"), func_code, "foo", None]

        self.assertEqual(concrete.names, names)
        self.assertEqual(concrete.consts, consts)
        self.assertInstructionListEqual(list(concrete), expected)

    # Ensure that concrete._remove_extended_args can handle extended_arg NOPs that get
    # passed in from other to_code/from_code methods.
    def test_extended_arg_nop(self):
        constants = [None] * (0x000129 + 1)
        constants[0x000129] = "Arbitrary String"
        # EXTENDED_ARG 0x01, NOP 0xFF, EXTENDED_ARG 0x01,
        # LOAD_CONST 0x29, RETURN_VALUE 0x00
        codestring = bytes(
            [
                opcode.EXTENDED_ARG,
                0x01,
                opcode.opmap["NOP"],
                0xFF,
                opcode.EXTENDED_ARG,
                0x01,
                opcode.opmap["LOAD_CONST"],
                0x29,
                opcode.opmap["RETURN_VALUE"],
                0x00,
            ]
        )
        codetype_list = [
            0,
            0,
            0,
            1,
            64,
            codestring,
            tuple(constants),
            (),
            (),
            "<no file>",
            "code",
            1,
            b"",
            (),
            (),
        ]
        if sys.version_info >= (3, 8):
            codetype_list.insert(1, 0)
        if sys.version_info >= (3, 11):
            codetype_list.insert(12, "code")
            codetype_list.insert(14, bytes())
        codetype_args = tuple(codetype_list)
        code = types.CodeType(*codetype_args)
        # Check it can be encoded and decoded
        codetype_output = Bytecode.from_code(code).to_code().co_consts

        code = ConcreteBytecode()
        code.consts = constants
        code.extend(
            [
                ConcreteInstr("EXTENDED_ARG", 0x01),
                ConcreteInstr("NOP"),
                ConcreteInstr("EXTENDED_ARG", 0x01),
                ConcreteInstr("LOAD_CONST", 0x29),
                ConcreteInstr("RETURN_VALUE"),
            ]
        )
        concrete_output = ConcreteBytecode.to_code(code).co_consts
        self.assertEqual(codetype_output, concrete_output)

    # The next three tests ensure we can round trip ConcreteBytecode generated
    # with extended_args=True

    def test_extended_arg_unpack_ex(self):
        def test():
            p = [1, 2, 3, 4, 5, 6]
            q, r, *s, t = p
            return q, r, s, t

        cpython_stacksize = test.__code__.co_stacksize
        test.__code__ = ConcreteBytecode.from_code(
            test.__code__, extended_arg=True
        ).to_code()
        self.assertEqual(test.__code__.co_stacksize, cpython_stacksize)
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

        test.__code__ = ConcreteBytecode.from_code(
            test.__code__, extended_arg=True
        ).to_code()
        self.assertEqual(test.__code__.co_stacksize, 1)
        self.assertEqual(test(), 259)

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
        bytecode.to_code()

    # XXX add tests for linenumbers which are None

    def test_packing_lines(self):
        import dis

        from .long_lines_example import long_lines

        line_starts = list(dis.findlinestarts(long_lines.__code__))

        concrete = ConcreteBytecode.from_code(long_lines.__code__)
        as_code = concrete.to_code()
        self.assertEqual(line_starts, list(dis.findlinestarts(as_code)))

    def test_exception_table_round_trip(self):
        from . import exception_handling_cases as ehc

        for f in ehc.TEST_CASES:
            print(f.__name__)
            with self.subTest(f.__name__):
                origin = f.__code__
                concrete = ConcreteBytecode.from_code(f.__code__)
                as_code = concrete.to_code(
                    stacksize=f.__code__.co_stacksize,
                    compute_exception_stack_depths=False,
                )
                self.assertCodeObjectEqual(origin, as_code)
                f.__code__ = as_code
                if inspect.iscoroutinefunction(f):
                    if sys.version_info >= (3, 10):
                        asyncio.run(f())
                else:
                    f()

    def test_cellvar_freevar_roundtrip(self):
        from . import cell_free_vars_cases as cfc

        def recompile_code_and_inner(code):
            concrete = ConcreteBytecode.from_code(code)
            for i, c in enumerate(concrete.consts):
                if isinstance(c, types.CodeType):
                    concrete.consts[i] = recompile_code_and_inner(c)
            as_code = concrete.to_code(
                stacksize=code.co_stacksize, compute_exception_stack_depths=False
            )
            self.assertCodeObjectEqual(code, as_code)
            return as_code

        for f in cfc.TEST_CASES:
            print(f.__name__)
            with self.subTest(f.__name__):
                origin = f.__code__
                f.__code__ = recompile_code_and_inner(origin)
                while callable(f := f()):
                    pass


class BytecodeToConcreteTests(TestCase):
    def test_label(self):
        code = Bytecode()
        label = Label()
        code.extend(
            [
                Instr("LOAD_CONST", "hello", lineno=1),
                Instr("JUMP_FORWARD", label, lineno=1),
                label,
                Instr("POP_TOP", lineno=1),
            ]
        )

        code = code.to_concrete_bytecode()
        expected = [
            ConcreteInstr("LOAD_CONST", 0, lineno=1),
            ConcreteInstr("JUMP_FORWARD", 0, lineno=1),
            ConcreteInstr("POP_TOP", lineno=1),
        ]
        self.assertInstructionListEqual(list(code), expected)
        self.assertListEqual(code.consts, ["hello"])

    def test_label2(self):
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
                ),
                Instr("LOAD_CONST", 5, lineno=2),
                Instr("STORE_NAME", "x"),
                Instr("JUMP_FORWARD", label),
                Instr("LOAD_CONST", 7, lineno=4),
                Instr("STORE_NAME", "x"),
                label,
                Instr("LOAD_CONST", None),
                Instr("RETURN_VALUE"),
            ]
        )

        concrete = bytecode.to_concrete_bytecode()
        expected = [
            ConcreteInstr("LOAD_NAME", 0, lineno=1),
            ConcreteInstr(
                "POP_JUMP_FORWARD_IF_FALSE"
                if (3, 12) > sys.version_info >= (3, 11)
                else "POP_JUMP_IF_FALSE",
                7 if OFFSET_AS_INSTRUCTION else 14,
                lineno=1,
            ),
            *([ConcreteInstr("CACHE")] if PY313 else []),
            ConcreteInstr("LOAD_CONST", 0, lineno=2),
            ConcreteInstr("STORE_NAME", 1, lineno=2),
            ConcreteInstr("JUMP_FORWARD", 2 if OFFSET_AS_INSTRUCTION else 4, lineno=2),
            ConcreteInstr("LOAD_CONST", 1, lineno=4),
            ConcreteInstr("STORE_NAME", 1, lineno=4),
            ConcreteInstr("LOAD_CONST", 2, lineno=4),
            ConcreteInstr("RETURN_VALUE", lineno=4),
        ]
        self.assertInstructionListEqual(list(concrete), expected)
        self.assertListEqual(concrete.consts, [5, 7, None])
        self.assertListEqual(concrete.names, ["test", "x"])
        self.assertListEqual(concrete.varnames, [])

    def test_label3(self):
        """
        CPython generates useless EXTENDED_ARG 0 in some cases. We need to
        properly track them as otherwise we can end up with broken offset for
        jumps.
        """
        source = """
            def func(x):
                if x == 1:
                    return x + 0
                elif x == 2:
                    return x + 1
                elif x == 3:
                    return x + 2
                elif x == 4:
                    return x + 3
                elif x == 5:
                    return x + 4
                elif x == 6:
                    return x + 5
                elif x == 7:
                    return x + 6
                elif x == 8:
                    return x + 7
                elif x == 9:
                    return x + 8
                elif x == 10:
                    return x + 9
                elif x == 11:
                    return x + 10
                elif x == 12:
                    return x + 11
                elif x == 13:
                    return x + 12
                elif x == 14:
                    return x + 13
                elif x == 15:
                    return x + 14
                elif x == 16:
                    return x + 15
                elif x == 17:
                    return x + 16
                return -1
        """
        code = get_code(source, function=True)
        bcode = Bytecode.from_code(code)
        concrete = bcode.to_concrete_bytecode()
        self.assertIsInstance(concrete, ConcreteBytecode)

        # Ensure that we do not generate broken code
        loc = {}
        exec(textwrap.dedent(source), loc)
        func = loc["func"]
        func.__code__ = bcode.to_code()
        for i, x in enumerate(range(1, 18)):
            self.assertEqual(func(x), x + i)
        self.assertEqual(func(18), -1)

        # Ensure that we properly round trip in such cases
        self.assertSequenceEqual(
            ConcreteBytecode.from_code(code)
            .to_code(stacksize=code.co_stacksize, compute_exception_stack_depths=False)
            .co_code,
            code.co_code,
        )

    def test_setlineno(self):
        # x = 7
        # y = 8
        # z = 9
        concrete = ConcreteBytecode()
        concrete.consts = [7, 8, 9]
        concrete.names = ["x", "y", "z"]
        concrete.first_lineno = 3
        concrete.extend(
            [
                ConcreteInstr("LOAD_CONST", 0),
                ConcreteInstr("STORE_NAME", 0),
                SetLineno(4),
                ConcreteInstr("LOAD_CONST", 1),
                ConcreteInstr("STORE_NAME", 1),
                SetLineno(5),
                ConcreteInstr("LOAD_CONST", 2),
                ConcreteInstr("STORE_NAME", 2),
            ]
        )

        code = concrete.to_bytecode()
        self.assertInstructionListEqual(
            code,
            [
                Instr("LOAD_CONST", 7, lineno=3),
                Instr("STORE_NAME", "x", lineno=3),
                Instr("LOAD_CONST", 8, lineno=4),
                Instr("STORE_NAME", "y", lineno=4),
                Instr("LOAD_CONST", 9, lineno=5),
                Instr("STORE_NAME", "z", lineno=5),
            ],
        )

    def test_extended_jump(self):
        # code using jumps > 0xffff to test extended arg
        nb_nop = 2**16 if OFFSET_AS_INSTRUCTION else 2**15
        # The length of the jump is independent of the number of instruction
        # per the above logic.
        jump = 2**16
        code = ConcreteBytecode(
            [ConcreteInstr("JUMP_FORWARD", jump)]
            + [ConcreteInstr("NOP")] * nb_nop
            + [
                ConcreteInstr("LOAD_CONST", 0),
                ConcreteInstr("RETURN_VALUE"),
            ],
            consts=(None,),
        )

        code_obj = code.to_code()
        # We use 2 extended args out of the maximum 3 which are allowed
        expected = bytes(
            (
                opcode.EXTENDED_ARG,
                1,
                opcode.EXTENDED_ARG,
                0,
                opcode.opmap["JUMP_FORWARD"],
                0,
                *([opcode.opmap["NOP"], 0] * nb_nop),
                opcode.opmap["LOAD_CONST"],
                0,
                opcode.opmap["RETURN_VALUE"],
                0,
            )
        )
        self.assertSequenceEqual(code_obj.co_code, expected)

    def test_jumps(self):
        # if test:
        #     x = 12
        # else:
        #     x = 37
        code = Bytecode()
        label_else = Label()
        label_return = Label()
        code.extend(
            [
                Instr("LOAD_NAME", "test", lineno=1),
                Instr(
                    "POP_JUMP_FORWARD_IF_FALSE"
                    if (3, 12) > sys.version_info >= (3, 11)
                    else "POP_JUMP_IF_FALSE",
                    label_else,
                ),
                Instr("LOAD_CONST", 12, lineno=2),
                Instr("STORE_NAME", "x"),
                Instr("JUMP_FORWARD", label_return),
                label_else,
                Instr("LOAD_CONST", 37, lineno=4),
                Instr("STORE_NAME", "x"),
                label_return,
                Instr("LOAD_CONST", None, lineno=4),
                Instr("RETURN_VALUE"),
            ]
        )

        code = code.to_concrete_bytecode()
        expected = [
            ConcreteInstr("LOAD_NAME", 0, lineno=1),
            ConcreteInstr(
                "POP_JUMP_FORWARD_IF_FALSE"
                if (3, 12) > sys.version_info >= (3, 11)
                else "POP_JUMP_IF_FALSE",
                5 if OFFSET_AS_INSTRUCTION else 10,
                lineno=1,
            ),
            *([ConcreteInstr("CACHE")] if PY313 else []),
            ConcreteInstr("LOAD_CONST", 0, lineno=2),
            ConcreteInstr("STORE_NAME", 1, lineno=2),
            ConcreteInstr("JUMP_FORWARD", 2 if OFFSET_AS_INSTRUCTION else 4, lineno=2),
            ConcreteInstr("LOAD_CONST", 1, lineno=4),
            ConcreteInstr("STORE_NAME", 1, lineno=4),
            ConcreteInstr("LOAD_CONST", 2, lineno=4),
            ConcreteInstr("RETURN_VALUE", lineno=4),
        ]
        self.assertInstructionListEqual(list(code), expected)
        self.assertListEqual(code.consts, [12, 37, None])
        self.assertListEqual(code.names, ["test", "x"])
        self.assertListEqual(code.varnames, [])

    def test_dont_merge_constants(self):
        # test two constants which are equal but have a different type
        code = Bytecode()
        code.extend(
            [
                Instr("LOAD_CONST", 5, lineno=1),
                Instr("LOAD_CONST", 5.0, lineno=1),
                Instr("LOAD_CONST", -0.0, lineno=1),
                Instr("LOAD_CONST", +0.0, lineno=1),
            ]
        )

        code = code.to_concrete_bytecode()
        expected = [
            ConcreteInstr("LOAD_CONST", 0, lineno=1),
            ConcreteInstr("LOAD_CONST", 1, lineno=1),
            ConcreteInstr("LOAD_CONST", 2, lineno=1),
            ConcreteInstr("LOAD_CONST", 3, lineno=1),
        ]
        self.assertInstructionListEqual(list(code), expected)
        self.assertListEqual(code.consts, [5, 5.0, -0.0, +0.0])

    def test_cellvars(self):
        code = Bytecode()
        code.cellvars = ["x"]
        code.freevars = ["y"]
        code.extend(
            [
                Instr("LOAD_DEREF", CellVar("x"), lineno=1),
                Instr("LOAD_DEREF", FreeVar("y"), lineno=1),
            ]
        )
        concrete = code.to_concrete_bytecode()
        self.assertEqual(concrete.cellvars, ["x"])
        self.assertEqual(concrete.freevars, ["y"])

    def test_compute_jumps_convergence(self):
        # Consider the following sequence of instructions:
        #
        #     JUMP_FORWARD Label1
        #     JUMP_FORWARD Label2
        #     ...126 instructions...
        #   Label1:                 Offset 254 on first pass, 256 second pass
        #     NOP
        #     ... many more instructions ...
        #   Label2:                 Offset > 256 on first pass
        #
        # On first pass of compute_jumps(), Label2 will be at address 254, so
        # that value encodes into the single byte arg of JUMP_ABSOLUTE.
        #
        # On second pass compute_jumps() the instr at Label1 will have offset
        # of 256 so will also be given an EXTENDED_ARG.
        #
        # Thus we need to make an additional pass.  This test only verifies
        # case where 2 passes is insufficient but three is enough.
        #
        # On Python > 3.10 we need to double the number since the offset is now
        # in term of instructions and not bytes.

        # Create code from comment above.
        code = Bytecode()
        label1 = Label()
        label2 = Label()
        nop = "NOP"
        code.append(Instr("JUMP_FORWARD", label1))
        code.append(Instr("JUMP_FORWARD", label2))
        # range excludes the last point ...
        for _ in range(4, 511 if OFFSET_AS_INSTRUCTION else 255, 2):
            code.append(Instr(nop))
        code.append(label1)
        code.append(Instr(nop))
        for _ in range(
            514 if OFFSET_AS_INSTRUCTION else 256,
            600 if OFFSET_AS_INSTRUCTION else 300,
            2,
        ):
            code.append(Instr(nop))
        code.append(label2)
        code.append(Instr(nop))

        # This should pass by default.
        code.to_code()

        # Try with max of two passes:  it should raise
        with self.assertRaises(RuntimeError):
            code.to_code(compute_jumps_passes=2)

    def test_extreme_compute_jumps_convergence(self):
        """Test of compute_jumps() requiring absurd number of passes.

        NOTE:  This test also serves to demonstrate that there is no worst
        case: the number of passes can be unlimited (or, actually, limited by
        the size of the provided code).

        This is an extension of test_compute_jumps_convergence.  Instead of
        two jumps, where the earlier gets extended after the latter, we
        instead generate a series of many jumps.  Each pass of compute_jumps()
        extends one more instruction, which in turn causes the one behind it
        to be extended on the next pass.

        """

        # N: the number of unextended instructions that can be squeezed into a
        # set of bytes adressable by the arg of an unextended instruction.
        # The answer is "128", but here's how we arrive at it.
        max_unextended_offset = 1 << 8
        unextended_branch_instr_size = 2
        N = max_unextended_offset // unextended_branch_instr_size

        # When using instruction rather than bytes in the offset multiply by 2
        if OFFSET_AS_INSTRUCTION:
            N *= 2

        nop = "UNARY_NEGATIVE"  # don't use NOP, dis.stack_effect will raise

        # The number of jumps will be equal to the number of labels.  The
        # number of passes of compute_jumps() required will be one greater
        # than this.
        labels = [Label() for x in range(0, 3 * N)]

        code = Bytecode()
        code.extend(
            Instr("JUMP_FORWARD", labels[len(labels) - x - 1])
            for x in range(0, len(labels))
        )
        end_of_jumps = len(code)
        code.extend(Instr(nop) for x in range(0, N))

        # Now insert the labels.  The first is N instructions (i.e. 256
        # bytes) after the last jump.  Then they proceed to earlier positions
        # 4 bytes at a time.  While the targets are in the range of the nop
        # instructions, 4 bytes is two instructions.  When the targets are in
        # the range of JUMP_FORWARD instructions we have to allow for the fact
        # that the instructions will have been extended to four bytes each, so
        # working backwards 4 bytes per label means just one instruction per
        # label.
        offset = end_of_jumps + N
        for index in range(0, len(labels)):
            code.insert(offset, labels[index])
            if offset <= end_of_jumps:
                offset -= 1
            else:
                offset -= 2

        code.insert(0, Instr("LOAD_CONST", 0))
        del end_of_jumps
        code.append(Instr("RETURN_VALUE"))

        code.to_code(compute_jumps_passes=(len(labels) + 1))

    def test_general_constants(self):
        """Test if general object could be linked as constants."""

        class CustomObject:
            pass

        class UnHashableCustomObject:
            __hash__ = None

        obj1 = [1, 2, 3]
        obj2 = {1, 2, 3}
        obj3 = CustomObject()
        obj4 = UnHashableCustomObject()
        code = Bytecode(
            [
                Instr("LOAD_CONST", obj1, lineno=1),
                Instr("LOAD_CONST", obj2, lineno=1),
                Instr("LOAD_CONST", obj3, lineno=1),
                Instr("LOAD_CONST", obj4, lineno=1),
                Instr("BUILD_TUPLE", 4, lineno=1),
                Instr("RETURN_VALUE", lineno=1),
            ]
        )
        self.assertEqual(code.to_code().co_consts, (obj1, obj2, obj3, obj4))

        def f():
            return  # pragma: no cover

        f.__code__ = code.to_code()
        self.assertEqual(f(), (obj1, obj2, obj3, obj4))

    # FIXME test more cases for line encoding in particular with extended args

    @unittest.skipIf(sys.version_info < (3, 13), "Apply only to 3.13+")
    def test_handling_dual_opcodes(self):
        code = Bytecode()
        code.extend(
            [
                Instr("LOAD_FAST_LOAD_FAST", ("a", "b"), lineno=1),
                Instr("LOAD_FAST_LOAD_FAST", ("c", "d"), lineno=1),
                Instr("LOAD_FAST_LOAD_FAST", ("e", "f"), lineno=1),
                Instr("LOAD_FAST_LOAD_FAST", ("g", "h"), lineno=1),
                Instr("LOAD_FAST_LOAD_FAST", ("i", "j"), lineno=1),
                Instr("LOAD_FAST_LOAD_FAST", ("k", "l"), lineno=1),
                Instr("LOAD_FAST_LOAD_FAST", ("m", "n"), lineno=1),
                Instr("LOAD_FAST_LOAD_FAST", ("o", "p"), lineno=1),
                Instr("LOAD_FAST_LOAD_FAST", ("q", "r"), lineno=1),
            ]
        )
        concrete = code.to_concrete_bytecode()
        assert len(concrete) == 10


if __name__ == "__main__":
    unittest.main()  # pragma: no cover

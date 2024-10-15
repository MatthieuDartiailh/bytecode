#!/usr/bin/env python3
import asyncio
import inspect
import sys
import textwrap
import types
import unittest

from bytecode import Bytecode, ConcreteInstr, FreeVar, Instr, Label, SetLineno
from bytecode.instr import BinaryOp, InstrLocation
from bytecode.utils import PY313

from . import TestCase, get_code


class BytecodeTests(TestCase):
    maxDiff = 80 * 100

    def test_constructor(self):
        code = Bytecode()
        self.assertEqual(code.name, "<module>")
        self.assertEqual(code.filename, "<string>")
        self.assertEqual(code.flags, 0)
        self.assertEqual(code, [])

    def test_invalid_types(self):
        code = Bytecode()
        code.append(123)
        with self.assertRaises(ValueError):
            list(code)
        with self.assertRaises(ValueError):
            code.legalize()
        with self.assertRaises(ValueError):
            Bytecode([123])

    def test_legalize(self):
        code = Bytecode()
        code.first_lineno = 3
        code.extend(
            [
                Instr("LOAD_CONST", 7),
                Instr("STORE_NAME", "x"),
                Instr("LOAD_CONST", 8, lineno=4),
                Instr("STORE_NAME", "y"),
                Label(),
                SetLineno(5),
                Instr("LOAD_CONST", 9, lineno=6),
                Instr("STORE_NAME", "z"),
            ]
        )

        code.legalize()
        self.assertListEqual(
            code,
            [
                Instr("LOAD_CONST", 7, lineno=3),
                Instr("STORE_NAME", "x", lineno=3),
                Instr("LOAD_CONST", 8, lineno=4),
                Instr("STORE_NAME", "y", lineno=4),
                Label(),
                Instr("LOAD_CONST", 9, lineno=5),
                Instr("STORE_NAME", "z", lineno=5),
            ],
        )

    def test_slice(self):
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
        sliced_code = code[:]
        self.assertEqual(code, sliced_code)
        for name in (
            "argcount",
            "posonlyargcount",
            "kwonlyargcount",
            "first_lineno",
            "name",
            "filename",
            "docstring",
            "cellvars",
            "freevars",
            "argnames",
        ):
            self.assertEqual(
                getattr(code, name, None), getattr(sliced_code, name, None)
            )

    def test_copy(self):
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

        copy_code = code.copy()
        self.assertEqual(code, copy_code)
        for name in (
            "argcount",
            "posonlyargcount",
            "kwonlyargcount",
            "first_lineno",
            "name",
            "filename",
            "docstring",
            "cellvars",
            "freevars",
            "argnames",
        ):
            self.assertEqual(getattr(code, name, None), getattr(copy_code, name, None))

    def test_eq(self):
        code = get_code(
            """
            if test:
                x = 1
            else:
                x = 2
        """
        )
        b1 = Bytecode.from_code(code)
        b2 = Bytecode.from_code(code)
        self.assertEqual(b1, b2)

    def test_eq_with_try(self):
        code = get_code(
            """
            try:
                x = 1
            except Exception:
                pass
            finally:
                print()
        """
        )
        b1 = Bytecode.from_code(code)
        b2 = Bytecode.from_code(code)
        self.assertEqual(b1, b2)

    def test_from_code(self):
        code = get_code(
            """
            if test:
                x = 1
            else:
                x = 2
        """
        )
        bytecode = Bytecode.from_code(code)
        label_else = Label()
        label_exit = Label()
        if sys.version_info < (3, 10):
            self.assertEqual(
                bytecode,
                [
                    Instr("LOAD_NAME", "test", lineno=1),
                    Instr("POP_JUMP_IF_FALSE", label_else, lineno=1),
                    Instr("LOAD_CONST", 1, lineno=2),
                    Instr("STORE_NAME", "x", lineno=2),
                    Instr("JUMP_FORWARD", label_exit, lineno=2),
                    label_else,
                    Instr("LOAD_CONST", 2, lineno=4),
                    Instr("STORE_NAME", "x", lineno=4),
                    label_exit,
                    Instr("LOAD_CONST", None, lineno=4),
                    Instr("RETURN_VALUE", lineno=4),
                ],
            )
        # Control flow handling appears to have changed under Python 3.10
        elif sys.version_info < (3, 11):
            self.assertEqual(
                bytecode,
                [
                    Instr("LOAD_NAME", "test", lineno=1),
                    Instr("POP_JUMP_IF_FALSE", label_else, lineno=1),
                    Instr("LOAD_CONST", 1, lineno=2),
                    Instr("STORE_NAME", "x", lineno=2),
                    Instr("LOAD_CONST", None, lineno=2),
                    Instr("RETURN_VALUE", lineno=2),
                    label_else,
                    Instr("LOAD_CONST", 2, lineno=4),
                    Instr("STORE_NAME", "x", lineno=4),
                    Instr("LOAD_CONST", None, lineno=4),
                    Instr("RETURN_VALUE", lineno=4),
                ],
            )
        elif sys.version_info < (3, 12):
            self.assertInstructionListEqual(
                bytecode,
                [
                    Instr("RESUME", 0, lineno=0),
                    Instr("LOAD_NAME", "test", lineno=1),
                    Instr("POP_JUMP_FORWARD_IF_FALSE", label_else, lineno=1),
                    Instr("LOAD_CONST", 1, lineno=2),
                    Instr("STORE_NAME", "x", lineno=2),
                    Instr("LOAD_CONST", None, lineno=2),
                    Instr("RETURN_VALUE", lineno=2),
                    label_else,
                    Instr("LOAD_CONST", 2, lineno=4),
                    Instr("STORE_NAME", "x", lineno=4),
                    Instr("LOAD_CONST", None, lineno=4),
                    Instr("RETURN_VALUE", lineno=4),
                ],
            )
        elif sys.version_info < (3, 13):
            self.assertInstructionListEqual(
                bytecode,
                [
                    Instr("RESUME", 0, lineno=0),
                    Instr("LOAD_NAME", "test", lineno=1),
                    Instr("POP_JUMP_IF_FALSE", label_else, lineno=1),
                    Instr("LOAD_CONST", 1, lineno=2),
                    Instr("STORE_NAME", "x", lineno=2),
                    Instr("RETURN_CONST", None, lineno=2),
                    label_else,
                    Instr("LOAD_CONST", 2, lineno=4),
                    Instr("STORE_NAME", "x", lineno=4),
                    Instr("RETURN_CONST", None, lineno=4),
                ],
            )
        else:
            self.assertInstructionListEqual(
                bytecode,
                [
                    Instr("RESUME", 0, lineno=0),
                    Instr("LOAD_NAME", "test", lineno=1),
                    Instr("TO_BOOL", lineno=1),
                    Instr("POP_JUMP_IF_FALSE", label_else, lineno=1),
                    Instr("LOAD_CONST", 1, lineno=2),
                    Instr("STORE_NAME", "x", lineno=2),
                    Instr("RETURN_CONST", None, lineno=2),
                    label_else,
                    Instr("LOAD_CONST", 2, lineno=4),
                    Instr("STORE_NAME", "x", lineno=4),
                    Instr("RETURN_CONST", None, lineno=4),
                ],
            )

    def test_from_code_freevars(self):
        ns = {}
        exec(
            textwrap.dedent(
                """
            def create_func():
                x = 1
                def func():
                    return x
                return func

            func = create_func()
        """
            ),
            ns,
            ns,
        )
        code = ns["func"].__code__

        bytecode = Bytecode.from_code(code)
        self.assertInstructionListEqual(
            bytecode,
            (
                [
                    Instr("COPY_FREE_VARS", 1, lineno=None),
                    Instr("RESUME", 0, lineno=4),
                ]
                if sys.version_info >= (3, 11)
                else []
            )
            + [
                Instr("LOAD_DEREF", FreeVar("x"), lineno=5),
                Instr("RETURN_VALUE", lineno=5),
            ],
        )

    def test_from_code_load_fast(self):
        code = get_code(
            """
            def func():
                x = 33
                y = x
        """,
            function=True,
        )
        code = Bytecode.from_code(code)
        self.assertInstructionListEqual(
            code,
            (
                [
                    Instr("RESUME", 0, lineno=1),
                ]
                if sys.version_info >= (3, 11)
                else []
            )
            + [
                Instr("LOAD_CONST", 33, lineno=2),
                Instr("STORE_FAST", "x", lineno=2),
                Instr("LOAD_FAST", "x", lineno=3),
                Instr("STORE_FAST", "y", lineno=3),
            ]
            + (
                [Instr("RETURN_CONST", None, lineno=3)]
                if sys.version_info >= (3, 12)
                else [
                    Instr("LOAD_CONST", None, lineno=3),
                    Instr("RETURN_VALUE", lineno=3),
                ]
            ),
        )

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

        concrete = code.to_concrete_bytecode()
        self.assertEqual(concrete.consts, [7, 8, 9])
        self.assertEqual(concrete.names, ["x", "y", "z"])
        self.assertListEqual(
            list(concrete),
            [
                ConcreteInstr(
                    "LOAD_CONST", 0, location=InstrLocation(3, None, None, None)
                ),
                ConcreteInstr(
                    "STORE_NAME", 0, location=InstrLocation(3, None, None, None)
                ),
                ConcreteInstr(
                    "LOAD_CONST", 1, location=InstrLocation(4, None, None, None)
                ),
                ConcreteInstr(
                    "STORE_NAME", 1, location=InstrLocation(4, None, None, None)
                ),
                ConcreteInstr(
                    "LOAD_CONST", 2, location=InstrLocation(5, None, None, None)
                ),
                ConcreteInstr(
                    "STORE_NAME", 2, location=InstrLocation(5, None, None, None)
                ),
            ],
        )

    def test_to_code(self):
        code = Bytecode()
        code.first_lineno = 50
        code.extend(
            [
                Instr("LOAD_NAME", "print"),
                Instr("LOAD_CONST", "%s"),
                Instr(
                    "LOAD_GLOBAL", (False, "a") if sys.version_info >= (3, 11) else "a"
                ),
                Instr("BINARY_OP", BinaryOp.ADD)
                if sys.version_info >= (3, 11)
                else Instr("BINARY_ADD"),
            ]
            # For 3.12+ we need a NULL before a CALL to a free function
            + ([Instr("PUSH_NULL")] if sys.version_info >= (3, 12) else [])
            + [
                # On 3.11 we should have a pre-call
                Instr("CALL" if sys.version_info >= (3, 11) else "CALL_FUNCTION", 1),
                Instr("RETURN_VALUE"),
            ]
        )
        co = code.to_code()
        # hopefully this is obvious from inspection? :-)
        self.assertEqual(co.co_stacksize, 3)

        co = code.to_code(stacksize=42, compute_exception_stack_depths=False)
        self.assertEqual(co.co_stacksize, 42)

    def test_negative_size_unary(self):
        opnames = (
            "UNARY_POSITIVE",
            "UNARY_NEGATIVE",
            "UNARY_NOT",
            "UNARY_INVERT",
        )
        for opname in opnames:
            # Replaced by an intrinsic in 3.12
            if sys.version_info >= (3, 12) and opname == "UNARY_POSITIVE":
                continue
            with self.subTest(opname):
                code = Bytecode()
                code.first_lineno = 1
                code.extend([Instr(opname)])
                with self.assertRaises(RuntimeError):
                    code.compute_stacksize()

    def test_negative_size_unary_with_disable_check_of_pre_and_post(self):
        opnames = (
            "UNARY_POSITIVE",
            "UNARY_NEGATIVE",
            "UNARY_NOT",
            "UNARY_INVERT",
        )
        for opname in opnames:
            # Replaced by an intrinsic in 3.12
            if sys.version_info >= (3, 12) and opname == "UNARY_POSITIVE":
                continue
            with self.subTest(opname):
                code = Bytecode()
                code.first_lineno = 1
                code.extend([Instr(opname)])
                co = code.to_code(check_pre_and_post=False)
                # In 3.13 the code object constructor fixes the stacksize for us...
                if not PY313:
                    self.assertEqual(co.co_stacksize, 0)

    def test_negative_size_binary(self):
        operations = (
            "SUBSCR",  # Subscr is special
            "POWER",
            "MULTIPLY",
            "MATRIX_MULTIPLY",
            "FLOOR_DIVIDE",
            "TRUE_DIVIDE",
            "ADD",
            "SUBTRACT",
            "LSHIFT",
            "RSHIFT",
            "AND",
            "XOR",
            "OR",
        )
        if sys.version_info >= (3, 11):
            operations += ("REMAINDER",)
        else:
            operations += ("MODULO",)

        for opname in operations:
            ops = (opname,)
            if opname != "SUBSCR":
                ops += ("INPLACE_" + opname,)
            for op in ops:
                with self.subTest(op):
                    code = Bytecode()
                    code.first_lineno = 1
                    if sys.version_info >= (3, 11):
                        if op == "SUBSCR":
                            i = Instr("BINARY_SUBSCR")
                        else:
                            i = Instr("BINARY_OP", getattr(BinaryOp, op))
                    else:
                        if "INPLACE" not in op:
                            op = "BINARY_" + op
                        i = Instr(op)

                    code.extend([Instr("LOAD_CONST", 1), i])
                    with self.assertRaises(RuntimeError):
                        code.compute_stacksize()

    def test_negative_size_binary_with_disable_check_of_pre_and_post(self):
        operations = (
            "SUBSCR",  # Subscr is special
            "POWER",
            "MULTIPLY",
            "MATRIX_MULTIPLY",
            "FLOOR_DIVIDE",
            "TRUE_DIVIDE",
            "ADD",
            "SUBTRACT",
            "LSHIFT",
            "RSHIFT",
            "AND",
            "XOR",
            "OR",
        )
        if sys.version_info >= (3, 11):
            operations += ("REMAINDER",)
        else:
            operations += ("MODULO",)

        for opname in operations:
            ops = (opname,)
            if opname != "SUBSCR":
                ops += ("INPLACE_" + opname,)
            for op in ops:
                with self.subTest(op):
                    code = Bytecode()
                    code.first_lineno = 1
                    if sys.version_info >= (3, 11):
                        if op == "SUBSCR":
                            i = Instr("BINARY_SUBSCR")
                        else:
                            i = Instr("BINARY_OP", getattr(BinaryOp, op))
                    else:
                        if "INPLACE" not in op:
                            op = "BINARY_" + op
                        i = Instr(op)

                    code.extend([Instr("LOAD_CONST", 1), i])
                    co = code.to_code(check_pre_and_post=False)
                    self.assertEqual(co.co_stacksize, 1)

    def test_negative_size_call(self):
        code = Bytecode()
        code.first_lineno = 1
        code.extend(
            [Instr("CALL" if sys.version_info >= (3, 11) else "CALL_FUNCTION", 0)]
        )
        with self.assertRaises(RuntimeError):
            code.compute_stacksize()

    def test_negative_size_unpack(self):
        opnames = (
            "UNPACK_SEQUENCE",
            "UNPACK_EX",
        )
        for opname in opnames:
            with self.subTest(opname):
                code = Bytecode()
                code.first_lineno = 1
                code.extend([Instr(opname, 1)])
                with self.assertRaises(RuntimeError):
                    code.compute_stacksize()

    def test_negative_size_build(self):
        opnames = (
            "BUILD_TUPLE",
            "BUILD_LIST",
            "BUILD_SET",
        )
        opnames = (*opnames, "BUILD_STRING")

        for opname in opnames:
            with self.subTest(opname):
                code = Bytecode()
                code.first_lineno = 1
                code.extend([Instr(opname, 1)])
                with self.assertRaises(RuntimeError):
                    code.compute_stacksize()

    def test_negative_size_build_map(self):
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("LOAD_CONST", 1), Instr("BUILD_MAP", 1)])
        with self.assertRaises(RuntimeError):
            code.compute_stacksize()

    def test_negative_size_build_map_with_disable_check_of_pre_and_post(self):
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("LOAD_CONST", 1), Instr("BUILD_MAP", 1)])
        co = code.to_code(check_pre_and_post=False)
        self.assertEqual(co.co_stacksize, 1)

    def test_negative_size_build_const_map(self):
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("LOAD_CONST", ("a",)), Instr("BUILD_CONST_KEY_MAP", 1)])
        with self.assertRaises(RuntimeError):
            code.compute_stacksize()

    def test_negative_size_build_const_map_with_disable_check_of_pre_and_post(self):
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("LOAD_CONST", ("a",)), Instr("BUILD_CONST_KEY_MAP", 1)])
        co = code.to_code(check_pre_and_post=False)
        self.assertEqual(co.co_stacksize, 1)

    def test_empty_dup(self):
        if sys.version_info >= (3, 11):
            self.skipTest("Instructions DUP_TOP do not exist in 3.11+")
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("DUP_TOP")])
        with self.assertRaises(RuntimeError):
            code.compute_stacksize()

    def test_not_enough_dup(self):
        if sys.version_info >= (3, 11):
            self.skipTest("Instructions DUP_TOP_TWO do not exist in 3.11+")
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("LOAD_CONST", 1), Instr("DUP_TOP_TWO")])
        with self.assertRaises(RuntimeError):
            code.compute_stacksize()

    def test_not_enough_rot(self):
        if sys.version_info >= (3, 11):
            self.skipTest("Instructions ROT_* do not exist in 3.11+")
        opnames = ["ROT_TWO", "ROT_THREE", "ROT_FOUR"]
        for opname in opnames:
            with self.subTest(opname):
                code = Bytecode()
                code.first_lineno = 1
                code.extend([Instr("LOAD_CONST", 1), Instr(opname)])
                with self.assertRaises(RuntimeError):
                    code.compute_stacksize()

    def test_not_enough_rot_with_disable_check_of_pre_and_post(self):
        if sys.version_info >= (3, 11):
            self.skipTest("Instructions ROT_* do not exist in 3.11+")
        opnames = ["ROT_TWO", "ROT_THREE", "ROT_FOUR"]
        for opname in opnames:
            with self.subTest(opname):
                code = Bytecode()
                code.first_lineno = 1
                code.extend([Instr("LOAD_CONST", 1), Instr(opname)])
                co = code.to_code(check_pre_and_post=False)
                self.assertEqual(co.co_stacksize, 1)

    def test_not_enough_copy(self):
        if sys.version_info < (3, 11):
            self.skipTest("Instruction COPY does not exist before 3.11")
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("LOAD_CONST", 1), Instr("COPY", 2)])
        with self.assertRaises(RuntimeError):
            code.compute_stacksize()

    def test_not_enough_copy_with_disable_check_of_pre_and_post(self):
        if sys.version_info < (3, 11):
            self.skipTest("Instruction COPY does not exist before 3.11")
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("LOAD_CONST", 1), Instr("COPY", 2)])
        co = code.to_code(check_pre_and_post=False)
        self.assertEqual(co.co_stacksize, 2)

    def test_not_enough_swap(self):
        if sys.version_info < (3, 11):
            self.skipTest("Instruction SWAP does not exist before 3.11")
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("LOAD_CONST", 1), Instr("SWAP", 2)])
        with self.assertRaises(RuntimeError):
            code.compute_stacksize()

    def test_not_enough_swap_with_disable_check_of_pre_and_post(self):
        if sys.version_info < (3, 11):
            self.skipTest("Instruction SWAP does not exist before 3.11")
        code = Bytecode()
        code.first_lineno = 1
        code.extend([Instr("LOAD_CONST", 1), Instr("SWAP", 2)])
        co = code.to_code(check_pre_and_post=False)
        self.assertEqual(co.co_stacksize, 1)

    def test_for_iter_stack_effect_computation(self):
        code = Bytecode()
        code.first_lineno = 1
        lab1 = Label()
        lab2 = Label()
        code.extend(
            [
                lab1,
                Instr("FOR_ITER", lab2),
                Instr("STORE_FAST", "i"),
                Instr(
                    "JUMP_BACKWARD" if sys.version_info >= (3, 11) else "JUMP_ABSOLUTE",
                    lab1,
                ),
                lab2,
            ]
        )
        # Under 3.12+ FOR_ITER does not pop the iterator on completion so this
        # does not fail a coarse stack effect computation.
        if sys.version_info >= (3, 12):
            self.skipTest("Irrelevant on 3.12+")
        with self.assertRaises(RuntimeError):
            # Use compute_stacksize since the code is so broken that conversion
            # to from concrete is actually broken
            code.compute_stacksize(check_pre_and_post=False)

    def test_exception_table_round_trip(self):
        from . import exception_handling_cases as ehc

        for f in ehc.TEST_CASES:
            print(f.__name__)
            with self.subTest(f.__name__):
                origin = f.__code__
                bytecode = Bytecode.from_code(
                    origin,
                    conserve_exception_block_stackdepth=True,
                )
                as_code = bytecode.to_code(
                    stacksize=f.__code__.co_stacksize,
                    compute_exception_stack_depths=False,
                )
                self.assertCodeObjectEqual(origin, as_code)
                if inspect.iscoroutinefunction(f):
                    # contextlib.nullcontext support async context only in 3.10+
                    if sys.version_info >= (3, 10):
                        asyncio.run(f())
                else:
                    f()

    def test_cellvar_freevar_roundtrip(self):
        from . import cell_free_vars_cases as cfc

        def recompile_code_and_inner(code):
            bytecode = Bytecode.from_code(
                code,
                conserve_exception_block_stackdepth=True,
            )
            for instr in bytecode:
                if isinstance(instr, Instr) and isinstance(instr.arg, types.CodeType):
                    instr.arg = recompile_code_and_inner(instr.arg)
            as_code = bytecode.to_code(
                stacksize=code.co_stacksize,
                compute_exception_stack_depths=False,
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

    def test_empty_try_block(self):
        if sys.version_info < (3, 11):
            self.skipTest("Exception tables were introduced in 3.11")

        import bytecode as b

        def foo():
            return 42

        code = Bytecode.from_code(foo.__code__)

        try_begin = b.TryBegin(Label(), push_lasti=True)
        code[1:1] = [try_begin, b.TryEnd(try_begin), try_begin.target]

        foo.__code__ = code.to_code()

        # Test that the function is still good
        self.assertEqual(foo(), 42)

        # Test that we can re-decompile the code
        code = Bytecode.from_code(foo.__code__)
        foo.__code__ = code.to_code()

        # Test that the function is still good
        self.assertEqual(foo(), 42)

        # Do another round trip
        Bytecode.from_code(foo.__code__).to_code()

    def test_try_block_around_extended_arg(self):
        """Test that we can handle small try blocks around opcodes that require
        extended arguments.

        We wrap a jump instruction between a TryBegin and TryEnd, and ensure
        that the jump target is further away as to require an extended argument
        for the branching instruction. We then test that we can compile and
        de-compile the code object without issues.
        """
        if sys.version_info < (3, 11):
            self.skipTest("Exception tables were introduced in 3.11")

        import bytecode as b

        def foo():
            return 42

        bc = Bytecode.from_code(foo.__code__)

        try_begin = b.TryBegin(Label(), push_lasti=True)
        bc[1:1] = [
            try_begin,
            Instr("JUMP_FORWARD", try_begin.target),
            b.TryEnd(try_begin),
            *(Instr("NOP") for _ in range(400)),
            try_begin.target,
        ]

        foo.__code__ = bc.to_code()

        self.assertEqual(foo(), 42)

        # Do another round trip
        foo.__code__ = Bytecode.from_code(foo.__code__).to_code()

        self.assertEqual(foo(), 42)


if __name__ == "__main__":
    unittest.main()  # pragma: no cover

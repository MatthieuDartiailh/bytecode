#!/usr/bin/env python3
import opcode
import sys
import unittest

from bytecode import (
    UNSET,
    BasicBlock,
    CellVar,
    Compare,
    FreeVar,
    Instr,
    Label,
    SetLineno,
)
from bytecode.instr import (
    BITFLAG2_OPCODES,
    BITFLAG_OPCODES,
    DUAL_ARG_OPCODES,
    INTRINSIC_1OP,
    INTRINSIC_2OP,
    InstrLocation,
    Intrinsic1Op,
    Intrinsic2Op,
    opcode_has_argument,
)
from bytecode.utils import PY311, PY313

from . import TestCase

# XXX  tests for location and lineno setter

# Starting with Python 3.11 jump opcode have changed quite a bit. We define here
# opcode useful to test for both Python < 3.11 and Python >= 3.11
UNCONDITIONAL_JUMP = "JUMP_FORWARD" if PY311 else "JUMP_ABSOLUTE"
CONDITIONAL_JUMP = (
    "POP_JUMP_FORWARD_IF_TRUE"
    if (3, 12) > sys.version_info >= (3, 11)
    else "POP_JUMP_IF_TRUE"
)
CALL = "CALL" if PY311 else "CALL_FUNCTION"


class SetLinenoTests(TestCase):
    def test_lineno(self):
        lineno = SetLineno(1)
        self.assertEqual(lineno.lineno, 1)

    def test_equality(self):
        lineno = SetLineno(1)
        self.assertNotEqual(lineno, 1)
        self.assertEqual(lineno, SetLineno(1))
        self.assertNotEqual(lineno, SetLineno(2))


class VariableTests(TestCase):
    def test_str(self):
        for cls in (CellVar, FreeVar):
            var = cls("a")
            self.assertEqual(str(var), "a")

    def test_repr(self):
        for cls in (CellVar, FreeVar):
            var = cls("_a_x_a_")
            r = repr(var)
            self.assertIn("_a_x_a_", r)
            self.assertIn(cls.__name__, r)

    def test_eq(self):
        f1 = FreeVar("a")
        f2 = FreeVar("b")
        c1 = CellVar("a")
        c2 = CellVar("b")

        for v1, v2, eq in (
            (f1, f1, True),
            (f1, f2, False),
            (f1, c1, False),
            (c1, c1, True),
            (c1, c2, False),
        ):
            if eq:
                self.assertEqual(v1, v2)
            else:
                self.assertNotEqual(v1, v2)


class InstrLocationTests(TestCase):
    def test_init(self):
        for args, error in [
            ((None, None, None, None), ""),
            ((None, 1, None, None), "End lineno specified with no lineno"),
            ((12, 1, None, None), "cannot be smaller than lineno"),
            ((12, 13, None, None), ""),
            ((None, None, 1, None), "lineno information are incomplete"),
            ((None, None, None, 1), "lineno information are incomplete"),
            ((1, None, 1, None), "lineno information are incomplete"),
            ((1, None, None, 1), "lineno information are incomplete"),
            ((1, 2, None, 1), "with no column offset"),
            ((1, 2, 12, 1), ""),
            ((1, 1, 12, 1), "cannot be smaller than column offset"),
            ((1, 1, 12, None), "No end column offset was"),
        ]:
            print(f"{args}, {error}")
            with self.subTest(f"{args}, {error}"):
                if error:
                    with self.assertRaises(ValueError) as e:
                        InstrLocation(*args)
                    self.assertIn(error, str(e.exception))
                else:
                    InstrLocation(*args)


class InstrTests(TestCase):
    def test_constructor(self):
        # invalid line number
        with self.assertRaises(TypeError):
            Instr("NOP", lineno="x")
        with self.assertRaises(ValueError):
            Instr("NOP", lineno=-1 if sys.version_info >= (3, 11) else 0)

        # invalid name
        with self.assertRaises(TypeError):
            Instr(1)
        with self.assertRaises(ValueError):
            Instr("xxx")

    def test_repr(self):
        # No arg
        r = repr(Instr("NOP", lineno=10))
        self.assertIn("NOP", r)
        self.assertIn("10", r)
        self.assertIn("lineno", r)

        # Arg
        r = repr(Instr("LOAD_FAST", "_x_", lineno=10))
        self.assertIn("LOAD_FAST", r)
        self.assertIn("lineno", r)
        self.assertIn("10", r)
        self.assertIn("arg", r)
        self.assertIn("_x_", r)

    def test_reject_pseudo_opcode(self):
        if sys.version_info >= (3, 12):
            with self.assertRaises(ValueError) as e:
                Instr("LOAD_METHOD", "x")
            self.assertIn("is an instrumented or pseudo opcode", str(e.exception))

    def test_invalid_arg(self):
        label = Label()
        block = BasicBlock()

        # EXTENDED_ARG
        self.assertRaises(ValueError, Instr, "EXTENDED_ARG", 0)

        # has_jump()
        self.assertRaises(TypeError, Instr, UNCONDITIONAL_JUMP, 1)
        self.assertRaises(TypeError, Instr, UNCONDITIONAL_JUMP, 1.0)
        Instr(UNCONDITIONAL_JUMP, label)
        Instr(UNCONDITIONAL_JUMP, block)

        # hasfree
        self.assertRaises(TypeError, Instr, "LOAD_DEREF", "x")
        Instr("LOAD_DEREF", CellVar("x"))
        Instr("LOAD_DEREF", FreeVar("x"))

        # haslocal
        self.assertRaises(TypeError, Instr, "LOAD_FAST", 1)
        Instr("LOAD_FAST", "x")

        # hasname
        self.assertRaises(TypeError, Instr, "LOAD_NAME", 1)
        Instr("LOAD_NAME", "x")

        # hasconst
        self.assertRaises(ValueError, Instr, "LOAD_CONST")  # UNSET
        self.assertRaises(ValueError, Instr, "LOAD_CONST", label)
        self.assertRaises(ValueError, Instr, "LOAD_CONST", block)
        Instr("LOAD_CONST", 1.0)
        Instr("LOAD_CONST", object())

        # hascompare
        self.assertRaises(TypeError, Instr, "COMPARE_OP", 1)
        Instr("COMPARE_OP", Compare.EQ)

        # HAVE_ARGUMENT
        self.assertRaises(ValueError, Instr, CALL, -1)
        self.assertRaises(TypeError, Instr, CALL, 3.0)
        Instr(CALL, 3)

        # test maximum argument
        self.assertRaises(ValueError, Instr, CALL, 2147483647 + 1)
        instr = Instr(CALL, 2147483647)
        self.assertEqual(instr.arg, 2147483647)

        # not HAVE_ARGUMENT
        self.assertRaises(ValueError, Instr, "NOP", 0)
        Instr("NOP")

        # Instructions using a bitflag in their oparg
        for name in (opcode.opname[op] for op in BITFLAG_OPCODES):
            self.assertRaises(TypeError, Instr, name, "arg")
            self.assertRaises(TypeError, Instr, name, ("arg",))
            self.assertRaises(TypeError, Instr, name, ("", "arg"))
            self.assertRaises(TypeError, Instr, name, (False, 1))
            Instr(name, (True, "arg"))

        # Instructions using 2 bitflag in their oparg
        for name in (opcode.opname[op] for op in BITFLAG2_OPCODES):
            self.assertRaises(TypeError, Instr, name, "arg")
            self.assertRaises(TypeError, Instr, name, ("arg",))
            self.assertRaises(TypeError, Instr, name, ("", True, "arg"))
            self.assertRaises(TypeError, Instr, name, (True, "", "arg"))
            self.assertRaises(TypeError, Instr, name, (False, True, 1))
            Instr(name, (False, True, "arg"))

        # Instructions packing 2 args in their oparg
        for name in (opcode.opname[op] for op in DUAL_ARG_OPCODES):
            self.assertRaises(TypeError, Instr, name, "arg")
            self.assertRaises(TypeError, Instr, name, ("arg",))
            self.assertRaises(TypeError, Instr, name, ("", True))
            Instr(name, ("arg1", "arg2"))

        for name in [opcode.opname[i] for i in INTRINSIC_1OP]:
            self.assertRaises(TypeError, Instr, name, 1)
            Instr(name, Intrinsic1Op.INTRINSIC_PRINT)

        for name in [opcode.opname[i] for i in INTRINSIC_2OP]:
            self.assertRaises(TypeError, Instr, name, 1)
            Instr(name, Intrinsic2Op.INTRINSIC_PREP_RERAISE_STAR)

    def test_require_arg(self):
        i = Instr(CALL, 3)
        self.assertTrue(i.require_arg())
        i = Instr("NOP")
        self.assertFalse(i.require_arg())

    def test_attr(self):
        instr = Instr("LOAD_CONST", 3, lineno=5)
        self.assertEqual(instr.name, "LOAD_CONST")
        self.assertEqual(instr.opcode, opcode.opmap["LOAD_CONST"])
        self.assertEqual(instr.arg, 3)
        self.assertEqual(instr.lineno, 5)

        # invalid values/types
        self.assertRaises(
            ValueError,
            setattr,
            instr,
            "lineno",
            -1 if sys.version_info >= (3, 11) else 0,
        )
        self.assertRaises(TypeError, setattr, instr, "lineno", 1.0)
        self.assertRaises(TypeError, setattr, instr, "name", 5)
        self.assertRaises(TypeError, setattr, instr, "opcode", 1.0)
        self.assertRaises(ValueError, setattr, instr, "opcode", -1)
        self.assertRaises(ValueError, setattr, instr, "opcode", 255)

        # arg can take any attribute but cannot be deleted
        instr.arg = -8
        instr.arg = object()
        self.assertRaises(AttributeError, delattr, instr, "arg")

        # no argument
        instr = Instr("RETURN_VALUE")
        self.assertIs(instr.arg, UNSET)

    def test_modify_op(self):
        instr = Instr("LOAD_NAME", "x")
        load_fast = opcode.opmap["LOAD_FAST"]
        instr.opcode = load_fast
        self.assertEqual(instr.name, "LOAD_FAST")
        self.assertEqual(instr.opcode, load_fast)

    def test_extended_arg(self):
        instr = Instr("LOAD_CONST", 0x1234ABCD)
        self.assertEqual(instr.arg, 0x1234ABCD)

    def test_slots(self):
        instr = Instr("NOP")
        with self.assertRaises(AttributeError):
            instr.myattr = 1

    def test_compare(self):
        instr = Instr("LOAD_CONST", 3, lineno=7)
        self.assertEqual(instr, Instr("LOAD_CONST", 3, lineno=7))
        self.assertNotEqual(instr, 1)

        # different lineno
        self.assertNotEqual(instr, Instr("LOAD_CONST", 3))
        self.assertNotEqual(instr, Instr("LOAD_CONST", 3, lineno=6))
        # different op
        self.assertNotEqual(instr, Instr("LOAD_FAST", "x", lineno=7))
        # different arg
        self.assertNotEqual(instr, Instr("LOAD_CONST", 4, lineno=7))

    def test_has_jump(self):
        label = Label()
        jump = Instr(UNCONDITIONAL_JUMP, label)
        self.assertTrue(jump.has_jump())

        instr = Instr("LOAD_FAST", "x")
        self.assertFalse(instr.has_jump())

    def test_is_cond_jump(self):
        label = Label()
        jump = Instr(CONDITIONAL_JUMP, label)
        self.assertTrue(jump.is_cond_jump())

        instr = Instr("LOAD_FAST", "x")
        self.assertFalse(instr.is_cond_jump())

    def test_is_uncond_jump(self):
        label = Label()
        jump = Instr(UNCONDITIONAL_JUMP, label)
        self.assertTrue(jump.is_uncond_jump())

        instr = Instr(CONDITIONAL_JUMP, label)
        self.assertFalse(instr.is_uncond_jump())

    def test_const_key_not_equal(self):
        def check(value):
            self.assertEqual(Instr("LOAD_CONST", value), Instr("LOAD_CONST", value))

        def func():
            pass

        check(None)
        check(0)
        check(0.0)
        check(b"bytes")
        check("text")
        check(Ellipsis)
        check((1, 2, 3))
        check(frozenset({1, 2, 3}))
        check(func.__code__)
        check(object())

    def test_const_key_equal(self):
        neg_zero = -0.0
        pos_zero = +0.0

        # int and float: 0 == 0.0
        self.assertNotEqual(Instr("LOAD_CONST", 0), Instr("LOAD_CONST", 0.0))

        # float: -0.0 == +0.0
        self.assertNotEqual(
            Instr("LOAD_CONST", neg_zero), Instr("LOAD_CONST", pos_zero)
        )

        # complex
        self.assertNotEqual(
            Instr("LOAD_CONST", complex(neg_zero, 1.0)),
            Instr("LOAD_CONST", complex(pos_zero, 1.0)),
        )
        self.assertNotEqual(
            Instr("LOAD_CONST", complex(1.0, neg_zero)),
            Instr("LOAD_CONST", complex(1.0, pos_zero)),
        )

        # tuple
        self.assertNotEqual(Instr("LOAD_CONST", (0,)), Instr("LOAD_CONST", (0.0,)))
        nested_tuple1 = (0,)
        nested_tuple1 = (nested_tuple1,)
        nested_tuple2 = (0.0,)
        nested_tuple2 = (nested_tuple2,)
        self.assertNotEqual(
            Instr("LOAD_CONST", nested_tuple1), Instr("LOAD_CONST", nested_tuple2)
        )

        # frozenset
        self.assertNotEqual(
            Instr("LOAD_CONST", frozenset({0})), Instr("LOAD_CONST", frozenset({0.0}))
        )

    def test_stack_effects(self):
        # Verify all opcodes are handled and that "jump=None" really returns
        # the max of the other cases.
        from bytecode.concrete import ConcreteInstr

        def check_pre_post(instr, jump):
            effect = instr.stack_effect(jump)
            pre, post = instr.pre_and_post_stack_effect(jump)
            self.assertEqual(pre + post, effect)
            return effect

        def check(instr):
            jump = check_pre_post(instr, jump=True)
            no_jump = check_pre_post(instr, jump=False)
            max_effect = check_pre_post(instr, jump=None)
            self.assertEqual(instr.stack_effect(), max_effect)
            self.assertEqual(max_effect, max(jump, no_jump))

            if not instr.has_jump():
                self.assertEqual(jump, no_jump)

        for name, op in opcode.opmap.items():
            if sys.version_info >= (3, 12) and op >= opcode.MIN_INSTRUMENTED_OPCODE:
                continue
            print(name)
            with self.subTest(name):
                # Use ConcreteInstr instead of Instr because it doesn't care
                # what kind of argument it is constructed with.
                # The 0 handles the CACHE case
                if not opcode_has_argument(op) and op != 0:
                    check(ConcreteInstr(name))
                else:
                    for arg in range(256):
                        check(ConcreteInstr(name, arg))

        # LOAD_CONST uses a concrete python object as its oparg, however, in
        #       dis.stack_effect(opcode.opmap['LOAD_CONST'], oparg),
        # oparg should be the index of that python object in the constants.
        #
        # Fortunately, for an instruction whose oparg isn't equivalent to its
        # form in binary files(pyc format), the stack effect is a
        # constant which does not depend on its oparg.
        #
        # The second argument of dis.stack_effect cannot be
        # more than 2**31 - 1. If stack effect of an instruction is
        # independent of its oparg, we pass 0 as the second argument
        # of dis.stack_effect.
        # (As a result we can calculate stack_effect for
        #  any LOAD_CONST instructions, even for large integers)

        for arg in 2**31, 2**32, 2**63, 2**64, -1:
            self.assertEqual(Instr("LOAD_CONST", arg).stack_effect(), 1)

    def test_code_object_containing_mutable_data(self):
        from types import CodeType

        from bytecode import Bytecode, Instr

        def f():
            def g():
                # Under Python 3.12+ we need a temporary var to be sure we use
                # LOAD_CONST rather than RETURN_CONST
                a = "value"
                return a

            return g

        f_code = Bytecode.from_code(f.__code__)
        instr_load_code = None
        mutable_datum = [4, 2]

        for each in f_code:
            if (
                isinstance(each, Instr)
                and each.name == "LOAD_CONST"
                and isinstance(each.arg, CodeType)
            ):
                instr_load_code = each
                break

        self.assertIsNotNone(instr_load_code)

        g_code = Bytecode.from_code(instr_load_code.arg)
        # Under Python 3.11+, the first instruction is not LOAD_CONST but RESUME
        for instr in g_code:
            if isinstance(each, Instr) and instr.name == "LOAD_CONST":
                instr.arg = mutable_datum
        instr_load_code.arg = g_code.to_code()
        f.__code__ = f_code.to_code()

        self.assertIs(f()(), mutable_datum)


class CompareTests(TestCase):
    def test_compare_ops(self):
        from bytecode import Bytecode, Instr

        def f():
            pass

        params = zip(iter(Compare), (True, True, False, True, False, False))
        for cmp, expected in params:
            for cast in (False, True) if PY313 else (False,):
                with self.subTest(cmp):
                    operation = Compare(cmp + (16 if cast else 0))
                    print(f"Subtest: {operation.name}")
                    bcode = Bytecode(
                        ([Instr("RESUME", 0)] if sys.version_info >= (3, 11) else [])
                        + [
                            Instr("LOAD_CONST", 24),
                            Instr("LOAD_CONST", 42),
                            Instr("COMPARE_OP", operation),
                            Instr("RETURN_VALUE"),
                        ]
                    )
                    bcode.update_flags()
                    f.__code__ = bcode.to_code()
                    self.assertIs(f(), expected)


if __name__ == "__main__":
    unittest.main()  # pragma: no cover

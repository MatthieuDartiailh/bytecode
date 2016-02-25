#!/usr/bin/env python3
import contextlib
import io
import textwrap
import unittest

import bytecode
from bytecode.tests import disassemble


class DumpCodeTests(unittest.TestCase):
    def check_dump(self, code, expected):
        with contextlib.redirect_stdout(io.StringIO()) as stderr:
            bytecode.dump(code)
            output = stderr.getvalue()

        self.assertEqual(output, expected)

    def test_bytecode(self):
        source = """
            def func(test):
                if test == 1:
                    return 1
                elif test == 2:
                    return 2
                return 3
        """
        code = disassemble(source, function=True)
        code = code.to_bytecode()

        expected = textwrap.dedent("""
            label_instr0:
                LOAD_FAST 'test'
                LOAD_CONST 1
                COMPARE_OP 2
                POP_JUMP_IF_FALSE <label_instr7>
                LOAD_CONST 1
                RETURN_VALUE

            label_instr7:
                LOAD_FAST 'test'
                LOAD_CONST 2
                COMPARE_OP 2
                POP_JUMP_IF_FALSE <label_instr14>
                LOAD_CONST 2
                RETURN_VALUE

            label_instr14:
                LOAD_CONST 3
                RETURN_VALUE

        """).lstrip()
        self.check_dump(code, expected)

    def test_bytecode_blocks(self):
        source = """
            def func(test):
                if test == 1:
                    return 1
                elif test == 2:
                    return 2
                return 3
        """
        code = disassemble(source, function=True)

        expected = textwrap.dedent("""
            label_block1:
                LOAD_FAST 'test'
                LOAD_CONST 1
                COMPARE_OP 2
                POP_JUMP_IF_FALSE <label_block2>
                LOAD_CONST 1
                RETURN_VALUE

            label_block2:
                LOAD_FAST 'test'
                LOAD_CONST 2
                COMPARE_OP 2
                POP_JUMP_IF_FALSE <label_block3>
                LOAD_CONST 2
                RETURN_VALUE

            label_block3:
                LOAD_CONST 3
                RETURN_VALUE

        """).lstrip()
        self.check_dump(code, expected)

    def test_concrete_bytecode(self):
        source = """
            def func(test):
                if test == 1:
                    return 1
                elif test == 2:
                    return 2
                return 3
        """
        code = disassemble(source, function=True)
        code = code.to_concrete_bytecode()

        expected = """
  2  0    LOAD_FAST(0)
     3    LOAD_CONST(1)
     6    COMPARE_OP(2)
     9    POP_JUMP_IF_FALSE(16)
  3 12    LOAD_CONST(1)
    15    RETURN_VALUE
  4 16    LOAD_FAST(0)
    19    LOAD_CONST(2)
    22    COMPARE_OP(2)
    25    POP_JUMP_IF_FALSE(32)
  5 28    LOAD_CONST(2)
    31    RETURN_VALUE
  6 32    LOAD_CONST(3)
    35    RETURN_VALUE
""".lstrip("\n")
        self.check_dump(code, expected)


class MiscTests(unittest.TestCase):
    def test_version(self):
        import setup
        self.assertEqual(bytecode.__version__, setup.VERSION)


if __name__ == "__main__":
    unittest.main()

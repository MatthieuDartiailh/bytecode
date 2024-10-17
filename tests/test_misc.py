#!/usr/bin/env python3
import contextlib
import io
import sys
import textwrap
import unittest

import bytecode
from bytecode import BasicBlock, Bytecode, ControlFlowGraph, Instr, Label
from bytecode.concrete import OFFSET_AS_INSTRUCTION
from bytecode.utils import PY313

from . import disassemble


class DumpCodeTests(unittest.TestCase):
    maxDiff = 80 * 100

    def check_dump_bytecode(self, code, expected, lineno=None):
        with contextlib.redirect_stdout(io.StringIO()) as stderr:
            if lineno is not None:
                bytecode.dump_bytecode(code, lineno=True)
            else:
                bytecode.dump_bytecode(code)
            output = stderr.getvalue()

        self.assertMultiLineEqual(output, expected)

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

        # without line numbers
        enum_repr = "<Compare.EQ_CAST: 18>" if PY313 else "<Compare.EQ: 2>"
        if sys.version_info >= (3, 12):
            expected = f"""
    RESUME 0
    LOAD_FAST 'test'
    LOAD_CONST 1
    COMPARE_OP {enum_repr}
    POP_JUMP_IF_FALSE <label_instr6>
    RETURN_CONST 1

label_instr6:
    LOAD_FAST 'test'
    LOAD_CONST 2
    COMPARE_OP {enum_repr}
    POP_JUMP_IF_FALSE <label_instr12>
    RETURN_CONST 2

label_instr12:
    RETURN_CONST 3

    """
        elif sys.version_info >= (3, 11):
            expected = f"""
    RESUME 0
    LOAD_FAST 'test'
    LOAD_CONST 1
    COMPARE_OP {enum_repr}
    POP_JUMP_FORWARD_IF_FALSE <label_instr7>
    LOAD_CONST 1
    RETURN_VALUE

label_instr7:
    LOAD_FAST 'test'
    LOAD_CONST 2
    COMPARE_OP {enum_repr}
    POP_JUMP_FORWARD_IF_FALSE <label_instr14>
    LOAD_CONST 2
    RETURN_VALUE

label_instr14:
    LOAD_CONST 3
    RETURN_VALUE

    """
        else:
            expected = f"""
    LOAD_FAST 'test'
    LOAD_CONST 1
    COMPARE_OP {enum_repr}
    POP_JUMP_IF_FALSE <label_instr6>
    LOAD_CONST 1
    RETURN_VALUE

label_instr6:
    LOAD_FAST 'test'
    LOAD_CONST 2
    COMPARE_OP {enum_repr}
    POP_JUMP_IF_FALSE <label_instr13>
    LOAD_CONST 2
    RETURN_VALUE

label_instr13:
    LOAD_CONST 3
    RETURN_VALUE

        """
        self.check_dump_bytecode(code, expected[1:].rstrip(" "))

        # with line numbers
        if sys.version_info >= (3, 12):
            expected = f"""
    L.  1   0: RESUME 0
    L.  2   1: LOAD_FAST 'test'
            2: LOAD_CONST 1
            3: COMPARE_OP {enum_repr}
            4: POP_JUMP_IF_FALSE <label_instr6>
    L.  3   5: RETURN_CONST 1

label_instr6:
    L.  4   7: LOAD_FAST 'test'
            8: LOAD_CONST 2
            9: COMPARE_OP {enum_repr}
           10: POP_JUMP_IF_FALSE <label_instr12>
    L.  5  11: RETURN_CONST 2

label_instr12:
    L.  6  13: RETURN_CONST 3

    """
        elif sys.version_info >= (3, 11):
            expected = f"""
    L.  1   0: RESUME 0
    L.  2   1: LOAD_FAST 'test'
            2: LOAD_CONST 1
            3: COMPARE_OP {enum_repr}
            4: POP_JUMP_FORWARD_IF_FALSE <label_instr7>
    L.  3   5: LOAD_CONST 1
            6: RETURN_VALUE

label_instr7:
    L.  4   8: LOAD_FAST 'test'
            9: LOAD_CONST 2
           10: COMPARE_OP {enum_repr}
           11: POP_JUMP_FORWARD_IF_FALSE <label_instr14>
    L.  5  12: LOAD_CONST 2
           13: RETURN_VALUE

label_instr14:
    L.  6  15: LOAD_CONST 3
           16: RETURN_VALUE

    """
        else:
            expected = f"""
    L.  2   0: LOAD_FAST 'test'
            1: LOAD_CONST 1
            2: COMPARE_OP {enum_repr}
            3: POP_JUMP_IF_FALSE <label_instr6>
    L.  3   4: LOAD_CONST 1
            5: RETURN_VALUE

label_instr6:
    L.  4   7: LOAD_FAST 'test'
            8: LOAD_CONST 2
            9: COMPARE_OP {enum_repr}
           10: POP_JUMP_IF_FALSE <label_instr13>
    L.  5  11: LOAD_CONST 2
           12: RETURN_VALUE

label_instr13:
    L.  6  14: LOAD_CONST 3
           15: RETURN_VALUE

        """
        self.check_dump_bytecode(code, expected[1:].rstrip(" "), lineno=True)

    def test_bytecode_broken_label(self):
        label = Label()
        code = Bytecode([Instr("JUMP_FORWARD", label)])

        expected = "    JUMP_FORWARD <error: unknown label>\n\n"
        self.check_dump_bytecode(code, expected)

    def test_blocks_broken_jump(self):
        block = BasicBlock()
        code = ControlFlowGraph()
        code[0].append(Instr("JUMP_FORWARD", block))

        expected = textwrap.dedent(
            """
            block1:
                JUMP_FORWARD <error: unknown block>

        """
        ).lstrip("\n")
        self.check_dump_bytecode(code, expected)

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
        code = ControlFlowGraph.from_bytecode(code)

        # without line numbers
        enum_repr = "<Compare.EQ_CAST: 18>" if PY313 else "<Compare.EQ: 2>"
        if sys.version_info >= (3, 12):
            expected = textwrap.dedent(
                f"""
            block1:
                RESUME 0
                LOAD_FAST 'test'
                LOAD_CONST 1
                COMPARE_OP {enum_repr}
                POP_JUMP_IF_FALSE <block3>
                -> block2

            block2:
                RETURN_CONST 1

            block3:
                LOAD_FAST 'test'
                LOAD_CONST 2
                COMPARE_OP {enum_repr}
                POP_JUMP_IF_FALSE <block5>
                -> block4

            block4:
                RETURN_CONST 2

            block5:
                RETURN_CONST 3

            """
            )
        elif sys.version_info >= (3, 11):
            expected = textwrap.dedent(
                f"""
            block1:
                RESUME 0
                LOAD_FAST 'test'
                LOAD_CONST 1
                COMPARE_OP {enum_repr}
                POP_JUMP_FORWARD_IF_FALSE <block3>
                -> block2

            block2:
                LOAD_CONST 1
                RETURN_VALUE

            block3:
                LOAD_FAST 'test'
                LOAD_CONST 2
                COMPARE_OP {enum_repr}
                POP_JUMP_FORWARD_IF_FALSE <block5>
                -> block4

            block4:
                LOAD_CONST 2
                RETURN_VALUE

            block5:
                LOAD_CONST 3
                RETURN_VALUE

            """
            )
        else:
            expected = textwrap.dedent(
                f"""
                block1:
                    LOAD_FAST 'test'
                    LOAD_CONST 1
                    COMPARE_OP {enum_repr}
                    POP_JUMP_IF_FALSE <block3>
                    -> block2

                block2:
                    LOAD_CONST 1
                    RETURN_VALUE

                block3:
                    LOAD_FAST 'test'
                    LOAD_CONST 2
                    COMPARE_OP {enum_repr}
                    POP_JUMP_IF_FALSE <block5>
                    -> block4

                block4:
                    LOAD_CONST 2
                    RETURN_VALUE

                block5:
                    LOAD_CONST 3
                    RETURN_VALUE

            """
            )
        self.check_dump_bytecode(code, expected.lstrip())

        # with line numbers
        if sys.version_info >= (3, 12):
            expected = textwrap.dedent(
                f"""
            block1:
                L.  1   0: RESUME 0
                L.  2   1: LOAD_FAST 'test'
                        2: LOAD_CONST 1
                        3: COMPARE_OP {enum_repr}
                        4: POP_JUMP_IF_FALSE <block3>
                -> block2

            block2:
                L.  3   0: RETURN_CONST 1

            block3:
                L.  4   0: LOAD_FAST 'test'
                        1: LOAD_CONST 2
                        2: COMPARE_OP {enum_repr}
                        3: POP_JUMP_IF_FALSE <block5>
                -> block4

            block4:
                L.  5   0: RETURN_CONST 2

            block5:
                L.  6   0: RETURN_CONST 3

            """
            )
        elif sys.version_info >= (3, 11):
            expected = textwrap.dedent(
                f"""
            block1:
                L.  1   0: RESUME 0
                L.  2   1: LOAD_FAST 'test'
                        2: LOAD_CONST 1
                        3: COMPARE_OP {enum_repr}
                        4: POP_JUMP_FORWARD_IF_FALSE <block3>
                -> block2

            block2:
                L.  3   0: LOAD_CONST 1
                        1: RETURN_VALUE

            block3:
                L.  4   0: LOAD_FAST 'test'
                        1: LOAD_CONST 2
                        2: COMPARE_OP {enum_repr}
                        3: POP_JUMP_FORWARD_IF_FALSE <block5>
                -> block4

            block4:
                L.  5   0: LOAD_CONST 2
                        1: RETURN_VALUE

            block5:
                L.  6   0: LOAD_CONST 3
                        1: RETURN_VALUE

            """
            )
        else:
            expected = textwrap.dedent(
                f"""
                block1:
                    L.  2   0: LOAD_FAST 'test'
                            1: LOAD_CONST 1
                            2: COMPARE_OP {enum_repr}
                            3: POP_JUMP_IF_FALSE <block3>
                    -> block2

                block2:
                    L.  3   0: LOAD_CONST 1
                            1: RETURN_VALUE

                block3:
                    L.  4   0: LOAD_FAST 'test'
                            1: LOAD_CONST 2
                            2: COMPARE_OP {enum_repr}
                            3: POP_JUMP_IF_FALSE <block5>
                    -> block4

                block4:
                    L.  5   0: LOAD_CONST 2
                            1: RETURN_VALUE

                block5:
                    L.  6   0: LOAD_CONST 3
                            1: RETURN_VALUE

            """
            )
        self.check_dump_bytecode(code, expected.lstrip(), lineno=True)

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

        # without line numbers
        if sys.version_info >= (3, 13):
            # COMPARE_OP use the 4 lowest bits as a cache
            expected = """
  0    RESUME 0
  2    LOAD_FAST 0
  4    LOAD_CONST 1
  6    COMPARE_OP 88
  8    CACHE 0
 10    POP_JUMP_IF_FALSE 1
 12    CACHE 0
 14    RETURN_CONST 1
 16    LOAD_FAST 0
 18    LOAD_CONST 2
 20    COMPARE_OP 88
 22    CACHE 0
 24    POP_JUMP_IF_FALSE 1
 26    CACHE 0
 28    RETURN_CONST 2
 30    RETURN_CONST 3
"""

        elif sys.version_info >= (3, 12):
            # COMPARE_OP use the 4 lowest bits as a cache
            expected = """
  0    RESUME 0
  2    LOAD_FAST 0
  4    LOAD_CONST 1
  6    COMPARE_OP 40
  8    CACHE 0
 10    POP_JUMP_IF_FALSE 1
 12    RETURN_CONST 1
 14    LOAD_FAST 0
 16    LOAD_CONST 2
 18    COMPARE_OP 40
 20    CACHE 0
 22    POP_JUMP_IF_FALSE 1
 24    RETURN_CONST 2
 26    RETURN_CONST 3
"""
        elif sys.version_info >= (3, 11):
            expected = """
  0    RESUME 0
  2    LOAD_FAST 0
  4    LOAD_CONST 1
  6    COMPARE_OP 2
  8    CACHE 0
 10    CACHE 0
 12    POP_JUMP_FORWARD_IF_FALSE 2
 14    LOAD_CONST 1
 16    RETURN_VALUE
 18    LOAD_FAST 0
 20    LOAD_CONST 2
 22    COMPARE_OP 2
 24    CACHE 0
 26    CACHE 0
 28    POP_JUMP_FORWARD_IF_FALSE 2
 30    LOAD_CONST 2
 32    RETURN_VALUE
 34    LOAD_CONST 3
 36    RETURN_VALUE
"""
        else:
            expected = f"""
  0    LOAD_FAST 0
  2    LOAD_CONST 1
  4    COMPARE_OP 2
  6    POP_JUMP_IF_FALSE {6 if OFFSET_AS_INSTRUCTION else 12}
  8    LOAD_CONST 1
 10    RETURN_VALUE
 12    LOAD_FAST 0
 14    LOAD_CONST 2
 16    COMPARE_OP 2
 18    POP_JUMP_IF_FALSE {12 if OFFSET_AS_INSTRUCTION else 24}
 20    LOAD_CONST 2
 22    RETURN_VALUE
 24    LOAD_CONST 3
 26    RETURN_VALUE
"""
        self.check_dump_bytecode(code, expected.lstrip("\n"))

        # with line numbers
        if sys.version_info >= (3, 13):
            expected = """
L.  1   0: RESUME 0
L.  2   2: LOAD_FAST 0
        4: LOAD_CONST 1
        6: COMPARE_OP 88
        8: CACHE 0
       10: POP_JUMP_IF_FALSE 1
       12: CACHE 0
L.  3  14: RETURN_CONST 1
L.  4  16: LOAD_FAST 0
       18: LOAD_CONST 2
       20: COMPARE_OP 88
       22: CACHE 0
       24: POP_JUMP_IF_FALSE 1
       26: CACHE 0
L.  5  28: RETURN_CONST 2
L.  6  30: RETURN_CONST 3
"""
        elif sys.version_info >= (3, 12):
            expected = """
L.  1   0: RESUME 0
L.  2   2: LOAD_FAST 0
        4: LOAD_CONST 1
        6: COMPARE_OP 40
        8: CACHE 0
       10: POP_JUMP_IF_FALSE 1
L.  3  12: RETURN_CONST 1
L.  4  14: LOAD_FAST 0
       16: LOAD_CONST 2
       18: COMPARE_OP 40
       20: CACHE 0
       22: POP_JUMP_IF_FALSE 1
L.  5  24: RETURN_CONST 2
L.  6  26: RETURN_CONST 3
"""
        elif sys.version_info >= (3, 11):
            expected = """
L.  1   0: RESUME 0
L.  2   2: LOAD_FAST 0
        4: LOAD_CONST 1
        6: COMPARE_OP 2
        8: CACHE 0
       10: CACHE 0
       12: POP_JUMP_FORWARD_IF_FALSE 2
L.  3  14: LOAD_CONST 1
       16: RETURN_VALUE
L.  4  18: LOAD_FAST 0
       20: LOAD_CONST 2
       22: COMPARE_OP 2
       24: CACHE 0
       26: CACHE 0
       28: POP_JUMP_FORWARD_IF_FALSE 2
L.  5  30: LOAD_CONST 2
       32: RETURN_VALUE
L.  6  34: LOAD_CONST 3
       36: RETURN_VALUE
"""
        else:
            expected = f"""
L.  2   0: LOAD_FAST 0
        2: LOAD_CONST 1
        4: COMPARE_OP 2
        6: POP_JUMP_IF_FALSE {6 if OFFSET_AS_INSTRUCTION else 12}
L.  3   8: LOAD_CONST 1
       10: RETURN_VALUE
L.  4  12: LOAD_FAST 0
       14: LOAD_CONST 2
       16: COMPARE_OP 2
       18: POP_JUMP_IF_FALSE {12 if OFFSET_AS_INSTRUCTION else 24}
L.  5  20: LOAD_CONST 2
       22: RETURN_VALUE
L.  6  24: LOAD_CONST 3
       26: RETURN_VALUE
"""
        self.check_dump_bytecode(code, expected.lstrip("\n"), lineno=True)

    def test_type_validation(self):
        class T:
            first_lineno = 1

        with self.assertRaises(TypeError):
            bytecode.dump_bytecode(T())


if __name__ == "__main__":
    unittest.main()  # pragma: no cover

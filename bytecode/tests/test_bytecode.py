#!/usr/bin/env python3
import textwrap
import unittest
from bytecode import Label, Instr, Bytecode
from bytecode.tests import TestCase, get_code, disassemble


class BytecodeTests(TestCase):
    maxDiff = 80 * 100

    def test_constructor(self):
        code = Bytecode()
        self.assertEqual(code.name, "<module>")
        self.assertEqual(code.filename, "<string>")
        self.assertEqual(code.flags, 0)
        self.assertEqual(code, [])

    def test_from_code(self):
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
                         [Instr('LOAD_NAME', 'test', lineno=1),
                          Instr('POP_JUMP_IF_FALSE', label_else, lineno=1),
                          Instr('LOAD_CONST', 1, lineno=2),
                          Instr('STORE_NAME', 'x', lineno=2),
                          Instr('JUMP_FORWARD', label_exit, lineno=2),
                          label_else,
                              Instr('LOAD_CONST', 2, lineno=4),
                              Instr('STORE_NAME', 'x', lineno=4),
                          label_exit,
                              Instr('LOAD_CONST', None, lineno=4),
                              Instr('RETURN_VALUE', lineno=4)])

    def test_from_code_freevars(self):
        ns = {}
        exec(textwrap.dedent('''
            def create_func():
                x = 1
                def func():
                    return x
                return func

            func = create_func()
        '''), ns, ns)
        code = ns['func'].__code__

        bytecode = Bytecode.from_code(code)
        self.assertEqual(bytecode,
                         [Instr('LOAD_DEREF', 'x', lineno=5),
                          Instr('RETURN_VALUE', lineno=5)])

    def test_from_code_load_fast(self):
        code = get_code("""
            def func():
                x = 33
                y = x
        """, function=True)
        code = Bytecode.from_code(code)
        self.assertEqual(code,
                         [Instr('LOAD_CONST', 33, lineno=2),
                          Instr('STORE_FAST', 'x', lineno=2),
                          Instr('LOAD_FAST', 'x', lineno=3),
                          Instr('STORE_FAST', 'y', lineno=3),
                          Instr('LOAD_CONST', None, lineno=3),
                          Instr('RETURN_VALUE', lineno=3)])


if __name__ == "__main__":
    unittest.main()

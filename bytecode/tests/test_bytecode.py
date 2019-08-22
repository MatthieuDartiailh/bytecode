#!/usr/bin/env python3
import textwrap
import unittest
from bytecode import Label, Instr, FreeVar, Bytecode, SetLineno, ConcreteInstr
from bytecode.tests import TestCase, get_code


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
            Bytecode([123])

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
                         [Instr('LOAD_DEREF', FreeVar('x'), lineno=5),
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

    def test_setlineno(self):
        # x = 7
        # y = 8
        # z = 9
        code = Bytecode()
        code.first_lineno = 3
        code.extend([Instr("LOAD_CONST", 7),
                     Instr("STORE_NAME", 'x'),
                     SetLineno(4),
                     Instr("LOAD_CONST", 8),
                     Instr("STORE_NAME", 'y'),
                     SetLineno(5),
                     Instr("LOAD_CONST", 9),
                     Instr("STORE_NAME", 'z')])

        concrete = code.to_concrete_bytecode()
        self.assertEqual(concrete.consts, [7, 8, 9])
        self.assertEqual(concrete.names, ['x', 'y', 'z'])
        code.extend([ConcreteInstr("LOAD_CONST", 0, lineno=3),
                     ConcreteInstr("STORE_NAME", 0, lineno=3),
                     ConcreteInstr("LOAD_CONST", 1, lineno=4),
                     ConcreteInstr("STORE_NAME", 1, lineno=4),
                     ConcreteInstr("LOAD_CONST", 2, lineno=5),
                     ConcreteInstr("STORE_NAME", 2, lineno=5)])

    def test_to_code(self):
        code = Bytecode()
        code.first_lineno = 50
        code.extend([Instr("LOAD_NAME", "print"),
                     Instr("LOAD_CONST", "%s"),
                     Instr("LOAD_GLOBAL", "a"),
                     Instr("BINARY_MODULO"),
                     Instr("CALL_FUNCTION", 1),
                     Instr("RETURN_VALUE")])
        co = code.to_code()
        # hopefully this is obvious from inspection? :-)
        self.assertEqual(co.co_stacksize, 3)

        co = code.to_code(stacksize=42)
        self.assertEqual(co.co_stacksize, 42)


if __name__ == "__main__":
    unittest.main()

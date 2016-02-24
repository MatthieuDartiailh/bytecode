# FIXME: these tests requires a Python patched with the PEP 511

import bytecode
import peephole_opt
import sys
import textwrap
import types
import unittest
from bytecode import Instr
from unittest import mock


def LOAD_CONST(arg, lineno=1):
    return Instr(lineno, 'LOAD_CONST', arg)

def LOAD_NAME(arg, lineno=1):
    return Instr(lineno, 'LOAD_NAME', arg)

def STORE_NAME(arg, lineno=1):
    return Instr(lineno, 'STORE_NAME', arg)


class Tests(unittest.TestCase):
    maxDiff = 80 * 100

    def setUp(self):
        # disable the C peephole optimizer
        if hasattr(sys, 'get_code_transformers'):
            transformers = sys.get_code_transformers()
            self.addCleanup(sys.set_code_transformers, transformers)
            sys.set_code_transformers([])
        else:
            raise Exception("cannot disable the C peephole optimizer")

    def compile(self, source, function=False):
        source = textwrap.dedent(source).strip()
        orig = compile(source, '<string>', 'exec')

        if function:
            sub_code = [const for const in orig.co_consts
                        if isinstance(const, types.CodeType)]
            if len(sub_code) != 1:
                raise ValueError("unable to find function code")
            orig = sub_code[0]

        return orig

    def create_code(self, source, function=False):
        orig = self.compile(source)

        code = bytecode.Code.disassemble(orig)
        block = code[-1]

        if not function:
            block = code[-1]
            if not(block[-2].name == "LOAD_CONST"
                   and block[-2].arg == code.consts.index(None)
                   and block[-1].name == "RETURN_VALUE"):
                raise ValueError("unable to find implicit RETURN_VALUE <None>: %s"
                                 % block[-2:])
            del block[-2:]

        return code

    def _optimize(self, source, function=False):
        code = self.create_code(source, function=function)
        optimizer = peephole_opt._CodePeepholeOptimizer()
        optimizer._optimize(code)
        return code

    def assertCodeEqual(self, code, *expected_blocks):
        blocks = [list(block) for block in code]
        self.assertEqual(len(blocks), len(expected_blocks))
        for block, expected_block in zip(blocks, expected_blocks):
            self.assertListEqual(block, list(expected_block))

    def check(self, source, *expected_blocks, consts=(None,), names=None,
              function=False):
        code = self._optimize(source, function=function)

        self.assertCodeEqual(code, *expected_blocks)
        self.assertListEqual(code.consts, list(consts))
        if names is not None:
            self.assertListEqual(list(names), code.names)

    def check_dont_optimize(self, source):
        code = self.create_code(source)
        code2 = self._optimize(source)
        self.assertEqual(code, code2)

    def test_unary_op(self):
        def check_unary_op(op, value, result):
            self.check('x = %s(%r)' % (op, value),
                       (LOAD_CONST(2), STORE_NAME(0)),
                       consts=(value, None, result))

        check_unary_op('+', 2, 2)
        check_unary_op('-', 3, -3)
        check_unary_op('~', 5, -6)

    def test_bin_op(self):
        def check_bin_op(left, op, right, result):
            self.check('x = %r %s %r' % (left, op, right),
                       (LOAD_CONST(3), STORE_NAME(0)),
                       consts=(left, right, None, result))

        check_bin_op(10,  '+', 20, 30)
        check_bin_op(5, '-', 1, 4)
        check_bin_op(5, '*', 3, 15)
        check_bin_op(10, '/', 3, 10 / 3)
        check_bin_op(10, '//', 3, 3)
        check_bin_op(10, '%', 3, 1)
        check_bin_op(2, '**', 8, 256)
        check_bin_op(1, '<<', 3, 8)
        check_bin_op(16, '>>', 3, 2)
        check_bin_op(10, '&', 3, 2)
        check_bin_op(2, '|', 3, 3)
        check_bin_op(2, '^', 3, 1)

    def test_chain_operations(self):
        self.check('x = 1 + 3 + 7',
                   (LOAD_CONST(5), STORE_NAME(0)),
                   consts=(1, 3, 7, None, 4, 11))

        self.check('x = ~(~(5))',
                   (LOAD_CONST(3), STORE_NAME(0)),
                   consts=(5, None, -6, 5))

        self.check("events = [(0, 'call'), (1, 'line'), (-3, 'call')]",
                   (LOAD_CONST(6),
                    LOAD_CONST(7),
                    LOAD_CONST(9),
                    Instr(1, 'BUILD_LIST', 3),
                    STORE_NAME(0)),
                   consts=(0, 'call', 1, 'line', 3, None,
                           (0, 'call'), (1, 'line'),
                           -3, (-3, 'call')))

        zeros = (0,) * 8
        result = (1,) + zeros
        self.check('x = (1,) + (0,) * 8',
                   (LOAD_CONST(7), STORE_NAME(0)),
                   consts=[1, 0, 8, None, (1,), (0,), zeros, result])

    def test_max_size(self):
        max_size = 3
        with mock.patch.object(peephole_opt, 'MAX_SIZE', max_size):
            # optimized binary operation: size <= maximum size
            size = max_size
            result = (9,) * size
            self.check('x = (9,) * %s' % size,
                       (LOAD_CONST(4), STORE_NAME(0)),
                       consts=(9, size, None, (9,), result),
                       names=['x'])

            # don't optimize  binary operation: size > maximum size
            size = (max_size + 1)
            self.check('x = (9,) * %s' % size,
                       (LOAD_CONST(3),
                        LOAD_CONST(1),
                        Instr(1, 'BINARY_MULTIPLY'),
                        STORE_NAME(0)),
                       consts=(9, size, None, (9,)),
                       names=['x'])

    def test_bin_op_dont_optimize(self):
        self.check_dont_optimize('1 / 0')
        self.check_dont_optimize('1 // 0')
        self.check_dont_optimize('1 % 0')
        self.check_dont_optimize('1 % 1j')

    def test_build_tuple(self):
        self.check('x = (1, 2, 3)',
                   (LOAD_CONST(4), STORE_NAME(0)),
                   consts=(1, 2, 3, None, (1, 2, 3)),
                   names=['x'])

    def test_build_tuple_unpack_seq(self):
        self.check('x, = (a,)',
                   (LOAD_NAME(0), STORE_NAME(1)),
                   names=['a','x'])

        self.check('x, y = (a, b)',
                   (LOAD_NAME(0), LOAD_NAME(1),
                    Instr(1, 'ROT_TWO'),
                    STORE_NAME(2), STORE_NAME(3)),
                   names=['a', 'b', 'x', 'y'])

        self.check('x, y, z = (a, b, c)',
                   (LOAD_NAME(0), LOAD_NAME(1), LOAD_NAME(2),
                    Instr(1, 'ROT_THREE'),
                    Instr(1, 'ROT_TWO'),
                    STORE_NAME(3), STORE_NAME(4), STORE_NAME(5)),
                   names=['a', 'b', 'c', 'x', 'y', 'z'])

    def test_build_list(self):
        self.check('test = x in [1, 2, 3]',
                   (LOAD_NAME(0),
                    LOAD_CONST(4),
                    Instr(1, 'COMPARE_OP', 6),
                    STORE_NAME(1)),
                   consts=(1, 2, 3, None, (1, 2, 3)),
                   names=['x', 'test'])

    def test_build_list_unpack_seq(self):
        self.check('x, = [a]',
                   (LOAD_NAME(0), STORE_NAME(1)),
                   names=['a','x'])

        self.check('x, y = [a, b]',
                   (LOAD_NAME(0), LOAD_NAME(1),
                    Instr(1, 'ROT_TWO'),
                    STORE_NAME(2), STORE_NAME(3)),
                   names=['a', 'b', 'x', 'y'])

        self.check('x, y, z = [a, b, c]',
                   (LOAD_NAME(0), LOAD_NAME(1), LOAD_NAME(2),
                    Instr(1, 'ROT_THREE'),
                    Instr(1, 'ROT_TWO'),
                    STORE_NAME(3), STORE_NAME(4), STORE_NAME(5)),
                   names=['a', 'b', 'c', 'x', 'y', 'z'])

    def test_build_set(self):
        self.check('test = x in {1, 2, 3}',
                   (LOAD_NAME(0),
                    LOAD_CONST(4),
                    Instr(1, 'COMPARE_OP', 6),
                    STORE_NAME(1)),
                   consts=(1, 2, 3, None, frozenset((1, 2, 3))),
                   names=['x', 'test'])

    def test_compare_not(self):
        for source, op in (
            ('x = not(a in b)', 7),
            ('x = not(a not in b)', 6),
            ('x = not(a is b)', 9),
            ('x = not(a is not b)', 8),
        ):
            self.check(source,
                       (LOAD_NAME(0),
                        LOAD_NAME(1),
                        Instr(1, 'COMPARE_OP', op),
                        STORE_NAME(2)))

    def test_dont_optimize(self):
        self.check('x = 1 < 2',
                   (LOAD_CONST(0),
                    LOAD_CONST(1),
                    Instr(1, 'COMPARE_OP', 0),
                    STORE_NAME(0)),
                   consts=[1, 2, None])

        self.check('x = (10, 20, 30)[1:]',
                   (LOAD_CONST(5),
                    LOAD_CONST(3),
                    LOAD_CONST(4),
                    Instr(1, 'BUILD_SLICE', 2),
                    Instr(1, 'BINARY_SUBSCR'),
                    STORE_NAME(0)),
                   consts=[10, 20, 30, 1, None, (10, 20, 30)])

    def test_optimize_code_obj(self):
        # x = 1 + 2
        block = [
            Instr(1, 'LOAD_CONST', 0),
            Instr(1, 'LOAD_CONST', 1),
            Instr(1, 'BINARY_ADD'),
            Instr(1, 'STORE_NAME', 0),
            Instr(1, 'LOAD_CONST', 2),
            Instr(1, 'RETURN_VALUE'),
        ]
        code_noopt = bytecode.Code('test', 'test.py', 0)
        code_noopt.consts = [1, 2, None]
        code_noopt.names.append('x')
        code_noopt[0][:] = block
        noopt = code_noopt.assemble()

        optimizer = peephole_opt._CodePeepholeOptimizer()
        optim = optimizer.optimize(noopt)

        code = bytecode.Code.disassemble(optim)

        expected = [
            Instr(1, 'LOAD_CONST', 3),
            Instr(1, 'STORE_NAME', 0),
            Instr(1, 'LOAD_CONST', 2),
            Instr(1, 'RETURN_VALUE'),
        ]
        self.assertCodeEqual(code, expected)

    def test_mimicks_c_impl_long_code(self):
        with mock.patch.object(peephole_opt, 'MIMICK_C_IMPL', True):
            source = 'x=1'
            code = self.compile(source)
            # -4 to ignore LOAD_CONST <None>; RETURN_VALUE
            codelen = len(code.co_code) - 4

            # create code bigger than 32,700 bytes
            minlen = 32700
            ninstr = minlen // codelen + 1
            source = '; '.join('x=%s' % i for i in range(ninstr))
            noopt = self.compile(source)
            self.assertGreater(len(noopt.co_code), minlen)

            # don't optimize if the code is bigger than 32,700 bytes
            optimizer = peephole_opt._CodePeepholeOptimizer()
            optim = optimizer.optimize(noopt)

            self.assertIs(optim, noopt)

    def test_mimicks_c_impl_no_return_value(self):
        with mock.patch.object(peephole_opt, 'MIMICK_C_IMPL', True):
            # create (invalid) code without RETURN_VALUE
            block = [
                Instr(1, 'LOAD_CONST', 0),
                Instr(1, 'POP_TOP'),
            ]
            code_noopt = bytecode.Code('test', 'test.py', 0)
            code_noopt.consts = [None]
            code_noopt[0][:] = block
            noopt = code_noopt.assemble()

            # don't optimize if the last instruction of the code
            # is not RETURN_VALUE
            optimizer = peephole_opt._CodePeepholeOptimizer()
            optim = optimizer.optimize(noopt)

            self.assertIs(optim, noopt)

    def test_mimicks_c_impl_extended_arg(self):
        with mock.patch.object(peephole_opt, 'MIMICK_C_IMPL', True):
            # create code with EXTENDED_ARG opcode
            block = [
                Instr(1, 'LOAD_CONST', 3 << 16),
                Instr(1, 'POP_TOP'),
                Instr(1, 'LOAD_CONST', 0),
                Instr(1, 'LOAD_CONST', 1),
                Instr(1, 'BINARY_ADD'),
                Instr(1, 'STORE_NAME', 0),
                Instr(1, 'LOAD_CONST', 2),
                Instr(1, 'RETURN_VALUE'),
            ]
            code_noopt = bytecode.Code('test', 'test.py', 0)
            code_noopt.consts = [1, 2, None]
            code_noopt[0][:] = block
            noopt = code_noopt.assemble()

            # don't optimize if the code contains EXTENDED_ARG opcode
            optimizer = peephole_opt._CodePeepholeOptimizer()
            optim = optimizer.optimize(noopt)

            self.assertIs(optim, noopt)


if __name__ == "__main__":
    unittest.main()

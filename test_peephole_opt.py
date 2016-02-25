# FIXME: these tests requires a Python patched with the PEP 511

import peephole_opt
import sys
import textwrap
import types
import unittest
from bytecode import Instr, ConcreteInstr, BytecodeBlocks, ConcreteBytecode
from unittest import mock
from test_utils import TestCase


def LOAD_CONST(arg, lineno=1):
    return Instr(lineno, 'LOAD_CONST', arg)

def LOAD_NAME(arg, lineno=1):
    return Instr(lineno, 'LOAD_NAME', arg)

def STORE_NAME(arg, lineno=1):
    return Instr(lineno, 'STORE_NAME', arg)


class Tests(TestCase):
    maxDiff = 80 * 100

    @staticmethod
    def setUpClass():
        if not hasattr(sys, 'get_code_transformers'):
            raise Exception("cannot disable the C peephole optimizer: "
                            "need a Python patched with the PEP 511!")

    def setUp(self):
        # disable the C peephole optimizer
        transformers = sys.get_code_transformers()
        self.addCleanup(sys.set_code_transformers, transformers)
        sys.set_code_transformers([])

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

    # FIXME: move to test_utils
    def create_bytecode(self, source, function=False):
        code = self.compile(source, function=function)

        bytecode = BytecodeBlocks.from_code(code)

        if not function:
            block = bytecode[-1]
            if not(block[-2].name == "LOAD_CONST"
                   and block[-2].arg is None
                   and block[-1].name == "RETURN_VALUE"):
                raise ValueError("unable to find implicit RETURN_VALUE <None>: %s"
                                 % block[-2:])
            del block[-2:]

        return bytecode

    def optimize_bytecode(self, source, function=False):
        bytecode = self.create_bytecode(source, function=function)
        optimizer = peephole_opt._CodePeepholeOptimizer()
        optimizer._optimize(bytecode)
        return bytecode

    def check(self, source, *expected_blocks, function=False):
        bytecode = self.optimize_bytecode(source, function=function)

        self.assertBlocksEqual(bytecode, *expected_blocks)

    def check_dont_optimize(self, source):
        noopt = self.create_bytecode(source)
        optim = self.optimize_bytecode(source)
        self.assertEqual(optim, noopt)

    def test_unary_op(self):
        def check_unary_op(op, value, result):
            self.check('x = %s(%r)' % (op, value),
                       (LOAD_CONST(result), STORE_NAME('x')))

        check_unary_op('+', 2, 2)
        check_unary_op('-', 3, -3)
        check_unary_op('~', 5, -6)

    def test_bin_op(self):
        def check_bin_op(left, op, right, result):
            self.check('x = %r %s %r' % (left, op, right),
                       (LOAD_CONST(result), STORE_NAME('x')))

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

    def test_combined_unary_bin_ops(self):
        self.check('x = 1 + 3 + 7',
                   (LOAD_CONST(11), STORE_NAME('x')))

        self.check('x = ~(~(5))',
                   (LOAD_CONST(5), STORE_NAME('x')))

        self.check("events = [(0, 'call'), (1, 'line'), (-(3), 'call')]",
                   (LOAD_CONST((0, 'call')),
                    LOAD_CONST((1, 'line')),
                    LOAD_CONST((-3, 'call')),
                    Instr(1, 'BUILD_LIST', 3),
                    STORE_NAME('events')))

        zeros = (0,) * 8
        result = (1,) + zeros
        self.check('x = (1,) + (0,) * 8',
                   (LOAD_CONST(result), STORE_NAME('x')))

    def test_max_size(self):
        max_size = 3
        with mock.patch.object(peephole_opt, 'MAX_SIZE', max_size):
            # optimized binary operation: size <= maximum size
            size = max_size
            result = (9,) * size
            self.check('x = (9,) * %s' % size,
                       (LOAD_CONST(result), STORE_NAME('x')))

            # don't optimize  binary operation: size > maximum size
            size = (max_size + 1)
            self.check('x = (9,) * %s' % size,
                       (LOAD_CONST((9,)),
                        LOAD_CONST(size),
                        Instr(1, 'BINARY_MULTIPLY'),
                        STORE_NAME('x')))

    def test_bin_op_dont_optimize(self):
        self.check_dont_optimize('1 / 0')
        self.check_dont_optimize('1 // 0')
        self.check_dont_optimize('1 % 0')
        self.check_dont_optimize('1 % 1j')

    def test_build_tuple(self):
        self.check('x = (1, 2, 3)',
                   (LOAD_CONST((1, 2, 3)), STORE_NAME('x')))

    def test_build_tuple_unpack_seq(self):
        self.check('x, = (a,)',
                   (LOAD_NAME('a'), STORE_NAME('x')))

        self.check('x, y = (a, b)',
                   (LOAD_NAME('a'), LOAD_NAME('b'),
                    Instr(1, 'ROT_TWO'),
                    STORE_NAME('x'), STORE_NAME('y')))

        self.check('x, y, z = (a, b, c)',
                   (LOAD_NAME('a'), LOAD_NAME('b'), LOAD_NAME('c'),
                    Instr(1, 'ROT_THREE'),
                    Instr(1, 'ROT_TWO'),
                    STORE_NAME('x'), STORE_NAME('y'), STORE_NAME('z')))

    def test_build_list(self):
        self.check('test = x in [1, 2, 3]',
                   (LOAD_NAME('x'),
                    LOAD_CONST((1, 2, 3)),
                    Instr(1, 'COMPARE_OP', 6),
                    STORE_NAME('test')))

    def test_build_list_unpack_seq(self):
        self.check('x, = [a]',
                   (LOAD_NAME('a'), STORE_NAME('x')))

        self.check('x, y = [a, b]',
                   (LOAD_NAME('a'), LOAD_NAME('b'),
                    Instr(1, 'ROT_TWO'),
                    STORE_NAME('x'), STORE_NAME('y')))

        self.check('x, y, z = [a, b, c]',
                   (LOAD_NAME('a'), LOAD_NAME('b'), LOAD_NAME('c'),
                    Instr(1, 'ROT_THREE'),
                    Instr(1, 'ROT_TWO'),
                    STORE_NAME('x'), STORE_NAME('y'), STORE_NAME('z')))

    def test_build_set(self):
        data = frozenset((1, 2, 3))
        self.check('test = x in {1, 2, 3}',
                   (LOAD_NAME('x'),
                    LOAD_CONST(data),
                    Instr(1, 'COMPARE_OP', 6),
                    STORE_NAME('test')))

    def test_compare_op_unary_not(self):
        for source, op in (
            ('x = not(a in b)', 7),
            ('x = not(a not in b)', 6),
            ('x = not(a is b)', 9),
            ('x = not(a is not b)', 8),
        ):
            self.check(source,
                       (LOAD_NAME('a'),
                        LOAD_NAME('b'),
                        Instr(1, 'COMPARE_OP', op),
                        STORE_NAME('x')))

        # don't optimize
        self.check_dont_optimize('x = not (a and b is True)')

    def test_dont_optimize(self):
        self.check('x = 3 < 5',
                   (LOAD_CONST(3),
                    LOAD_CONST(5),
                    Instr(1, 'COMPARE_OP', 0),
                    STORE_NAME('x')))

        self.check('x = (10, 20, 30)[1:]',
                   (LOAD_CONST((10, 20, 30)),
                    LOAD_CONST(1),
                    LOAD_CONST(None),
                    Instr(1, 'BUILD_SLICE', 2),
                    Instr(1, 'BINARY_SUBSCR'),
                    STORE_NAME('x')))

    def test_optimize_code_obj(self):
        # x = 3 + 5
        block = [
            Instr(1, 'LOAD_CONST', 3),
            Instr(1, 'LOAD_CONST', 5),
            Instr(1, 'BINARY_ADD'),
            Instr(1, 'STORE_NAME', 'x'),
            Instr(1, 'LOAD_CONST', None),
            Instr(1, 'RETURN_VALUE'),
        ]
        code_noopt = BytecodeBlocks()
        code_noopt[0][:] = block
        noopt = code_noopt.to_code()

        optimizer = peephole_opt._CodePeepholeOptimizer()
        optim = optimizer.optimize(noopt)

        code = BytecodeBlocks.from_code(optim)

        expected = [
            Instr(1, 'LOAD_CONST', 8),
            Instr(1, 'STORE_NAME', 'x'),
            Instr(1, 'LOAD_CONST', None),
            Instr(1, 'RETURN_VALUE'),
        ]
        self.assertBlocksEqual(code, expected)

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
            code_noopt = BytecodeBlocks()
            code_noopt.consts = [None]
            code_noopt[0][:] = block
            noopt = code_noopt.to_code()

            # don't optimize if the last instruction of the code
            # is not RETURN_VALUE
            optimizer = peephole_opt._CodePeepholeOptimizer()
            optim = optimizer.optimize(noopt)

            self.assertIs(optim, noopt)

    def test_mimicks_c_impl_extended_arg(self):
        with mock.patch.object(peephole_opt, 'MIMICK_C_IMPL', True):
            # create code with EXTENDED_ARG opcode
            block = [
                ConcreteInstr(1, 'LOAD_CONST', 3 << 16),
                ConcreteInstr(1, 'POP_TOP'),
                ConcreteInstr(1, 'LOAD_CONST', 0),
                ConcreteInstr(1, 'LOAD_CONST', 1),
                ConcreteInstr(1, 'BINARY_ADD'),
                ConcreteInstr(1, 'STORE_NAME', 0),
                ConcreteInstr(1, 'LOAD_CONST', 2),
                ConcreteInstr(1, 'RETURN_VALUE'),
            ]
            code_noopt = ConcreteBytecode()
            code_noopt.consts = [1, 2, None]
            code_noopt.names = ['x']
            code_noopt[:] = block
            noopt = code_noopt.to_code()

            # don't optimize if the code contains EXTENDED_ARG opcode
            optimizer = peephole_opt._CodePeepholeOptimizer()
            optim = optimizer.optimize(noopt)

            self.assertIs(optim, noopt)

    def test_return_value(self):
        # return+return: remove second return
        source = """
            def func():
                return 4
                return 5
        """
        expected = [
                Instr(2, 'LOAD_CONST', 4),
                Instr(2, 'RETURN_VALUE'),
        ]
        self.check(source, expected,
                   function=True)

        # return+return + return+return: remove second and fourth return
        source = """
            def func():
                return 4
                return 5
                return 6
                return 7
        """
        expected = [
                Instr(2, 'LOAD_CONST', 4),
                Instr(2, 'RETURN_VALUE'),
                Instr(4, 'LOAD_CONST', 6),
                Instr(4, 'RETURN_VALUE'),
        ]
        self.check(source, expected, function=True)

        # return + JUMP_ABSOLUTE: remove JUMP_ABSOLUTE
        source = """
            def func():
                while 1:
                    return 7
        """
        code = self.optimize_bytecode(source, function=True)
        self.assertBlocksEqual(code,
                   [Instr(2, 'SETUP_LOOP', code[2].label)],
                   [Instr(3, 'LOAD_CONST', 7),
                    Instr(3, 'RETURN_VALUE'),
                    Instr(3, 'POP_BLOCK')],
                   [Instr(3, 'LOAD_CONST', None),
                    Instr(3, 'RETURN_VALUE')])


    def test_not_jump_if_false(self):
        # Replace UNARY_NOT+POP_JUMP_IF_FALSE with POP_JUMP_IF_TRUE
        source = '''
            if not x:
                y = 9
            y = 4
        '''
        code = self.optimize_bytecode(source)
        self.assertBlocksEqual(code,
                   [Instr(1, 'LOAD_NAME', 'x'),
                    Instr(1, 'POP_JUMP_IF_TRUE', code[1].label),
                    Instr(2, 'LOAD_CONST', 9),
                    Instr(2, 'STORE_NAME', 'y')],
                   [Instr(3, 'LOAD_CONST', 4),
                    Instr(3, 'STORE_NAME', 'y')])

    def test_unconditional_jump_to_return(self):
        source = """
            def func():
                if test:
                    if test2:
                        x = 10
                    else:
                        x = 20
                else:
                    x = 30
        """
        code = self.optimize_bytecode(source, function=True)
        self.assertBlocksEqual(code,
                             [Instr(2, 'LOAD_GLOBAL', 'test'),
                              Instr(2, 'POP_JUMP_IF_FALSE', code[3].label),

                              Instr(3, 'LOAD_GLOBAL', 'test2'),
                              Instr(3, 'POP_JUMP_IF_FALSE', code[1].label),

                              Instr(4, 'LOAD_CONST', 10),
                              Instr(4, 'STORE_FAST', 'x'),
                              Instr(4, 'JUMP_ABSOLUTE', code[4].label)],

                             [Instr(6, 'LOAD_CONST', 20),
                              Instr(6, 'STORE_FAST', 'x')],

                             # FIXME: optimize POP_JUMP_IF_FALSE+JUMP_FORWARD?
                             [Instr(6, 'JUMP_FORWARD', code[4].label)],

                             [Instr(8, 'LOAD_CONST', 30),
                              Instr(8, 'STORE_FAST', 'x')],

                             [Instr(8, 'LOAD_CONST', None),
                              Instr(8, 'RETURN_VALUE')])

    def test_unconditional_jumps(self):
        source = """
            def func():
                if x:
                    if y:
                        func()
        """
        code = self.optimize_bytecode(source, function=True)
        self.assertBlocksEqual(code,
                             [Instr(2, 'LOAD_GLOBAL', 'x'),
                              Instr(2, 'POP_JUMP_IF_FALSE', code[1].label),

                              Instr(3, 'LOAD_GLOBAL', 'y'),
                              Instr(3, 'POP_JUMP_IF_FALSE', code[1].label),

                              Instr(4, 'LOAD_GLOBAL', 'func'),
                              Instr(4, 'CALL_FUNCTION', 0),
                              Instr(4, 'POP_TOP')],

                             [Instr(4, 'LOAD_CONST', None),
                              Instr(4, 'RETURN_VALUE')])


    def test_jump_to_return(self):
        source = """
            def func(condition):
                return 'yes' if condition else 'no'
        """
        code = self.optimize_bytecode(source, function=True)
        self.assertBlocksEqual(code,
                             [Instr(2, 'LOAD_FAST', 'condition'),
                              Instr(2, 'POP_JUMP_IF_FALSE', code[1].label),

                              Instr(2, 'LOAD_CONST', 'yes'),
                              Instr(2, 'RETURN_VALUE')],

                             [Instr(2, 'LOAD_CONST', 'no')],
                             [Instr(2, 'RETURN_VALUE')])

    # FIXME: test fails!
    #def test_jump_if_true_to_jump_if_false(self):
    #    source = '''
    #        if x or y:
    #            z = 1
    #    '''
    #    code = self.optimize_bytecode(source)
    #    from test_utils import dump_code; dump_code(code)

    # FIXME: test fails!
    #def test_jump_if_false_to_jump_if_false(self):
    #    source = """
    #        while n > 0 and start > 3:
    #            func()
    #    """
    #    code = self.optimize_bytecode(source)
    #    from test_utils import dump_code; dump_code(code)


if __name__ == "__main__":
    unittest.main()

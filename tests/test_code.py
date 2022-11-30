import unittest

from bytecode import Bytecode, ConcreteBytecode, ControlFlowGraph

from . import TestCase, get_code


class CodeTests(TestCase):
    """Check that bytecode.from_code(code).to_code() returns code."""

    def check(self, source, function=False):
        ref_code = get_code(source, function=function)

        code = ConcreteBytecode.from_code(ref_code).to_code()
        self.assertCodeObjectEqual(ref_code, code)

        code = Bytecode.from_code(ref_code).to_code()
        self.assertCodeObjectEqual(ref_code, code)

        bytecode = Bytecode.from_code(ref_code)
        blocks = ControlFlowGraph.from_bytecode(bytecode)
        code = blocks.to_bytecode().to_code()
        self.assertCodeObjectEqual(ref_code, code)

    def test_loop(self):
        self.check(
            """
            for x in range(1, 10):
                x += 1
                if x == 3:
                    continue
                x -= 1
                if x > 7:
                    break
                x = 0
            print(x)
        """
        )

    def test_varargs(self):
        self.check(
            """
            def func(a, b, *varargs):
                pass
        """,
            function=True,
        )

    def test_kwargs(self):
        self.check(
            """
            def func(a, b, **kwargs):
                pass
        """,
            function=True,
        )

    def test_kwonlyargs(self):
        self.check(
            """
            def func(*, arg, arg2):
                pass
        """,
            function=True,
        )

    # Added because Python 3.10 added some special behavior with respect to
    # generators in term of stack size
    def test_generator_func(self):
        self.check(
            """
            def func(arg, arg2):
                yield
        """,
            function=True,
        )

    def test_async_func(self):
        self.check(
            """
            async def func(arg, arg2):
                pass
        """,
            function=True,
        )


if __name__ == "__main__":
    unittest.main()  # pragma: no cover

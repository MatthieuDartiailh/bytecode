import textwrap
import types
import unittest

import bytecode as _bytecode


def LOAD_CONST(arg):
    return _bytecode.Instr(1, 'LOAD_CONST', arg)

def STORE_NAME(arg):
    return _bytecode.Instr(1, 'STORE_NAME', arg)

def NOP():
    return _bytecode.Instr(1, 'NOP')

def RETURN_VALUE():
    return _bytecode.Instr(1, 'RETURN_VALUE')


def get_code(source, *, filename="<string>", function=False):
    source = textwrap.dedent(source).strip()
    code = compile(source, filename, "exec")
    if function:
        sub_code = [const for const in code.co_consts
                    if isinstance(const, types.CodeType)]
        if len(sub_code) != 1:
            raise ValueError("unable to find function code")
        code = sub_code[0]
    return code

def disassemble(source, *, filename="<string>", function=False,
                remove_last_return_none=False):
    code = get_code(source, filename=filename, function=function)

    bytecode = _bytecode.BytecodeBlocks.from_code(code)
    if remove_last_return_none:
        # drop LOAD_CONST+RETURN_VALUE to only keep 2 instructions,
        # to make unit tests shorter
        block = bytecode[-1]
        test = (block[-2].name == "LOAD_CONST"
                and block[-2].arg is None
                and block[-1].name == "RETURN_VALUE")
        if not test:
            raise ValueError("unable to find implicit RETURN_VALUE <None>: %s"
                             % block[-2:])
        del block[-2:]
    return bytecode


class TestCase(unittest.TestCase):
    def assertBlocksEqual(self, code, *expected_blocks):
        blocks = [list(block) for block in code]
        self.assertEqual(len(blocks), len(expected_blocks))
        for block, expected_block in zip(blocks, expected_blocks):
            self.assertListEqual(block, list(expected_block))

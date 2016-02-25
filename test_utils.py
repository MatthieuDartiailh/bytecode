import bytecode
import unittest


def dump_code(code):
    print()
    for block_index, block in enumerate(code):
        instr_list = []
        for instr in block:
            arg = instr.arg
            if arg is not bytecode.UNSET:
                if isinstance(arg, bytecode.Label):
                    arg = 'code[%s].label' % code._label_to_index[arg]
                text = 'Instr(%s, %r, %s)' % (instr.lineno, instr.name, arg)
            else:
                text = 'Instr(%s, %r)' % (instr.lineno, instr.name)
            instr_list.append(text)
        text = '[%s]'  % ',\n '.join(instr_list)
        if block_index != len(code) - 1:
            text += ','
        print(text)
        print()


class TestCase(unittest.TestCase):
    def assertBlocksEqual(self, code, *expected_blocks):
        blocks = [list(block) for block in code]
        self.assertEqual(len(blocks), len(expected_blocks))
        for block, expected_block in zip(blocks, expected_blocks):
            self.assertListEqual(block, list(expected_block))

    def assertBytecodeEqual(self, code, *expected_blocks):
        expected = bytecode.BytecodeBlocks()
        expected.argnames = code.argnames

        del expected[0]
        for block in expected_blocks:
            expected.add_block(block)

        bytecode._dump_code(code)
        print("*")
        bytecode._dump_code(expected)
        print(type(code))
        print(type(expected))
        self.assertEqual(code, expected)


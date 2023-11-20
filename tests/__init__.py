import dis
import sys
import textwrap
import types
import unittest

from bytecode import (
    UNSET,
    BasicBlock,
    Bytecode,
    ConcreteBytecode,
    ConcreteInstr,
    ControlFlowGraph,
    Instr,
    Label,
)


def _format_instr_list(block, labels, lineno):
    instr_list = []
    for instr in block:
        if not isinstance(instr, Label):
            if isinstance(instr, ConcreteInstr):
                cls_name = "ConcreteInstr"
            else:
                cls_name = "Instr"
            arg = instr.arg
            if arg is not UNSET:
                if isinstance(arg, Label):
                    arg = labels[arg]
                elif isinstance(arg, BasicBlock):
                    arg = labels[id(arg)]
                else:
                    arg = repr(arg)
                if lineno:
                    text = "%s(%r, %s, lineno=%s)" % (
                        cls_name,
                        instr.name,
                        arg,
                        instr.lineno,
                    )
                else:
                    text = "%s(%r, %s)" % (cls_name, instr.name, arg)
            else:
                if lineno:
                    text = "%s(%r, lineno=%s)" % (cls_name, instr.name, instr.lineno)
                else:
                    text = "%s(%r)" % (cls_name, instr.name)
        else:
            text = labels[instr]
        instr_list.append(text)
    return "[%s]" % ",\n ".join(instr_list)


def dump_bytecode(code, lineno=False):
    """
    Use this function to write unit tests: copy/paste its output to
    write a self.assertBlocksEqual() check.
    """
    print()

    if isinstance(code, (Bytecode, ConcreteBytecode)):
        is_concrete = isinstance(code, ConcreteBytecode)
        if is_concrete:
            block = list(code)
        else:
            block = code

        indent = " " * 8
        labels = {}
        for index, instr in enumerate(block):
            if isinstance(instr, Label):
                name = "label_instr%s" % index
                labels[instr] = name

        if is_concrete:
            name = "ConcreteBytecode"
            print(indent + "code = %s()" % name)
            if code.argcount:
                print(indent + "code.argcount = %s" % code.argcount)
            if code.posonlyargcount:
                print(indent + "code.posonlyargcount = %s" % code.posonlyargcount)
            if code.kwonlyargcount:
                print(indent + "code.kwargonlycount = %s" % code.kwonlyargcount)
            print(indent + "code.flags = %#x" % code.flags)
            if code.consts:
                print(indent + "code.consts = %r" % code.consts)
            if code.names:
                print(indent + "code.names = %r" % code.names)
            if code.varnames:
                print(indent + "code.varnames = %r" % code.varnames)

        for name in sorted(labels.values()):
            print(indent + "%s = Label()" % name)

        if is_concrete:
            text = indent + "code.extend("
            indent = " " * len(text)
        else:
            text = indent + "code = Bytecode("
            indent = " " * len(text)

        lines = _format_instr_list(code, labels, lineno).splitlines()
        last_line = len(lines) - 1
        for index, line in enumerate(lines):
            if index == 0:
                print(text + lines[0])
            elif index == last_line:
                print(indent + line + ")")
            else:
                print(indent + line)

        print()
    else:
        assert isinstance(code, ControlFlowGraph)
        labels = {}
        for block_index, block in enumerate(code):
            labels[id(block)] = "code[%s]" % block_index

        for block_index, block in enumerate(code):
            text = _format_instr_list(block, labels, lineno)
            if block_index != len(code) - 1:
                text += ","
            print(text)
            print()


def get_code(source, *, filename="<string>", function=False):
    source = textwrap.dedent(source).strip()
    code = compile(source, filename, "exec")
    if function:
        sub_code = [
            const for const in code.co_consts if isinstance(const, types.CodeType)
        ]
        if len(sub_code) != 1:
            raise ValueError("unable to find function code")
        code = sub_code[0]
    return code


def disassemble(source, *, filename="<string>", function=False):
    code = get_code(source, filename=filename, function=function)
    return Bytecode.from_code(code)


class TestCase(unittest.TestCase):
    def assertInstructionListEqual(self, l1, l2):
        # DO not check location information
        self.assertEqual(len(l1), len(l2))
        for i1, i2 in zip(l1, l2):
            if isinstance(i1, Instr):
                self.assertEqual(i1.name, i2.name)
                if not isinstance(i1.arg, Label):
                    self.assertEqual(i1.arg, i2.arg)
                else:
                    self.assertIs(l1.index(i1.arg), l2.index(i2.arg))
                self.assertEqual(i1.lineno, i2.lineno)
            else:
                assert type(i1) is type(i2)

    def assertCodeObjectEqual(self, code1: types.CodeType, code2: types.CodeType):
        self.assertEqual(code1.co_stacksize, code2.co_stacksize)
        self.assertEqual(code1.co_firstlineno, code2.co_firstlineno)
        self.assertSequenceEqual(code1.co_cellvars, code2.co_cellvars)
        self.assertSequenceEqual(code1.co_freevars, code2.co_freevars)
        self.assertSetEqual(set(code1.co_varnames), set(code2.co_varnames))
        if sys.version_info >= (3, 11):
            self.assertSequenceEqual(code1.co_exceptiontable, code2.co_exceptiontable)
            # We do not compare linetables because CPython does not always optimize
            # the packing of the table
            self.assertSequenceEqual(
                list(code1.co_positions()), list(code2.co_positions())
            )
            self.assertEqual(code1.co_qualname, code2.co_qualname)
        elif sys.version_info >= (3, 10):
            self.assertSequenceEqual(list(code1.co_lines()), list(code2.co_lines()))
        else:
            # This is safer than directly comparing co_lnotab that sometimes contains
            # cruft
            self.assertSequenceEqual(
                list(dis.findlinestarts(code1)), list(dis.findlinestarts(code2))
            )

        # If names have been re-ordered compared the output of dis.instructions
        if sys.version_info >= (3, 12) and (
            code1.co_names != code2.co_names or code1.co_varnames != code2.co_varnames
        ):
            instrs1 = list(dis.get_instructions(code1))
            instrs2 = list(dis.get_instructions(code2))
            self.assertEqual(len(instrs1), len(instrs2))
            for i1, i2 in zip(instrs1, instrs2):
                self.assertEqual(i1.opcode, i2.opcode)
                self.assertEqual(i1.argval, i2.argval)
        elif sys.version_info >= (3, 9):
            self.assertSequenceEqual(code1.co_code, code2.co_code)
        # On Python 3.8 it happens that fast storage index vary in a roundtrip
        else:
            import opcode

            fast_storage = opcode.opmap["LOAD_FAST"], opcode.opmap["STORE_FAST"]
            load_const = opcode.opmap["LOAD_CONST"]
            load_by_name = (
                opcode.opmap["LOAD_GLOBAL"],
                opcode.opmap["LOAD_NAME"],
                opcode.opmap["LOAD_METHOD"],
            )
            if code1.co_code != code2.co_code:
                for b1, a1, b2, a2 in zip(
                    code1.co_code[::2],
                    code1.co_code[1::2],
                    code2.co_code[::2],
                    code2.co_code[1::2],
                ):
                    if b1 != b2:
                        self.assertSequenceEqual(code1.co_code, code2.co_code)
                    # Do not check the argument of fast storage manipulation opcode
                    elif b1 in fast_storage:
                        pass
                    elif b1 == load_const:
                        self.assertEqual(code1.co_consts[a1], code2.co_consts[a2])
                    elif b1 in load_by_name:
                        self.assertEqual(code1.co_names[a1], code2.co_names[a2])
                    elif a1 != a2:
                        self.assertSequenceEqual(code1.co_code, code2.co_code)

        self.assertEqual(code1.co_flags, code2.co_flags)

    def assertBlocksEqual(self, code, *expected_blocks):
        self.assertEqual(len(code), len(expected_blocks))

        for block1, block2 in zip(code, expected_blocks):
            self.assertInstructionListEqual(list(block1), block2)

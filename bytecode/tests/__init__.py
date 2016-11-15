import sys
import textwrap
import types
import unittest

from bytecode import (UNSET, Label, Instr, ConcreteInstr, BasicBlock,   # noqa
                      Bytecode, ControlFlowGraph, ConcreteBytecode, IS_PY2)

WORDCODE = (sys.version_info >= (3, 6))


def _format_instr_list(block, labels, lineno):
    instr_list = []
    for instr in block:
        if not isinstance(instr, Label):
            if isinstance(instr, ConcreteInstr):
                cls_name = 'ConcreteInstr'
            else:
                cls_name = 'Instr'
            arg = instr.arg
            if arg is not UNSET:
                if isinstance(arg, Label):
                    arg = labels[arg]
                elif isinstance(arg, BasicBlock):
                    arg = labels[id(arg)]
                else:
                    arg = repr(arg)
                if lineno:
                    text = '%s(%r, %s, lineno=%s)' % (
                        cls_name, instr.name, arg, instr.lineno)
                else:
                    text = '%s(%r, %s)' % (cls_name, instr.name, arg)
            else:
                if lineno:
                    text = '%s(%r, lineno=%s)' % (
                        cls_name, instr.name, instr.lineno)
                else:
                    text = '%s(%r)' % (cls_name, instr.name)
        else:
            text = labels[instr]
        instr_list.append(text)
    return '[%s]' % ',\n '.join(instr_list)


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

        indent = ' ' * 8
        labels = {}
        for index, instr in enumerate(block):
            if isinstance(instr, Label):
                name = 'label_instr%s' % index
                labels[instr] = name

        if is_concrete:
            name = 'ConcreteBytecode'
            print(indent + 'code = %s()' % name)
            if code.argcount:
                print(indent + 'code.argcount = %s' % code.argcount)
            if code.kwonlyargcount:
                print(indent + 'code.argcount = %s' % code.kwonlyargcount)
            print(indent + 'code.flags = %#x' % code.flags)
            if code.consts:
                print(indent + 'code.consts = %r' % code.consts)
            if code.names:
                print(indent + 'code.names = %r' % code.names)
            if code.varnames:
                print(indent + 'code.varnames = %r' % code.varnames)

        for name in sorted(labels.values()):
            print(indent + '%s = Label()' % name)

        if is_concrete:
            text = indent + 'code.extend('
            indent = ' ' * len(text)
        else:
            text = indent + 'code = Bytecode('
            indent = ' ' * len(text)

        lines = _format_instr_list(code, labels, lineno).splitlines()
        last_line = len(lines) - 1
        for index, line in enumerate(lines):
            if index == 0:
                print(text + lines[0])
            elif index == last_line:
                print(indent + line + ')')
            else:
                print(indent + line)

        print()
    else:
        assert isinstance(code, ControlFlowGraph)
        labels = {}
        for block_index, block in enumerate(code):
            labels[id(block)] = 'code[%s]' % block_index

        for block_index, block in enumerate(code):
            text = _format_instr_list(block, labels, lineno)
            if block_index != len(code) - 1:
                text += ','
            print(text)
            print()


def get_code(source, filename="<string>", function=False):
    source = textwrap.dedent(source).strip()
    code = compile(source, filename, "exec")
    if function:
        sub_code = [const for const in code.co_consts
                    if isinstance(const, types.CodeType)]
        if len(sub_code) != 1:
            raise ValueError("unable to find function code")
        code = sub_code[0]
    return code


def disassemble(source, filename="<string>", function=False):
    code = get_code(source, filename=filename, function=function)
    return Bytecode.from_code(code)


if not IS_PY2:
    from contextlib import redirect_stdout
else:
    # Copied from Python 3.4 contextlib.py
    class _RedirectStream:

        _stream = None

        def __init__(self, new_target):
            self._new_target = new_target
            # We use a list of old targets to make this CM re-entrant
            self._old_targets = []

        def __enter__(self):
            self._old_targets.append(getattr(sys, self._stream))
            setattr(sys, self._stream, self._new_target)
            return self._new_target

        def __exit__(self, exctype, excinst, exctb):
            setattr(sys, self._stream, self._old_targets.pop())

    class redirect_stdout(_RedirectStream):
        """Context manager for temporarily redirecting stdout to another file.

            # How to send help() to stderr
            with redirect_stdout(sys.stderr):
                help(dir)

            # How to write help() to a file
            with open('help.txt', 'w') as f:
                with redirect_stdout(f):
                    help(pow)
        """
        _stream = "stdout"


class TestCase(unittest.TestCase):

    def assertBlocksEqual(self, code, *expected_blocks):
        self.assertEqual(len(code), len(expected_blocks))

        for block1, block2 in zip(code, expected_blocks):
            block_index = code.get_block_index(block1)
            self.assertListEqual(list(block1), block2,
                                 "Block #%s is different" % block_index)

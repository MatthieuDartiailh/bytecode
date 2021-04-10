__version__ = "0.12.0"

__all__ = [
    "Label",
    "Instr",
    "SetLineno",
    "Bytecode",
    "ConcreteInstr",
    "ConcreteBytecode",
    "ControlFlowGraph",
    "CompilerFlags",
    "Compare",
]

from .bytecode import BaseBytecode, Bytecode, _BaseBytecodeList, _InstrList  # noqa
from .cfg import BasicBlock, ControlFlowGraph  # noqa
from .concrete import ConcreteBytecode  # import needed to use it in bytecode.py; noqa
from .concrete import ConcreteInstr, _ConvertBytecodeToConcrete
from .flags import CompilerFlags
from .instr import FreeVar  # noqa
from .instr import UNSET, CellVar, Compare, Instr, Label, SetLineno


def dump_bytecode(bytecode, lineno=False):
    def format_line(index, line):
        if lineno:
            if cur_lineno != prev_lineno:
                return "L.% 3s % 3s: %s" % (cur_lineno, index, line), cur_lineno
            else:
                return "      % 3s: %s" % (index, line), prev_lineno
        else:
            return line, prev_lineno

    def format_instr(instr, labels=None):
        text = instr.name
        arg = instr._arg
        if arg is not UNSET:
            if isinstance(arg, Label):
                try:
                    arg = "<%s>" % labels[arg]
                except KeyError:
                    arg = "<error: unknown label>"
            elif isinstance(arg, BasicBlock):
                try:
                    arg = "<%s>" % labels[id(arg)]
                except KeyError:
                    arg = "<error: unknown block>"
            else:
                arg = repr(arg)
            text = "%s %s" % (text, arg)
        return text

    indent = " " * 4

    cur_lineno = bytecode.first_lineno
    prev_lineno = None

    if isinstance(bytecode, ConcreteBytecode):
        offset = 0
        for instr in bytecode:
            fields = []
            if instr.lineno is not None:
                cur_lineno = instr.lineno
            if lineno:
                fields.append(format_instr(instr))
                line = "".join(fields)
                line, prev_lineno = format_line(offset, line)
            else:
                fields.append("% 3s    %s" % (offset, format_instr(instr)))
                line = "".join(fields)
            print(line)

            offset += instr.size
    elif isinstance(bytecode, Bytecode):
        labels = {}
        for index, instr in enumerate(bytecode):
            if isinstance(instr, Label):
                labels[instr] = "label_instr%s" % index

        for index, instr in enumerate(bytecode):
            if isinstance(instr, Label):
                label = labels[instr]
                line = "%s:" % label
                if index != 0:
                    print("")
            else:
                if instr.lineno is not None:
                    cur_lineno = instr.lineno
                line = format_instr(instr, labels)
                _, prev_lineno = format_line(index, line)
                line = indent + _
            print(line)
        print("")
    elif isinstance(bytecode, ControlFlowGraph):
        labels = {}
        for block_index, block in enumerate(bytecode, 1):
            labels[id(block)] = "block%s" % block_index

        for block_index, block in enumerate(bytecode, 1):
            print("%s:" % labels[id(block)])
            prev_lineno = None
            for index, instr in enumerate(block):
                if instr.lineno is not None:
                    cur_lineno = instr.lineno
                line = format_instr(instr, labels)
                _, prev_lineno = format_line(index, line)
                line = indent + _
                print(line)
            if block.next_block is not None:
                print(indent + "-> %s" % labels[id(block.next_block)])
            print("")
    else:
        raise TypeError("unknown bytecode class")

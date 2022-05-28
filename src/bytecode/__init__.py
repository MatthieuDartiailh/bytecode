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
    "__version__",
]

from typing import Union

# import needed to use it in bytecode.py
from bytecode.bytecode import (  # noqa
    BaseBytecode,
    Bytecode,
    _BaseBytecodeList,
    _InstrList,
)

# import needed to use it in bytecode.py
from bytecode.cfg import BasicBlock, ControlFlowGraph  # noqa

# import needed to use it in bytecode.py
from bytecode.concrete import _ConvertBytecodeToConcrete  # noqa
from bytecode.concrete import (
    ConcreteBytecode,
    ConcreteInstr,
)
from bytecode.flags import CompilerFlags

# import needed to use it in bytecode.py
from bytecode.instr import FreeVar, CellVar  # noqa
from bytecode.instr import UNSET, Compare, Instr, Label, SetLineno
from bytecode.version import __version__


def dump_bytecode(
    bytecode: Union[Bytecode, ConcreteBytecode, ControlFlowGraph],
    *,
    lineno: bool = False
):
    def format_line(index, line):
        nonlocal cur_lineno, prev_lineno
        if lineno:
            if cur_lineno != prev_lineno:
                line = "L.% 3s % 3s: %s" % (cur_lineno, index, line)
                prev_lineno = cur_lineno
            else:
                line = "      % 3s: %s" % (index, line)
        else:
            line = line
        return line

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
        for c_instr in bytecode:
            fields = []
            if c_instr.lineno is not None:
                cur_lineno = c_instr.lineno
            if lineno:
                fields.append(format_instr(c_instr))
                line = "".join(fields)
                line = format_line(offset, line)
            else:
                fields.append("% 3s    %s" % (offset, format_instr(c_instr)))
                line = "".join(fields)
            print(line)

            if isinstance(c_instr, ConcreteInstr):
                offset += c_instr.size

    elif isinstance(bytecode, Bytecode):
        labels: dict[Label, str] = {}
        for index, instr in enumerate(bytecode):
            if isinstance(instr, Label):
                labels[instr] = "label_instr%s" % index

        for index, instr in enumerate(bytecode):
            if isinstance(instr, Label):
                label = labels[instr]
                line = "%s:" % label
                if index != 0:
                    print()
            else:
                if instr.lineno is not None:
                    cur_lineno = instr.lineno
                line = format_instr(instr, labels)
                line = indent + format_line(index, line)
            print(line)
        print()

    elif isinstance(bytecode, ControlFlowGraph):
        cfg_labels = {}
        for block_index, block in enumerate(bytecode, 1):
            cfg_labels[id(block)] = "block%s" % block_index

        for block_index, block in enumerate(bytecode, 1):
            print("%s:" % cfg_labels[id(block)])
            prev_lineno = None
            for index, instr in enumerate(block):
                if instr.lineno is not None:
                    cur_lineno = instr.lineno
                line = format_instr(instr, cfg_labels)
                line = indent + format_line(index, line)
                print(line)
            if block.next_block is not None:
                print(indent + "-> %s" % cfg_labels[id(block.next_block)])
            print()
    else:
        raise TypeError("unknown bytecode class")

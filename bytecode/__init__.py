__version__ = '0.1'

__all__ = ['Label', 'Instr', 'SetLineno', 'Bytecode',
           'ConcreteInstr', 'ConcreteBytecode',
           'BytecodeBlocks']

from bytecode.instr import UNSET, Label, SetLineno, Instr
from bytecode.bytecode import BaseBytecode, _InstrList, Bytecode
from bytecode.concrete import (ConcreteInstr, ConcreteBytecode,
                               _ConvertCodeToConcrete)
from bytecode.blocks import BytecodeBlocks


# FIXME: move code into a submodule or inside Bytecode classes?
def dump(code):
    indent = ' ' * 4
    if isinstance(code, ConcreteBytecode):
        line_width = 3

        offset = 0
        lineno = None
        for instr in code:
            fields = []
            if instr.lineno != lineno:
                fields.append(str(instr.lineno).rjust(line_width))
                lineno = instr.lineno
            else:
                fields.append(" " * line_width)

            fields.append("% 3s    %s" % (offset, instr.name))
            if instr.arg is not UNSET:
                fields.append("(%s)" % instr.arg)
            print(''.join(fields))

            offset += instr.size
    elif isinstance(code, Bytecode):
        labels = {}
        for index, instr in enumerate(code):
            if isinstance(instr, Label):
                labels[instr] = 'label_instr%s' % index

        for index, instr in enumerate(code):
            if isinstance(instr, Label):
                label = labels[instr]
                line = "%s:" % label
                if index != 0:
                    print()
            else:
                line = indent + instr.format(labels)
            print(line)
        print()
    elif isinstance(code, BytecodeBlocks):
        labels = {}
        for block_index, block in enumerate(code, 1):
            block_label = 'label_block%s' % block_index
            labels[block.label] = block_label

            for index, instr in enumerate(block):
                if isinstance(instr, Label):
                    labels[instr] = '%s_instr%s' % (block_label, index)

        for block_index, block in enumerate(code, 1):
            print('%s:' % labels[block.label])
            for instr in block:
                if isinstance(instr, Label):
                    label = labels[instr]
                    line = '%s:' % label
                else:
                    line = indent + instr.format(labels)
                print(line)
            print()
    else:
        raise TypeError("unknown bycode code")

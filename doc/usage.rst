**************
Bytecode Usage
**************

Installation
============

Install bytecode::

    python3 -m pip install bytecode

``bytecode`` only works on Python 3.


Hello World
===========

Abstract bytecode
-----------------

Example using abstract bytecode to execute ``print('Hello World!')``::

    from bytecode import Instr, Bytecode

    bytecode = Bytecode([Instr("LOAD_NAME", 'print'),
                         Instr("LOAD_CONST", 'Hello World!'),
                         Instr("CALL_FUNCTION", 1),
                         Instr("POP_TOP"),
                         Instr("LOAD_CONST", None),
                         Instr("RETURN_VALUE")])
    code = bytecode.to_code()
    exec(code)

Output::

    Hello World!


Concrete bytecode
-----------------

Example using concrete bytecode to execute ``print('Hello World!')``::

    from bytecode import ConcreteInstr, ConcreteBytecode

    bytecode = ConcreteBytecode()
    bytecode.names = ['print']
    bytecode.consts = ['Hello World!', None]
    bytecode.extend([ConcreteInstr("LOAD_NAME", 0),
                     ConcreteInstr("LOAD_CONST", 0),
                     ConcreteInstr("CALL_FUNCTION", 1),
                     ConcreteInstr("POP_TOP"),
                     ConcreteInstr("LOAD_CONST", 1),
                     ConcreteInstr("RETURN_VALUE")])
    code = bytecode.to_code()
    exec(code)

Output::

    Hello World!


Conditional jump
================

Bytecode of the Python code ``print('yes' if test else 'no')``::

    from bytecode import Label, Instr, Bytecode

    label_else = Label()
    label_print = Label()
    bytecode = Bytecode([Instr('LOAD_NAME', 'print'),
                         Instr('LOAD_NAME', 'test'),
                         Instr('POP_JUMP_IF_FALSE', label_else),
                             Instr('LOAD_CONST', 'yes'),
                             Instr('JUMP_FORWARD', label_print),
                         label_else,
                             Instr('LOAD_CONST', 'no'),
                         label_print,
                             Instr('CALL_FUNCTION', 1),
                         Instr('LOAD_CONST', None),
                         Instr('RETURN_VALUE')])
    code = bytecode.to_code()

    test = 0
    exec(code)

    test = 1
    exec(code)

Output::

    no
    yes

Instructions are only indented for readability.

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


Simple loop
===========

Bytecode of ``for x in (1, 2, 3): print(x)``::

    from bytecode import Label, Instr, Bytecode

    loop_start = Label()
    loop_done = Label()
    loop_exit = Label()
    code = Bytecode([Instr('SETUP_LOOP', loop_exit, lineno=2),
                     Instr('LOAD_CONST', (1, 2, 3), lineno=2),
                     Instr('GET_ITER', lineno=2),
                     loop_start,
                         Instr('FOR_ITER', loop_done, lineno=2),
                         Instr('STORE_NAME', 'x', lineno=2),
                         Instr('LOAD_NAME', 'print', lineno=3),
                         Instr('LOAD_NAME', 'x', lineno=3),
                         Instr('CALL_FUNCTION', 1, lineno=3),
                         Instr('POP_TOP', lineno=3),
                         Instr('JUMP_ABSOLUTE', loop_start, lineno=3),
                     loop_done,
                         Instr('POP_BLOCK', lineno=3),
                     loop_exit,
                         Instr('LOAD_CONST', None, lineno=3),
                         Instr('RETURN_VALUE', lineno=3)])

    # the conversion to Python code object resolve jump targets:
    # replace abstract labels with concrete offsets
    code = code.to_code()
    exec(code)

Output::

    1
    2
    3


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

**************
Bytecode Usage
**************

Installation
============

Install bytecode::

    pip install bytecode

``bytecode`` only works on Python 3.


Hello World
===========

Abstract bytecode
-----------------

Example using abstract bytecode to execute ``print('Hello World!')``::

    from bytecode import Instr, Bytecode

    bytecode = Bytecode()
    bytecode.extend([Instr("LOAD_NAME", 'print'),
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

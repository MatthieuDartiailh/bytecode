**************
Bytecode Usage
**************

Installation
============

Install bytecode::

    python3 -m pip install bytecode

``bytecode`` requires Python 3.4 or newer.


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


Setting the compiler flags
--------------------------

Bytecode,  ConcreteBytecode and ControlFlowGraph instances all have a flags
attribute which is an instance of the CompilerFlag enum. The value can be
manipulated like any binary flags.

Setting the OPTIMIZED flag::

    from bytecode import Bytecode, CompilerFlags

    bytecode = Bytecode()
    bytecode.flags |= CompilerFlags.OPTIMIZED

Clearing the OPTIMIZED flag::

    from bytecode import Bytecode, CompilerFlags

    bytecode = Bytecode()
    bytecode.flags ^= CompilerFlags.OPTIMIZED


The flags can be updated based on the instructions stored in the code object
using the method update_flags.


Simple loop
===========

Bytecode of ``for x in (1, 2, 3): print(x)``:

.. tabs::

    .. group-tab:: Python < 3.8

        .. code:: python

            from bytecode import Label, Instr, Bytecode

            loop_start = Label()
            loop_done = Label()
            loop_exit = Label()
            code = Bytecode(
                [
                    Instr('SETUP_LOOP', loop_exit),
                    Instr('LOAD_CONST', (1, 2, 3)),
                    Instr('GET_ITER'),
                    loop_start,
                        Instr('FOR_ITER', loop_done),
                        Instr('STORE_NAME', 'x'),
                        Instr('LOAD_NAME', 'print'),
                        Instr('LOAD_NAME', 'x'),
                        Instr('CALL_FUNCTION', 1),
                        Instr('POP_TOP'),
                        Instr('JUMP_ABSOLUTE', loop_start),
                    loop_done,
                        Instr('POP_BLOCK'),
                    loop_exit,
                        Instr('LOAD_CONST', None),
                        Instr('RETURN_VALUE')
                ]
            )

            # the conversion to Python code object resolve jump targets:
            # replace abstract labels with concrete offsets
            code = code.to_code()
            exec(code)

    .. group-tab:: Python >= 3.8

        .. code:: python

            from bytecode import Label, Instr, Bytecode

            loop_start = Label()
            loop_done = Label()
            loop_exit = Label()
            code = Bytecode(
                [
                    # Python 3.8 removed SETUP_LOOP
                    Instr("LOAD_CONST", (1, 2, 3)),
                    Instr("GET_ITER"),
                    loop_start,
                        Instr("FOR_ITER", loop_exit),
                        Instr("STORE_NAME", "x"),
                        Instr("LOAD_NAME", "print"),
                        Instr("LOAD_NAME", "x"),
                        Instr("CALL_FUNCTION", 1),
                        Instr("POP_TOP"),
                        Instr("JUMP_ABSOLUTE", loop_start),
                    # Python 3.8 removed the need to manually manage blocks in loops
                    # This is now handled internally by the interpreter
                    loop_exit,
                        Instr("LOAD_CONST", None),
                        Instr("RETURN_VALUE"),
                ]
            )

            # The conversion to Python code object resolve jump targets:
            # abstract labels are replaced with concrete offsets
            code = code.to_code()
            exec(code)

Output::

    1
    2
    3


.. _ex-cond-jump:

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

.. note::
   Instructions are only indented for readability.

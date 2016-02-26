********
bytecode
********

``bytecode`` is a Python module to modify bytecode.

* `bytecode project homepage at GitHub
  <https://github.com/haypo/bytecode>`_ (code, bugs)
* `Download latest bytecode release at the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/bytecode>`_

Install bytecode: ``pip install bytecode``.

``bytecode`` only works on Python 3.


Hello World
===========

Example running ``print('Hello World!')``::

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


API
===

bytecode module version string: ``bytecode.__version__`` (ex: ``'0.1'``).

Instruction
-----------

* ``Instr``: abstract instruction, argument is not validated
* ``ConcreteInstr``: concrete instruction, argument must be an integer

Create instructions
-------------------

* ``Instr(name, arg=UNSET, *, lineno=None)``
* ``ConcreteInstr(name, arg=UNSET, *, lineno=None)``
* ``Instr.disassemble(code, offset)``
* ``ConcreteInstr.disassemble(code, offset)``

Pseudo instructions
-------------------

* ``Label``: target of jumps for Bytecode, must not be used in ConcreteBytecode
* ``SetLineno``: set the line number of following instructions

Bytecode
--------

* ``Bytecode``: list of Instr
* ``BytecodeBlocks``: list of blocks, a block is a list of Instr and has a label
* ``ConcreteBytecode``: list of ConcreteInstr

Create bytecode
---------------

* ``Bytecode.from_code(*, extended_arg_op=False)``
* ``BytecodeBlocks.from_code()``
* ``ConcreteBytecode.from_code()``

Conversions
-----------

* ``bytecode.to_bytecode() -> Bytecode``
* ``bytecode.to_concrete_bytecode() -> ConcreteBytecode``
* ``bytecode.to_bytecode_blocks() -> BytecodeBlocks``
* ``bytecode.to_code() -> types.CodeType``


ChangeLog
=========

* 2016-02-26: Version 0.1

  - Rewrite completely the API!

* 2016-02-23: Release 0.0

  - First public release


See also
========

* `codetransformer
  <https://pypi.python.org/pypi/codetransformer>`_
* `byteplay
  <https://github.com/serprex/byteplay>`_
* `PEP 511 -- API for code transformers
  <https://www.python.org/dev/peps/pep-0511/>`_

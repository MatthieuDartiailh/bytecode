********
bytecode
********

``bytecode`` is a Python module to modify bytecode.

The API is unstable. The project is closer to a proof-of-concept (PoC).

A code object is made of blocks and a block is a list of instructions. An
instruction has 3 main attributes: lineno, name, arg. Jumps use labels to
blocks, each block object has an unique label.

It's possible to get a flat code with only one block and without labels:
use Code.disassemble(code, use_labels=False).

bytecode 0.0 has been written to reimplement the CPython 3.6 peephole optimizer
in pure Python. This version only supports Python 3.6.

Homepage: https://github.com/haypo/bytecode


API
===

Instruction:

* Instr: abstract instruction, argument is not validated
* ConcreteInstr: concrete instruction, argument must be an integer

Create instructions:

* ``Instr(name, arg=UNSET, *, lineno=None)``
* ``ConcreteInstr(name, arg=UNSET, *, lineno=None)``
* ``Instr.disassemble(code, offset)``
* ``ConcreteInstr.disassemble(code, offset)``

Bytecode:

* ``Bytecode``: list of Instr
* ``BytecodeBlocks``: list of blocks, a block is a list of Instr and has a label
* ``ConcreteBytecode``: list of ConcreteInstr

Create bytecode:

* ``Bytecode.from_code(*, extended_arg_op=False)``
* ``BytecodeBlocks.from_code()``
* ``ConcreteBytecode.from_code()``

Conversions:

* ``bytecode.to_bytecode() -> Bytecode``
* ``bytecode.to_concrete_bytecode() -> ConcreteBytecode``
* ``bytecode.to_bytecode_blocks() -> BytecodeBlocks``
* ``bytecode.to_code() -> types.CodeType``


ChangeLog
=========

* Version 0.1

  - Rewrite completely the API...

* 2016-02-23: Release 0.0

  - First public release


Comparison with other modules
=============================

byteplay
--------

* SetLineno pseudo instruction to store line numbers.
* Label pseudo instruction for jump targets.
* Don't support blocks, but use labels for jumps.
* An instruction is a tuple of 2 items: (name, arg)
* There are functions to get properties of instructions.
* LOAD_FAST uses the local variable name rather than the variable index:
  (byteplay.LOAD_FAST, 'x').
* LOAD_FAST uses directly the constant value rather than the variable index:
  (byteplay.LOAD_CONST, 3.14).
* Docstring has its own attribute.

Note: it looks like duplicated constants of the same type are not removed,
the code uses "x is y".

codetransformer
---------------

* Line numbers are not first citizen: need to provide a raw mapping:
  offset => line number
* Jump targets are directly instructions.
* Don't support blocks.


See also
========

* `codetransformer
  <https://pypi.python.org/pypi/codetransformer>`_
* `byteplay
  <https://github.com/serprex/byteplay>`_
* `PEP 511 -- API for code transformers
  <https://www.python.org/dev/peps/pep-0511/>`_

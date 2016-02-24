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


ChangeLog
=========

* Version 0.1

  - LOAD_CONST argument is now directly the constant value
  - Add ConcreteInstr; Instr looks its assemble() method
  - Support EXTENDED_ARG
  - Add optional extended_arg_op parameter to Instr.disassemble()
    and Code.disassemble() class methods to use explicit EXTEND_ARG opcode

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

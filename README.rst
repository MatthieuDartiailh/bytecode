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

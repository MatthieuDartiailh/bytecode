ChangeLog
=========

* Version 0.2

  - Fix bug #1: support jumps larger than 2^16.
  - Add bytecode.peephole_opt: a peephole optimizer, code based on
    peephole optimizer of CPython 3.6 which is implemented in C
  - Handle correctly cell and free variables. Instr now uses variable name
    instead of integer for cell/free variables
  - ConcreteInstr is now mutable
  - Add copy() methods to Instr and ConcreteInstr
  - Fix ConcreteBytecode for code with no constant (empty list of constants)
  - Fix argnames in ConcreteBytecode.to_bytecode(): use CO_VARARGS and
    CO_VARKEYWORDS flags to count the number of arguments
  - Fix also bugs in the peephole_opt.py example
  - Fix const_key() to compare correctly constants equal but of different types
    and special cases like -0.0 and +0.0

* 2016-02-26: Version 0.1

  - Rewrite completely the API!

* 2016-02-23: Release 0.0

  - First public release

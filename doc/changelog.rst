ChangeLog
=========

* Version 0.2

  - New major rework of the API.
  - The project has now a documentation:
    `bytecode documentation <https://bytecode.readthedocs.org/>`_
  - Fix bug #1: support jumps larger than 2^16.
  - Add a new :ref:`bytecode.peephole_opt module <peephole_opt>`: a peephole
    optimizer, code based on peephole optimizer of CPython 3.6 which is
    implemented in C
  - :class:`BytecodeBlocks` don't use labels anymore. Jump targets are now
    blocks (:class:`Block`).
  - :class:`Instr` now uses variable name instead of integer for cell and free
    variables.
  - :class:`ConcreteInstr` is now mutable
  - Add :meth:`Instr.copy` and :meth:`ConcreteInstr.copy` methods
  - Fix :class:`ConcreteBytecode` for code with no constant (empty list of
    constants)
  - Fix argnames in :meth:`ConcreteBytecode.to_bytecode`: use CO_VARARGS and
    CO_VARKEYWORDS flags to count the number of arguments
  - Fix const_key() to compare correctly constants equal but of different types
    and special cases like ``-0.0`` and ``+0.0``

* 2016-02-26: Version 0.1

  - Rewrite completely the API!

* 2016-02-23: Release 0.0

  - First public release

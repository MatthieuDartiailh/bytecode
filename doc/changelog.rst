ChangeLog
=========

* 2016-02-29: Version 0.2

  - Again, the API is deeply reworked.
  - The project has now a documentation:
    `bytecode documentation <https://bytecode.readthedocs.org/>`_
  - Fix bug #1: support jumps larger than 2^16.
  - Add a new :ref:`bytecode.peephole_opt module <peephole_opt>`: a peephole
    optimizer, code based on peephole optimizer of CPython 3.6 which is
    implemented in C
  - Add :func:`dump_bytecode` function to ease debug.
  - :class:`Instr`:

    * Add :func:`Instr.is_final` method
    * Add :meth:`Instr.copy` and :meth:`ConcreteInstr.copy` methods
    * :class:`Instr` now uses variable name instead of integer for cell and
      free variables.
    * Rename ``Instr.is_jump`` to :meth:`Instr.has_jump`


  - :class:`ConcreteInstr` is now mutable
  - Redesign the :class:`BytecodeBlocks` class:

    - :class:`Block` have no more label attribute: jump targets are now
      directly blocks
    - Rename ``BytecodeBlocks.add_label()`` method to
      :meth:`BytecodeBlocks.split_block`
    - Labels are not more allowed in blocks
    - :meth:`BytecodeBlocks.from_bytecode` now splits blocks after final
      instructions (:meth:`Instr.is_final`) and after conditional jumps
      (:meth:`Instr.is_cond_jump`). It helps the peephole optimizer to
      respect the control flow and to remove dead code.

  - Rework API to convert bytecode classes:

    - BytecodeBlocks: Remove ``to_concrete_bytecode()`` and ``to_code()``
      methods. Now you first have to convert blocks to bytecode using
      :meth:`~BytecodeBlocks.to_bytecode`.
    - Remove ``Bytecode.to_bytecode_blocks()`` method, replaced with
      :meth:`BytecodeBlocks.from_bytecode`
    - Remove ``ConcreteBytecode.to_concrete_bytecode()`` and
      ``Bytecode.to_bytecode()`` methods which did nothing (return ``self``)

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

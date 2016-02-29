************
Bytecode API
************

bytecode module version string: ``bytecode.__version__`` (ex: ``'0.1'``).

.. data:: UNSET

   Singleton used to mark the lack of value. It is different than ``None``.

Instruction classes:

* :class:`Instr`
* :class:`ConcreteInstr`
* :class:`Label`
* :class:`SetLineno`

Bytecode classes:

* :class:`BaseBytecode`
* :class:`Bytecode`
* :class:`ConcreteBytecode`
* :class:`Block`
* :class:`BytecodeBlocks`


Functions
=========

.. function:: dump_bytecode(bytecode, \*, lineno=False)

   Dump a bytecode to the standard output. :class:`ConcreteBytecode`,
   :class:`Bytecode` and :class:`BytecodeBlocks` are accepted for *bytecode*.

   If *lineno*, show also line numbers and instruction index/offset.

   This function is written for debug purpose.


Instruction classess
====================

Instr
-----

.. class:: Instr(name, arg=UNSET, \*, lineno=None)

   Abstract instruction.

   The type of the :attr:`arg` attribute depends on the operation.

   :class:`Label` argument must only be used with operation having a jump
   argument.

   Attributes:

   .. attribute:: name

      Operation name

   .. attribute:: op

      Operation code.

   .. attribute:: arg

      Argument value. It can be :data:`UNSET` if the instruction has no
      argument.

   .. attribute:: lineno

      Line number (``int`` greater or equal than ``1``), or ``None``.

   Methods:

   .. method:: copy()

      Create a copy of the instruction.

   .. method:: is_final()

      Is the operation a final operation? Return a boolean.

      Final operations:

      * RETURN_VALUE
      * RAISE_VARARGS
      * BREAK_LOOP
      * CONTINUE_LOOP
      * unconditional jumps: :meth:`is_uncond_jump`

   .. method:: has_jump()

      Does the operation have a jump argument? Return a boolean.

      More general than :meth:`is_cond_jump` and :meth:`is_uncond_jump`, it
      includes other operations. Examples:

      * FOR_ITER
      * SETUP_EXCEPT
      * CONTINUE_LOOP

   .. method:: is_cond_jump()

      Is the operation an conditional jump? Return a boolean.

      Conditional jumps:

      * JUMP_IF_FALSE_OR_POP
      * JUMP_IF_TRUE_OR_POP
      * POP_JUMP_IF_FALSE
      * POP_JUMP_IF_TRUE

   .. method:: is_uncond_jump()

      Is the operation an unconditional jump? Return a boolean.

      Unconditional jumps:

      * JUMP_FORWARD
      * JUMP_ABSOLUTE

   .. method:: set(name, arg=UNSET, \*, lineno=None):

      Replace all attributes at once.


ConcreteInstr
-------------

.. class:: ConcreteInstr(name, arg=UNSET, \*, lineno=None)

   Concrete instruction, inherit from :class:`Instr`.

   If the operation requires an argument, *arg* must be an integer.
   If the operation has no argument, *arg* must not by set.

   Use the :meth:`~Instr.set` method to replace the operation name and the
   argument at once. Otherwise, an exception can be raised if the
   previous operation requires an argument and the new operation has no
   argument (or the opposite).

   Concrete instructions should only be used in :class:`ConcreteBytecode`.

   Attributes:

   .. attribute:: arg

      Argument value (``int`` in range ``0``..\ ``2147483647``), or
      :data:`UNSET`. Changing the argument value can change the instruction
      size (:attr:`size`).

   .. attribute:: size

      Read-only size of the instruction in bytes: between ``1`` byte (no
      agument) and ``6`` bytes (extended argument).

   Static method:

   .. staticmethod:: disassemble(code: bytes, offset: int)

      Create a concrete instruction (:class:`ConcreteInstr`) from a bytecode
      string.

   Methods:

   .. method:: get_jump_target(instr_offset)

      Get the absolute target offset of a jump. Return ``None`` if the
      instruction is not a jump.

      The *instr_offset* parameter is the offset of the instruction. It is
      required by relative jumps.

   .. method:: assemble() -> bytes

      Assemble the instruction to a bytecode string.


Label
-----

.. class:: Label

   Pseudo-instruction used as targets of jump instructions.

   Label targets are "resolved" by :class:`Bytecode.to_concrete_bytecode`.

   Labels must only be used in :class:`Bytecode`.


SetLineno
---------

.. class:: SetLineno(lineno: int)

   Pseudo-instruction to set the line number of following instructions.


Bytecode classes
================

BaseBytecode
------------

.. class:: BaseBytecode

   Base class of bytecode classes.

   Attributes:

   .. attribute:: argcount

      Argument count (``int``), default: ``0``.

   .. attribute:: cellvars

      Names of the cell variables (``list`` of ``str``), default: empty list.

   .. attribute:: docstring

      Document string aka "docstring" (``str``), ``None``, or :data:`UNSET`.
      Default: :data:`UNSET`.

      If set, it is used by :meth:`ConcreteBytecode.to_code` as the first
      constant of the created Python code object.

   .. attribute:: filename

      Code filename (``str``), default: ``<string>``.

   .. attribute:: first_lineno

      First line number (``int``), default: ``1``.

   .. attribute:: flags

      Flags (``int``).

   .. attribute:: freevars

      List of free variable names (``list`` of ``str``), default: empty list.

   .. attribute:: kw_only_argcount

      Keyword-only argument count (``int``), default: ``0``.

   .. attribute:: name

      Code name (``str``), default: ``<module>``.


Bytecode
--------

.. class:: Bytecode

   Abstract bytecode: list of abstract instructions (:class:`Instr`).
   Inherit from :class:`BaseBytecode` and :class:`list`.

   It is possible to use concrete instructions (:class:`ConcreteInstr`), but
   abstract instructions are preferred.

   Attributes:

   .. attribute:: argnames

      Names of the argument names (``list`` of ``str``), default: empty list.

   Static methods:

   .. staticmethod:: from_code()

      Create an abstract bytecode from a Python code object.

   Methods:

   .. method:: to_code()

      Convert to a Python code object (:class:`types.CodeType`).

   .. method:: to_concrete_bytecode()

      Convert to concrete bytecode with concrete instructions. Resolve jumps
      using labels (:class:`Label`).


ConcreteBytecode
----------------

.. class:: ConcreteBytecode

   List of concrete instructions (:class:`ConcreteInstr`).
   Inherit from :class:`BaseBytecode`.

   Attributes:

   .. attribute:: consts

      List of constants (``list``), default: empty list.

   .. attribute:: names

      List of names (``list`` of ``str``), default: empty list.

   .. attribute:: varnames

      List of variable names (``list`` of ``str``), default: empty list.

   Static methods:

   .. staticmethod:: from_code(\*, extended_arg=false)

      Create a concrete bytecode from a Python code object.

      If *extended_arg* is true, decode ``EXTENDED_ARG`` instructions.
      Otherwise, concrete instruction may be extended (size of ``6`` bytes
      rather than ``3`` bytes).

   Methods:

   .. method:: to_code()

      Convert to a Python code object (:class:`types.CodeType`).

   .. method:: to_bytecode()

      Convert to abstrct bytecode with abstract instructions.


Block
-----

.. class:: Block

   List of abstract instructions (:class:`Instr`). Inherit from :class:`list`.

   Labels (:class:`Label`) must not be used in blocks.

   Attributes:

   .. attribute:: next_block

      Next block (:class:`Block`), or ``None``.


BytecodeBlocks
--------------

.. class:: BytecodeBlocks

   List of blocks (:class:`Block`), a block is a list of abstract instructions
   (:class:`Instr`). Inherit from :class:`BaseBytecode`.

   Jump targets are blocks (:class:`Block`).

   It is possible to use concrete instructions (:class:`ConcreteInstr`) in
   blocks, but abstract instructions are preferred.

   Labels (:class:`Label`) must not be used in blocks.

   This class is not designed to emit code, but to analyze and modify existing
   code. Use :class:`Bytecode` to emit code.

   Attributes:

   .. attribute:: argnames

      Names of the argument names (``list`` of ``str``), default: empty list.

   Methods:

   .. staticmethod:: from_bytecode(bytecode)

      Create a :class:`Bytecode` object to a :class:`BytecodeBlocks` object:
      replace labels with blocks.

      Splits blocks after final instructions (:meth:`Instr.is_final`) and after
      conditional jumps (:meth:`Instr.is_cond_jump`).

   .. method:: add_block(instructions=None)

      Add a new block. Return the new :class:`Block`.

   .. method:: split_block(block: Block, index: int)

      Split a block into two blocks at the specific instruction. Return
      the newly created block, or *block* if index equals ``0``.


Line Numbers
============

The line number can set directly on an instruction using the ``lineno``
parameter of the constructor. Otherwise, the line number if inherited from the
previous instruction, starting at ``first_lineno`` of the bytecode.

:class:`SetLineno` pseudo-instruction can be used to set the line number of
following instructions.

************
Bytecode API
************

bytecode module version string: ``bytecode.__version__`` (ex: ``'0.1'``).

.. data:: UNSET

   Singleton used to mark the lack of value. It is different than ``None``.

Instruction classes:

* :class:`BaseInstr`
* :class:`Instr`
* :class:`ConcreteInstr`
* :class:`Compare`
* :class:`Label`
* :class:`SetLineno`

Bytecode classes:

* :class:`BaseBytecode`
* :class:`Bytecode`
* :class:`ConcreteBytecode`
* :class:`BasicBlock`
* :class:`ControlFlowGraph`

Cell and Free Variables:

* :class:`CellVar`
* :class:`FreeVar`


Functions
=========

.. function:: dump_bytecode(bytecode, \*, lineno=False)

   Dump a bytecode to the standard output. :class:`ConcreteBytecode`,
   :class:`Bytecode` and :class:`ControlFlowGraph` are accepted for *bytecode*.

   If *lineno*, show also line numbers and instruction index/offset.

   This function is written for debug purpose.


Instruction classess
====================

BaseInstr
---------

.. class:: BaseInstr(name: str, arg=UNSET, \*, lineno: int=None)

   Base class of instruction classes.

   To replace the operation name and the argument, the :meth:`set` method must
   be used instead of than modifying the :attr:`name` attribute and then the
   :attr:`arg` attribute. Otherwise, an exception is be raised if the previous
   operation requires an argument and the new operation has no argument (or the
   opposite).

   Attributes:

   .. attribute:: arg

      Argument value.

      It can be :data:`UNSET` if the instruction has no argument.

   .. attribute:: lineno

      Line number (``int >= 1``), or ``None``.

   .. attribute:: name

      Operation name (``str``).

   .. attribute:: opcode

      Operation code (``int``).

   .. versionchanged:: 0.3
      The ``op`` attribute was renamed to :attr:`opcode`.

   Methods:

   .. method:: copy()

      Create a copy of the instruction.

   .. method:: is_final() -> bool

      Is the operation a final operation?

      Final operations:

      * RETURN_VALUE
      * RAISE_VARARGS
      * BREAK_LOOP
      * CONTINUE_LOOP
      * unconditional jumps: :meth:`is_uncond_jump`

   .. method:: has_jump() -> bool

      Does the operation have a jump argument?

      More general than :meth:`is_cond_jump` and :meth:`is_uncond_jump`, it
      includes other operations. Examples:

      * FOR_ITER
      * SETUP_EXCEPT
      * CONTINUE_LOOP

   .. method:: is_cond_jump() -> bool

      Is the operation an conditional jump?

      Conditional jumps:

      * JUMP_IF_FALSE_OR_POP
      * JUMP_IF_TRUE_OR_POP
      * POP_JUMP_IF_FALSE
      * POP_JUMP_IF_TRUE

   .. method:: is_uncond_jump() -> bool

      Is the operation an unconditional jump?

      Unconditional jumps:

      * JUMP_FORWARD
      * JUMP_ABSOLUTE

   .. method:: set(name: str, arg=UNSET)

      Modify the instruction in-place: replace :attr:`name` and :attr:`arg`
      attributes.

      The :attr:`lineno` attribute is unchanged.

      .. versionchanged:: 0.3
         The *lineno* parameter has been removed.


Instr
-----

.. class:: Instr(name: str, arg=UNSET, \*, lineno: int=None)

   Abstract instruction. Inherit from :class:`BaseInstr`.

   The type of the *arg* parameter (and the :attr:`arg` attribute) depends on
   the operation:

   * If the operation has a jump argument (:meth:`has_jump`, ex:
     ``JUMP_ABSOLUTE``): *arg* must be a :class:`Label` (if the instruction is
     used in :class:`Bytecode`) or a :class:`BasicBlock` (used in
     :class:`ControlFlowGraph`).
   * If the operation has a cell or free argument (ex: ``LOAD_DEREF``): *arg*
     must be a :class:`CellVar` or :class:`FreeVar` instance.
   * If the operation has a local variable (ex: ``LOAD_FAST``): *arg* must be a
     variable name, type ``str``.
   * If the operation has a constant argument (``LOAD_CONST``): *arg* must not
     be a :class:`Label` or :class:`BasicBlock` instance.
   * If the operation has a compare argument (``'COMPARE_OP'``):
     *arg* must a :class:`Compare` enum.
   * If the operation has no argument (ex: ``DUP_TOP``), *arg* must not be set.
   * Otherwise (the operation has an argument, ex: ``CALL_FUNCTION``), *arg*
     must be an integer (``int``) in the range ``0``..\ ``2,147,483,647``.

   .. versionchanged:: 0.3
      The argument is now validated.


ConcreteInstr
-------------

.. class:: ConcreteInstr(name: str, arg=UNSET, \*, lineno: int=None)

   Concrete instruction Inherit from :class:`BaseInstr`.

   If the operation requires an argument, *arg* must be an integer (``int``) in
   the range ``0``..\ ``2,147,483,647``. Otherwise, *arg* must not by set.

   Concrete instructions should only be used in :class:`ConcreteBytecode`.

   Attributes:

   .. attribute:: arg

      Argument value: an integer (``int``) in the range ``0``..\
      ``2,147,483,647``, or :data:`UNSET`. Changing the argument value can
      change the instruction size (:attr:`size`).

   .. attribute:: size

      Read-only size of the instruction in bytes (``int``): between ``1`` byte
      (no agument) and ``6`` bytes (extended argument).

   Static method:

   .. staticmethod:: disassemble(code: bytes, offset: int) -> ConcreteInstr

      Create a concrete instruction from a bytecode string.

   Methods:

   .. method:: get_jump_target(instr_offset: int) -> int or None

      Get the absolute target offset of a jump. Return ``None`` if the
      instruction is not a jump.

      The *instr_offset* parameter is the offset of the instruction. It is
      required by relative jumps.

   .. method:: assemble() -> bytes

      Assemble the instruction to a bytecode string.


Compare
-------

.. class:: Compare

   Enum for the argument of the ``COMPARE_OP`` instruction.

   Equality test:

   * ``Compare.EQ`` (``2``): ``x == y``
   * ``Compare.NE`` (``3``): ``x != y``
   * ``Compare.IS`` (``8``): ``x is y``
   * ``Compare.IS_NOT`` (``9``): ``x is not y``

   Inequality test:

   * ``Compare.LT`` (``0``): ``x < y``
   * ``Compare.LE`` (``1``): ``x <= y``
   * ``Compare.GT`` (``4``): ``x > y``
   * ``Compare.GE`` (``5``): ``x >= y``

   Other tests:

   * ``Compare.IN`` (``6``): ``x in y``
   * ``Compare.NOT_IN`` (``7``): ``x not in y``
   * ``Compare.EXC_MATCH`` (``10``): used to compare exceptions
     for ``except:`` block


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

   *lineno* must be greater or equal than ``1``.

   .. attribute:: lineno

      Line number (``int``), read-only attribute.


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

      Documentation string aka "docstring" (``str``), ``None``, or
      :data:`UNSET`.  Default: :data:`UNSET`.

      If set, it is used by :meth:`ConcreteBytecode.to_code` as the first
      constant of the created Python code object.

   .. attribute:: filename

      Code filename (``str``), default: ``'<string>'``.

   .. attribute:: first_lineno

      First line number (``int``), default: ``1``.

   .. attribute:: flags

      Flags (``int``).

   .. attribute:: freevars

      List of free variable names (``list`` of ``str``), default: empty list.

   .. attribute:: kwonlyargcount

      Keyword-only argument count (``int``), default: ``0``.

   .. attribute:: name

      Code name (``str``), default: ``'<module>'``.

   .. versionchanged:: 0.3
      Attribute ``kw_only_argcount`` renamed to :attr:`kwonlyargcount`.


Bytecode
--------

.. class:: Bytecode

   Abstract bytecode: list of abstract instructions (:class:`Instr`).
   Inherit from :class:`BaseBytecode` and :class:`list`.

   A bytecode must only contain objects of the 4 following types:

   * :class:`Label`
   * :class:`SetLineno`
   * :class:`Instr`
   * :class:`ConcreteInstr`

   It is possible to use concrete instructions (:class:`ConcreteInstr`), but
   abstract instructions are preferred.

   Attributes:

   .. attribute:: argnames

      List of the argument names (``list`` of ``str``), default: empty list.

   Static methods:

   .. staticmethod:: from_code() -> Bytecode

      Create an abstract bytecode from a Python code object.

   Methods:

   .. method:: to_concrete_bytecode() -> ConcreteBytecode

      Convert to concrete bytecode with concrete instructions.

      Resolve jump targets: replace abstract labels (:class:`Label`) with
      concrete instruction offsets (relative or absolute, depending on the jump
      operation).

   .. method:: to_code() -> types.CodeType

      Convert to a Python code object.

      It is based on :meth:`to_concrete_bytecode` and so resolve jump targets.



ConcreteBytecode
----------------

.. class:: ConcreteBytecode

   List of concrete instructions (:class:`ConcreteInstr`).
   Inherit from :class:`BaseBytecode`.

   A concrete bytecode must only contain objects of the 2 following types:

   * :class:`SetLineno`
   * :class:`ConcreteInstr`

   :class:`Label` and :class:`Instr` must not be used in concrete bytecode.

   Attributes:

   .. attribute:: consts

      List of constants (``list``), default: empty list.

   .. attribute:: names

      List of names (``list`` of ``str``), default: empty list.

   .. attribute:: varnames

      List of variable names (``list`` of ``str``), default: empty list.

   Static methods:

   .. staticmethod:: from_code(\*, extended_arg=false) -> ConcreteBytecode

      Create a concrete bytecode from a Python code object.

      If *extended_arg* is true, create ``EXTENDED_ARG`` instructions.
      Otherwise, concrete instruction use extended argument (size of ``6``
      bytes rather than ``3`` bytes).

   Methods:

   .. method:: to_code() -> types.CodeType

      Convert to a Python code object.

      On Python older than 3.6, raise an exception on negative line number
      delta.

   .. method:: to_bytecode() -> Bytecode

      Convert to abstract bytecode with abstract instructions.


BasicBlock
----------

.. class:: BasicBlock

   `Basic block <https://en.wikipedia.org/wiki/Basic_block>`_. Inherit from
   :class:`list`.

   A basic block is a straight-line code sequence of abstract instructions
   (:class:`Instr`) with no branches in except to the entry and no branches out
   except at the exit.

   A block must only contain objects of the 3 following types:

   * :class:`SetLineno`
   * :class:`Instr`
   * :class:`ConcreteInstr`

   It is possible to use concrete instructions (:class:`ConcreteInstr`) in
   blocks, but abstract instructions (:class:`Instr`) are preferred.

   Only the last instruction can have a jump argument, and the jump argument
   must be a basic block (:class:`BasicBlock`).

   Labels (:class:`Label`) must not be used in blocks.

   Attributes:

   .. attribute:: next_block

      Next basic block (:class:`BasicBlock`), or ``None``.

   Methods:

   .. method:: get_jump()

      Get the target block (:class:`BasicBlock`) of the jump if the basic block
      ends with an instruction with a jump argument. Otherwise, return
      ``None``.


ControlFlowGraph
----------------

.. class:: ControlFlowGraph

   `Control flow graph (CFG)
   <https://en.wikipedia.org/wiki/Control_flow_graph>`_: list of basic blocks
   (:class:`BasicBlock`). A basic block is a straight-line code sequence of
   abstract instructions (:class:`Instr`) with no branches in except to the
   entry and no branches out except at the exit. Inherit from
   :class:`BaseBytecode`.

   Labels (:class:`Label`) must not be used in blocks.

   This class is not designed to emit code, but to analyze and modify existing
   code. Use :class:`Bytecode` to emit code.

   Attributes:

   .. attribute:: argnames

      List of the argument names (``list`` of ``str``), default: empty list.

   Methods:

   .. staticmethod:: from_bytecode(bytecode: Bytecode) -> ControlFlowGraph

      Convert a :class:`Bytecode` object to a :class:`ControlFlowGraph` object:
      convert labels to blocks.

      Splits blocks after final instructions (:meth:`Instr.is_final`) and after
      conditional jumps (:meth:`Instr.is_cond_jump`).

   .. method:: add_block(instructions=None) -> BasicBlock

      Add a new basic block. Return the newly created basic block.

   .. method:: get_block_index(block: BasicBlock) -> int

      Get the index of a block in the bytecode.

      Raise a :exc:`ValueError` if the block is not part of the bytecode.

      .. versionadded:: 0.3

   .. method:: split_block(block: BasicBlock, index: int) -> BasicBlock

      Split a block into two blocks at the specific instruction. Return
      the newly created block, or *block* if index equals ``0``.

   .. method:: to_bytecode() -> Bytecode

      Convert to a bytecode object using labels.


Cell and Free Variables
=======================

CellVar
-------

.. class:: CellVar(name: str)

   Cell variable used for instruction argument by operations taking a cell or
   free variable name.


   Attributes:

   .. attribute:: name

      Name of the cell variable (``str``).


FreeVar
-------

.. class:: FreeVar(name: str)

   Free variable used for instruction argument by operations taking a cell or
   free variable name.

   Attributes:

   .. attribute:: name

      Name of the free variable (``str``).


Line Numbers
============

The line number can set directly on an instruction using the ``lineno``
parameter of the constructor. Otherwise, the line number if inherited from the
previous instruction, starting at ``first_lineno`` of the bytecode.

:class:`SetLineno` pseudo-instruction can be used to set the line number of
following instructions.

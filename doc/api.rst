************
Bytecode API
************

* Constants: :data:`__version__`, :data:`UNSET`
* Abstract bytecode: :class:`Label`, :class:`Instr`, :class:`Bytecode`
* Line number: :class:`SetLineno`
* Arguments: :class:`CellVar`, :class:`Compare`, :class:`FreeVar`
* Concrete bytecode: :class:`ConcreteInstr`, :class:`ConcreteBytecode`
* Control Flow Graph (CFG): :class:`BasicBlock`, :class:`ControlFlowGraph`
* Base class: :class:`BaseBytecode`


Constants
=========

.. data:: __version__

   Module version string (ex: ``'0.1'``).

.. data:: UNSET

   Singleton used to mark the lack of value. It is different than ``None``.


Functions
=========

.. function:: format_bytecode(bytecode, \*, lineno: bool = False) -> str:

   Format a bytecode to a str representation. :class:`ConcreteBytecode`,
   :class:`Bytecode` and :class:`ControlFlowGraph` are accepted for *bytecode*.

   If *lineno* is true, show also line numbers and instruction index/offset.

   This function is written for debug purpose.

.. function:: dump_bytecode(bytecode, \*, lineno=False)

   Dump a bytecode to the standard output. :class:`ConcreteBytecode`,
   :class:`Bytecode` and :class:`ControlFlowGraph` are accepted for *bytecode*.

   If *lineno* is true, show also line numbers and instruction index/offset.

   This function is written for debug purpose.


Instruction classes
===================

Instr
-----

.. class:: Instr(name: str, arg=UNSET, \*, lineno: Union[int, None, UNSET] = UNSET, location: Optional[InstrLocation] = None)

   Abstract instruction.

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
   * If the operation has a compare argument (``COMPARE_OP``):
     *arg* must be a :class:`Compare` enum.
   * If the operation has no argument (ex: ``DUP_TOP``), *arg* must not be set.
   * Otherwise (the operation has an argument, ex: ``CALL_FUNCTION``), *arg*
     must be an integer (``int``) in the range ``0``..\ ``2,147,483,647``.

   To replace the operation name and the argument, the :meth:`set` method must
   be used instead of modifying the :attr:`name` attribute and then the
   :attr:`arg` attribute. Otherwise, an exception is raised if the previous
   operation requires an argument and the new operation has no argument (or the
   opposite).

   Attributes:

   .. attribute:: arg

      Argument value.

      It can be :data:`UNSET` if the instruction has no argument.

   .. attribute:: lineno

      Line number (``int >= 1``), or ``None``.

   .. attribute:: name

      Operation name (``str``). Setting the name updates the :attr:`opcode`
      attribute.

   .. attribute:: opcode

      Operation code (``int``). Setting the operation code updates the
      :attr:`name` attribute.

   .. versionchanged:: 0.3
      The ``op`` attribute was renamed to :attr:`opcode`.

   .. attribute:: location

      Detailed location (:class:`InstrLocation`)

   Methods:

   .. method:: require_arg() -> bool

      Does the instruction require an argument?

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

      Is the operation a conditional jump?

      Conditional jumps:

      * JUMP_IF_FALSE_OR_POP
      * JUMP_IF_TRUE_OR_POP
      * JUMP_FORWARD_IF_FALSE_OR_POP
      * JUMP_BACKWARD_IF_FALSE_OR_POP
      * JUMP_FORWARD_IF_TRUE_OR_POP
      * JUMP_BACKWARD_IF_TRUE_OR_POP
      * POP_JUMP_IF_FALSE
      * POP_JUMP_IF_TRUE

   .. method:: is_uncond_jump() -> bool

      Is the operation an unconditional jump?

      Unconditional jumps:

      * JUMP_FORWARD
      * JUMP_ABSOLUTE
      * JUMP_BACKWARD
      * JUMP_BACKWARD_NO_INTERRUPT

   .. method:: is_abs_jump() -> bool

      Is the operation an absolute jump?

   .. method:: is_forward_rel_jump() -> bool

      Is the operation a forward relative jump?

   .. method:: is_backward_rel_jump() -> bool

      Is the operation a backward relative jump?

   .. method:: set(name: str, arg=UNSET)

      Modify the instruction in-place: replace :attr:`name` and :attr:`arg`
      attributes, and update the :attr:`opcode` attribute.

      .. versionchanged:: 0.3
         The *lineno* parameter has been removed.

   .. method:: stack_effect(jump: bool = None) -> int

      Operation effect on the stack size as computed by
      :func:`dis.stack_effect`.

      The *jump* argument takes one of three values.  None (the default)
      requests the largest stack effect.  This works fine with most
      instructions.  True returns the stack effect for taken branches.  False
      returns the stack effect for non-taken branches.

      .. versionchanged:: 0.8
         ``stack_effect`` was changed from a property to a method in order to
         add the keyword argument *jump*.

    .. method:: pre_and_post_stack_effect(jump: Optional[bool] = None) -> Tuple[int, int]

      Effect of the instruction on the stack before and after its execution.

      The impact on the stack before the instruction reflects how many values
      from the stacks are used/popped. The impact on the stack after the
      instruction execution reflects how many values are pushed back on the
      stack. Those are deduced from :func:`dis.stack_effect` and manual
      analysis.

      The *jump* argument has the same meaning as in
      :py:meth:`Instr.stack_effect`.

      .. versionadded:: 0.12


ConcreteInstr
-------------

.. class:: ConcreteInstr(name: str, arg=UNSET, \*, lineno: int=None)

   Concrete instruction Inherit from :class:`Instr`.

   If the operation requires an argument, *arg* must be an integer (``int``) in
   the range ``0``..\ ``2,147,483,647``. Otherwise, *arg* must not by set.

   Concrete instructions should only be used in :class:`ConcreteBytecode`.

   Attributes:

   .. attribute:: arg

      Argument value: an integer (``int``) in the range ``0``..\
      ``2,147,483,647``, or :data:`UNSET`. Setting the argument value can
      change the instruction size (:attr:`size`).

   .. attribute:: size

      Read-only size of the instruction in bytes (``int``): between ``1`` byte
      (no argument) and ``6`` bytes (extended argument).

   Static method:

   .. staticmethod:: disassemble(code: bytes, offset: int) -> ConcreteInstr

      Create a concrete instruction from a bytecode string.

   Methods:

   .. method:: get_jump_target(instr_offset: int) -> int or None

      Get the absolute target offset of a jump. Return ``None`` if the
      instruction is not a jump.

      The *instr_offset* parameter is the offset of the instruction. It is
      required by relative jumps.

      .. note::

         Starting with Python 3.10, this quantity is expressed in term of
         instruction offset rather than byte offset, and is hence twice smaller
         than in 3.9 for identical code.

   .. method:: assemble() -> bytes

      Assemble the instruction to a bytecode string.

   .. method:: use_cache_opcodes() -> int

      Number of cache opcodes that should follow the instruction.


Compare
-------

.. class:: Compare

   Enum for the argument of the ``COMPARE_OP`` instruction.

   Equality test:

   * ``Compare.EQ`` (``2``): ``x == y``
   * ``Compare.NE`` (``3``): ``x != y``
   * ``Compare.IS`` (``8``): ``x is y`` removed in Python 3.9+
   * ``Compare.IS_NOT`` (``9``): ``x is not y`` removed in Python 3.9+

   Inequality test:

   * ``Compare.LT`` (``0``): ``x < y``
   * ``Compare.LE`` (``1``): ``x <= y``
   * ``Compare.GT`` (``4``): ``x > y``
   * ``Compare.GE`` (``5``): ``x >= y``

   Other tests:

   * ``Compare.IN`` (``6``): ``x in y`` removed in Python 3.9+
   * ``Compare.NOT_IN`` (``7``): ``x not in y`` removed in Python 3.9+
   * ``Compare.EXC_MATCH`` (``10``): used to compare exceptions
     in ``except:`` blocks. Removed in Python 3.9+


Binary operation
----------------

.. class:: BinaryOp

   Enum for the argument of the ``BINARY_OP`` instruction (3.11+).

   Arithmetic operations

   ``BinaryOp.ADD`` (``0``): ``x + y``
   ``BinaryOp.SUBTRACT`` (``10``): ``x - y``
   ``BinaryOp.MULTIPLY`` (``5``): ``x * y``
   ``BinaryOp.TRUE_DIVIDE`` (``11``): ``x / y``
   ``BinaryOp.FLOOR_DIVIDE`` (``2``): ``x // y``
   ``BinaryOp.REMAINDER`` (``6``): ``x % y``
   ``BinaryOp.MATRIX_MULTIPLY`` (``4``): ``x @ y``
   ``BinaryOp.POWER`` (``8``): ``x ** y``

   Logical and binary operations

   ``BinaryOp.LSHIFT`` (``3``): ``x << y``
   ``BinaryOp.RSHIFT`` (``9``): ``x >> y``
   ``BinaryOp.AND`` (``1``): ``x & y``
   ``BinaryOp.OR`` (``7``): ``x | y``
   ``BinaryOp.XOR`` (``12``): ``x ^ y``

   Inplace operations:

   ``BinaryOp.INPLACE_ADD`` (``13``): ``x += y``
   ``BinaryOp.INPLACE_SUBTRACT`` (``23``): ``x -= y``
   ``BinaryOp.INPLACE_MULTIPLY`` (``18``): ``x *= y``
   ``BinaryOp.INPLACE_TRUE_DIVIDE`` (``24``): ``x /= y``
   ``BinaryOp.INPLACE_FLOOR_DIVIDE`` (``15``): ``x //= y``
   ``BinaryOp.INPLACE_REMAINDER`` (``19``): ``x %= y``
   ``BinaryOp.INPLACE_MATRIX_MULTIPLY`` (``17``): ``x @= y``
   ``BinaryOp.INPLACE_POWER`` (``21``): ``x **= y``
   ``BinaryOp.INPLACE_LSHIFT`` (``16``): ``x <<= y``
   ``BinaryOp.INPLACE_RSHIFT`` (``22``): ``x >>= y``
   ``BinaryOp.INPLACE_AND`` (``14``): ``x &= y``
   ``BinaryOp.INPLACE_OR`` (``20``): ``x |= y``
   ``BinaryOp.INPLACE_XOR`` (``25``): ``x ^= y``


Intrinsic operations
--------------------

.. class:: Intrinsic1Op

   Enum for the argument of the ``CALL_INTRINSIC_1`` instruction (3.12+).

   ``INTRINSIC_1_INVALID``
   ``INTRINSIC_PRINT``
   ``INTRINSIC_IMPORT_STAR``
   ``INTRINSIC_STOPITERATION_ERROR``
   ``INTRINSIC_ASYNC_GEN_WRAP``
   ``INTRINSIC_UNARY_POSITIVE``
   ``INTRINSIC_LIST_TO_TUPLE``
   ``INTRINSIC_TYPEVAR``
   ``INTRINSIC_PARAMSPEC``
   ``INTRINSIC_TYPEVARTUPLE``
   ``INTRINSIC_SUBSCRIPT_GENERIC``
   ``INTRINSIC_TYPEALIAS``

.. class:: Intrinsic2Op

   Enum for the argument of the ``CALL_INTRINSIC_2`` instruction (3.12+).

   ``INTRINSIC_2_INVALID``
   ``INTRINSIC_PREP_RERAISE_STAR``
   ``INTRINSIC_TYPEVAR_WITH_BOUND``
   ``INTRINSIC_TYPEVAR_WITH_CONSTRAINTS``
   ``INTRINSIC_SET_FUNCTION_TYPE_PARAMS``


CellVar and FreeVar
-------------------

The following classes are used to represent the argument of opcode listed in
``opcode.hasfree`` which includes:

- MAKE_CELL
- LOAD_CLOSURE
- LOAD_DEREF
- STORE_DEREF
- DELETE_DEREF
- LOAD_CLASSDEREF
- LOAD_FROM_DICT_OR_DEREF

.. class:: CellVar

   Argument of an opcode referring to a variable held in a cell.

   Cell variables cannot always be inferred only from the instructions
   (``__class__`` used by super() is implicit) and as a consequence cellvars are
   explicitly listed on all bytecode objects.

   Attributes:

   .. attribute:: name

      Name of the cell variable (``str``).

.. class:: FreeVar

   Argument of opcode referring to a free variable.

   Free variables cannot always be inferred only from the instructions
   (``__class__`` used by super() is implicit) and as a consequence freevars are
   explicitly listed on all bytecode objects.

   Attributes:

   .. attribute:: name

      Name of the free variable (``str``).


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

InstrLocation
-------------

.. class:: InstrLocation(lineno: Optional[int], end_lineno: Optional[int],        col_offset: Optional[int], end_col_offset: Optional[int])

   Detailed location for an instruction.

   .. attribute:: lineno

      Line number on which the instruction starts.

   .. attribute:: end_lineno

      Line number on which the instruction ends.

   .. attribute:: col_offset

      Column offset within the start line at which the instruction starts.

   .. attribute:: end_col_offset

      Column offset within the end line at which the instruction starts.

   .. classmethod:: from_positions(cls, position: dis.Positions) -> InstrLocation

      Build an InstrLocation from a dis.Position object.


TryBegin
--------

.. class:: TryBegin(target: Union[Label, BasicBlock], push_lasti: bool, stack_depth: Union[int, UNSET] = UNSET)

   Pseudo instruction marking the beginning of an exception table entry.

   TryBegin can never be nested.

   Used in Python 3.11+ in :class:`Bytecode` and :class:`BasicBlock`.

   .. attribute:: target

      Target :class:`Label` or :class:`BasicBlock` to which to jump to if an exception
      occurs on an instruction sitting between this :class:`TryBegin` and the
      matching :class:`TryEnd`.

   .. attribute:: push_lasti

      Is the instruction offset at which an exception occurred pushed on the stack
      before the exception itself when handling an exception.

   .. attribute:: stack_depth

      Stack depth that will be restored by the interpreter by popping from the stack
      when handling an exception, before pushing the exception possibly preceded by
      the instruction offset depending on :attr:`TryBegin.push_lasti`.

   .. method:: copy() -> TryBegin

      Create a copy of the TryBegin.


TryEnd
------

.. class:: TryEnd(entry: TryBegin)

   Pseudo instruction marking the end of an exception table entry.

   .. note::

      In a :class:`BasicBlock`, one may find a :class:`TryEnd` instance after a final
      instruction. This results from the exception enclosing the final instruction.
      Since :class:`TryEnd` is only a pseudo-instruction this does not violate
      the guarantee made by a :class:`BasicBlock` which only applies to instructions.

   .. note::

      A jump may cause to exit an exception table entry. If the jump is unconditional
      the instruction is final and the above applies. For conditional jumps, within
      a :class:`ControlFlowGraph`, we insert a :class:`TryEnd` at the beginning of
      the target block to explicitly signal that we left the exception table entry
      region. As a consequence, multiple :class:`TryExit` corresponding to a single
      :class:`TryBegin` can exist. :class:`TryEnd` corresponding to exiting an
      exception table entry through a conditional jump always appear before the
      first instruction of the target block. However, care needs to be taken since
      that block may be reached through a different path in which no :class:`TryBegin`
      was encountered. In such cases, the :class:`TryEnd` should be ignored.


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

   .. attribute:: posonlyargcount

      Positional-only argument count (``int``), default: ``0``.

      New in Python 3.8

   .. attribute:: kwonlyargcount

      Keyword-only argument count (``int``), default: ``0``.

   .. attribute:: name

      Code name (``str``), default: ``'<module>'``.

   .. attribute:: qualname

      Qualified code name (``str``).

      New in Python 3.11

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
   * :class:`TryBegin`
   * :class:`TryEnd`

   .. versionchanged:: 0.14.0

      It is not possible anymore to use concrete instructions (:class:`ConcreteInstr`)
      in :class:`Bytecode`.

   Attributes:

   .. attribute:: argnames

      List of the argument names (``list`` of ``str``), default: empty list.

   Static methods:

   .. staticmethod:: from_code(code) -> Bytecode

      Create an abstract bytecode from a Python code object.

   Methods:

   .. method:: legalize()

      Check the validity of all the instruction and remove the :class:`SetLineno`
      instances after updating the instructions.

   .. method:: to_concrete_bytecode(compute_jumps_passes: int = None, compute_exception_stack_depths: bool = True) -> ConcreteBytecode

      Convert to concrete bytecode with concrete instructions.

      Resolve jump targets: replace abstract labels (:class:`Label`) with
      concrete instruction offsets (relative or absolute, depending on the
      jump operation).  It will also add EXTENDED_ARG prefixes to jump
      instructions to ensure that the target instructions can be reached.

      If *compute_jumps_passes* is not None, it sets the upper limit for the
      number of passes that can be made to generate EXTENDED_ARG prefixes for
      jump instructions. If None then an internal default is used.  The number
      of passes is, in theory, limited only by the number of input
      instructions, however a much smaller default is used because the
      algorithm converges quickly on most code.  For example, running CPython
      3.6.5 unittests on OS X 11.13 results in 264996 compiled methods, only
      one of which requires 5 passes, and none requiring more.

      If *compute_exception_stack_depths*  is True, the stack depth for each
      exception table entry will be computed (which requires to convert the
      the bytecode to a :class:`ControlFlowGraph`)

   .. method:: to_code(compute_jumps_passes: int = None, stacksize: int = None, *, check_pre_and_post: bool = True, compute_exception_stack_depths: bool = True) -> types.CodeType

      Convert to a Python code object.

      It is based on :meth:`to_concrete_bytecode` and so resolve jump targets.

      *compute_jumps_passes*: see :meth:`to_concrete_bytecode`

      *stacksize*: see :meth:`ConcreteBytecode.to_code`

      *check_pre_and_post*: see :meth:`ConcreteBytecode.to_code`

      *compute_exception_stack_depths*: see :meth:`to_concrete_bytecode`

   .. method:: compute_stacksize(*, check_pre_and_post: bool = True) -> int

      Compute the stacksize needed to execute the code. Will raise an
      exception if the bytecode is invalid.

      This computation requires to build the control flow graph associated with
      the code.

      *check_pre_and_post* Allows caller to disable checking for stack underflow

    .. method:: update_flags(is_async: bool = None) -> None

      Update the object flags by calling :py:func:infer_flags on itself.


ConcreteBytecode
----------------

.. class:: ExceptionTableEntry

   Entry for a given line in the exception table.

   All offsets are expressed in instructions not in bytes.

   Attributes:

   .. attribute:: start_offset

      Offset (``int``) in instruction between the beginning of the bytecode and
      the beginning of this entry.

   .. attribute:: stop_offset

      Offset (``int``) in instruction between the beginning of the bytecode and
      the end of this entry. This offset is inclusive meaning that the instruction
      it points to is included in the try/except handling.

   .. attribute:: target

      Offset (``int``) in instruction to the first instruction of the exception
      handling block.

   .. attribute:: stack_depth

      Minimal stack depth (``int``) in the block delineated by start and stop
      offset of the exception table entry. Used to restore the stack (by
      popping items) when entering the exception handling block.

   .. attribute:: push_lasti

      ``bool`` indicating if the offset, at which an exception was raised, should
      be pushed on the stack before the exception itself (which is pushed as a single value).


.. class:: ConcreteBytecode

   List of concrete instructions (:class:`ConcreteInstr`).
   Inherit from :class:`BaseBytecode`.

   A concrete bytecode must only contain objects of the 2 following types:

   * :class:`SetLineno`
   * :class:`ConcreteInstr`

   :class:`Label`, :class:`TryBegin`, :class:`TryEnd` and :class:`Instr` must
   not be used in concrete bytecode.

   Attributes:

   .. attribute:: consts

      List of constants (``list``), default: empty list.

   .. attribute:: names

      List of names (``list`` of ``str``), default: empty list.

   .. attribute:: varnames

      List of variable names (``list`` of ``str``), default: empty list.

   .. attribute:: exception_table

      List of :class:`ExceptionTableEntry` describing portion of the bytecode
      in which exceptions are caught and where there are handled.
      Used only in Python 3.11+

   Static methods:

   .. staticmethod:: from_code(code, \*, extended_arg=false) -> ConcreteBytecode

      Create a concrete bytecode from a Python code object.

      If *extended_arg* is true, create ``EXTENDED_ARG`` instructions.
      Otherwise, concrete instruction use extended argument (size of ``6``
      bytes rather than ``3`` bytes).

   Methods:

   .. method:: legalize()

      Check the validity of all the instruction and remove the :class:`SetLineno`
      instances after updating the instructions.


   .. method:: to_code(stacksize: int = None, *, check_pre_and_post: bool = True, compute_exception_stack_depths: bool = True) -> types.CodeType

      Convert to a Python code object.

      *stacksize* Allows caller to explicitly specify a stacksize.  If not
      specified a :class:`ControlFlowGraph` is created internally in order to call
      :meth:`ControlFlowGraph.compute_stacksize`.  It's cheaper to pass a value if
      the value is known.

      *check_pre_and_post* Allows caller to disable checking for stack underflow

      If *compute_exception_stack_depths*  is True, the stack depth for each
      exception table entry will be computed (which requires to convert the
      the bytecode to a :class:`ControlFlowGraph`)

   .. method:: to_bytecode() -> Bytecode

      Convert to abstract bytecode with abstract instructions.

   .. method:: compute_stacksize(*, check_pre_and_post: bool = True) -> int

      Compute the stacksize needed to execute the code. Will raise an
      exception if the bytecode is invalid.

      This computation requires to build the control flow graph associated with
      the code.

      *check_pre_and_post* Allows caller to disable checking for stack underflow

   .. method:: update_flags(is_async: bool = None)

      Update the object flags by calling :py:func:infer_flags on itself.


BasicBlock
----------

.. class:: BasicBlock

   `Basic block <https://en.wikipedia.org/wiki/Basic_block>`_. Inherit from
   :class:`list`.

   A basic block is a straight-line code sequence of abstract instructions
   (:class:`Instr`) with no branches in except to the entry and no branches out
   except at the exit.

   A block must only contain objects of the 4 following types:

   * :class:`SetLineno`
   * :class:`Instr`
   * :class:`TryBegin`
   * :class:`TryEnd`

   .. versionchanged:: 0.14.0

      It is not possible anymore to use concrete instructions (:class:`ConcreteInstr`)
      in :class:`BasicBlock`.

   Only the last instruction can have a jump argument, and the jump argument
   must be a basic block (:class:`BasicBlock`).

   Labels (:class:`Label`) must not be used in blocks.

   Attributes:

   .. attribute:: next_block

      Next basic block (:class:`BasicBlock`), or ``None``.

   Methods:

   .. method:: legalize(first_lineno: int) -> None

      Check the validity of all the instruction and remove the :class:`SetLineno`
      instances after updating the instructions. `first_lineno` specifies
      the line number to use for instruction without a set line number encountered
      before the first :class:`SetLineno` instance.

   .. method:: get_jump() --> BasicBlock | None

      Get the target block (:class:`BasicBlock`) of the jump if the basic block
      ends with an instruction with a jump argument. Otherwise, return
      ``None``.

   .. method:: get_trailing_end(index: int) -> TryEnd | None

      Get the first TryEnd found after the position ``index`` in the block if any.


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

    .. method:: legalize(first_lineno: int)

      Legalize all the blocks of the CFG.

   .. method:: add_block(instructions=None) -> BasicBlock

      Add a new basic block. Return the newly created basic block.

   .. method:: get_block_index(block: BasicBlock) -> int

      Get the index of a block in the bytecode.

      Raise a :exc:`ValueError` if the block is not part of the bytecode.

      .. versionadded:: 0.3

   .. method:: split_block(block: BasicBlock, index: int) -> BasicBlock

      Split a block into two blocks at the specific instruction. Return
      the newly created block, or *block* if index equals ``0``.

   .. method:: get_dead_blocks() -> List[BasicBlock]

      Retrieve all the blocks of the CFG that are unreachable.

   .. method:: to_bytecode() -> Bytecode

      Convert to a bytecode object using labels.

   .. method:: compute_stacksize(*, check_pre_and_post: bool = True, compute_exception_stack_depths: bool = True) -> int

      Compute the stack size required by a bytecode object. Will raise an
      exception if the bytecode is invalid.

      *check_pre_and_post* Allows caller to disable checking for stack underflow

      *compute_exception_stack_depths* Allows caller to disable the computation of
      the stack depth required by exception table entries.

      NOTE:

      The computation will only consider block that can be reached from the entry block.
      In particular, stack size for TryBegin/TryEnd in dead blocks is not updated.

      In some cases, stack usage may be slightly overestimated compared to CPython.
      This occurs when CPython duplicated the code for a finally clause but computed
      stack size before the duplication in which case one could infer a smaller stack
      usage for a TryBegin/TryEnd pair than can be done with the final bytecode
      form.

   .. method:: update_flags(is_async: bool = None)

      Update the object flags by calling :py:func:infer_flags on itself.

   .. method:: to_code(stacksize: int = None, *, check_pre_and_post: bool = True, compute_exception_stack_depths: bool = True)

      Convert to a Python code object.  Refer to descriptions of
      :meth:`Bytecode.to_code` and :meth:`ConcreteBytecode.to_code`.

      *check_pre_and_post* Allows caller to disable checking for stack underflow

      *compute_exception_stack_depths* Allows caller to disable the computation of
      the stack depth required by exception table entries.


Line Numbers
============

The line number can set directly on an instruction using the ``lineno``
parameter of the constructor. Otherwise, the line number if inherited from the
previous instruction, starting at ``first_lineno`` of the bytecode.

:class:`SetLineno` pseudo-instruction can be used to set the line number of
following instructions.

Starting with Python 3.11, instructions now have a starting lineno, and end lineno
along with a starting column offset and an end column offset. :class:`InstrLocation`
is used to store these new detailed information.


Compiler Flags
==============

.. class:: CompilerFlags()

    .. attribute:: OPTIMIZED

        Set if a code object only uses fast locals

    .. attribute:: NEWLOCALS

        Set if the code execution should be done with a new local scope

    .. attribute:: VARARGS

        Set if a code object expects variable number of positional arguments

    .. attribute:: VARKEYWORDS

        Set if a code object expects variable number of keyword arguments

    .. attribute:: NESTED

        Set if a code object correspond to function defined in another function

    .. attribute:: GENERATOR

        Set if a code object is a generator (contains yield instructions)

    .. attribute:: NOFREE

        Set if a code object does not use free variables

    .. attribute:: COROUTINE

        Set if a code object is a coroutine. New in Python 3.5

    .. attribute:: ITERABLE_COROUTINE

        Set if a code object is an iterable coroutine. New in Python 3.5

    .. attribute:: ASYNC_GENERATOR

        Set if a code object is an asynchronous generator. New in Python 3.6

    .. attribute:: FUTURE_GENERATOR_STOP

        Set if a code object is defined in a context in which generator_stop
        has been imported from \_\_future\_\_


.. function:: infer_flags(bytecode, async: bool = None) -> CompilerFlags

    Infer the correct values for the compiler flags for a given bytecode based
    on the instructions. The flags that can be inferred are :

    - OPTIMIZED
    - GENERATOR
    - NOFREE
    - COROUTINE
    - ASYNC_GENERATOR

    Force the code to be marked as asynchronous if True, prevent it from
    being marked as asynchronous if False and simply infer the best
    solution based on the opcode and the existing flag if None.

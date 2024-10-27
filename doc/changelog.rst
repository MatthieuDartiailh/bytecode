ChangeLog
=========

2024-05-28: Version 0.15.3
--------------------------

Bugfixes:

- Ensure the correct management of TryBegin blocks in CFGs. PR #1xx

2024-05-28: Version 0.15.2
--------------------------

Bugfixes:

- Ensure that empty or small (one-instruction) try blocks are handled without
  problems when compiling and de-compiling abstract code for CPython 3.11 and
  later. PR #145

2023-10-13: Version 0.15.1
--------------------------

Bugfixes:

- Disallow creating an instruction targeting a pseudo/instrumented opcode PR #133
- Fixes encoding of 0 as a varint PR #132
- Correct spelling of "INTRINSIC" in several places; this affected
  some ops in Python 3.12.  PR #131

2023-09-01: Version 0.15.0
--------------------------

New features:

- Add support for Python 3.12 PR #122

  Support for Python 3.12, comes with a number of changes reflecting changes in
  CPython bytecode itself:

  - handle the ability of ``LOAD_ATTR`` to replace ``LOAD_METHOD``
    As a consequence the argument is now a ``tuple[bool, str]``
  - similarly ``LOAD_SUPER_ATTR`` which uses the 2 lowest bits as flag takes
    a ``tuple[bool, bool, str]`` as argument
  - ``POP_JUMP_IF_*`` instructions are undirected in Python 3.12
  - ``YIELD_VALUE`` now takes an argument
  - Support for ``CALL_INTRINSIC_1/2`` led to the addition of 2 new enums to
    represent the argument

2023-05-24: Version 0.14.2
--------------------------

Bugfixes:

- allow to convert a CFG, for which stack sizes have not been computed, to Bytecode
  even in the presence of mergeable TryBegin/TryEnd  PR #120
- remove spurious TryEnd leftover when going from CFG to Bytecode  PR #120


2023-04-04: Version 0.14.1
--------------------------

Bugfixes:

- allow to disassemble code containing ``EXTENDED_ARG`` targeting a ``NOP`` PR #117


2022-11-30: Version 0.14.0
--------------------------

New features:

- Removed the peephole optimizer  PR #107

  Basically changes in Python 3.11 made it hard to port and the maintenance cost
  exceeded the perceived use. It could be re-added if there is a demand for it.

- Add support for Python 3.11 PR #107

  Support for Python 3.11, comes with a number of changes reflecting changes in
  CPython bytecode itself:

  - support for the exception table in ``ConcreteBytecode``
  - support for pseudo-instruction ``TryBegin`` and ``TryEnd`` describing the
    exception table in ``Bytecode`` and ``ControlflowGraph``
  - new keyword arguments in conversion method related to computations required
    for the exception table
  - handling of CACHE opcode at the ``ConcreteBytecode`` level
  - handling of the ability of ``LOAD_GLOBAL`` to push NULL (the argument is
    now a ``tuple[bool, str]``)
  - support for end_lineno and column offsets in instructions
  - support for ``co_qualname`` (as ``qualname`` on bytecode objects)

  and a number of internal changes related to changes in the internal bytecode
  representation.

- Add type annotations and make types stricter PR # 105
  In particular, ConcreteInstr does not inherit from Instr anymore and one
  cannot use ConcreteInstr in Bytecode object. This is saner than before.

Bugfixes:

- Removed ``EXC_MATCH`` from the ``Compare`` enumeration starting with Python
  3.9. The new ``JUMP_IF_NOT_EXC_MATCH`` opcode should be used instead.

- Removed ``IN``, ``NOT_IN``, ``IS``, ``NOT_IS`` from the ``Compare``
  enumeration starting with Python 3.9. The new ``CONTAINS_OP`` and ``IS_OP``
  opcodes should be used instead.

- Add proper pre and post stack effects to all opcodes (up to Python 3.11)
  PR #106 #107

Maintenance:

- Make the install process PEP517 compliant PR #97
- Drop support for Python 3.6 and 3.7 PR #100


2021-10-04: Version 0.13.0
--------------------------

New features:

- Add support for Python 3.10 new encoding of line number. This support is
  minimal in the sense that we still systematically assign a line number
  while the new format allow bytecode with absolutely no line number. PR #72


Bugfixes:

- Fix handling of RERAISE (introduced in 3.9) when creating a ControlFlowGraph,
  previously it was not considered final. PR #72

- Fix line table assembly in Python 3.10. PR #85


2021-02-02: Version 0.12.0
--------------------------

New features:

- All calculations of stacksize now check for stack underflow to avoid segfault at
  runtime PR #69

Bugfixes:

- Fix recursion limitations when compiling bytecode with numerous basic
  blocks. PR #57
- Fix handling of line offsets. Issue #67, PR #71

API changes:

- Forbid an :class:`Instr` to hold an EXTENDED_ARG op_code PR #65
- Forbid the use of :class:`ConcreteInstr` in :class:`Bytecode` and
  :class:`ControlFlowGraph` PR #65
  This is motivated by the extra complexity that handling possible EXTENDED_ARG
  instruction in those representation would bring (stack computation, etc)
- Always remove EXTENDED_ARG when converting :class:`ConcreteBytecode` to
  :class:`Bytecode` PR #65
  This is equivalent to say that the :class:`ConcreteBytecode` converted to
  :class:`Bytecode` was generated by :meth:`ConcreteBytecode.from_code`
  with extended_args=False
- :class:`Instr` now has a new method :meth:`Instr.pre_and_post_stack_effect`
  for checking the prerequisite stack size of an operation PR #69
- :meth:`_compute_stack_size` now uses :meth:`Instr.pre_and_post_stack_effect`
  to compute the stack size to reject code that will lead to runtime segfault
  caused by stack underflow PR #69


2020-03-02: Version 0.11.0
--------------------------

New features:

- The :func:`infer_flags` can now be used to forcibly mark a function as
  asynchronous or not.

Bugfixes:

- Fix a design flaw in the flag inference mechanism that could very easily
  lead to invalid flags configuration PR #56


2020-02-02: Version 0.10.0
--------------------------

New features:

- Slices and copy of :class:`Bytecode`, :class:`ConcreteBytecode` and
  :class:`BasicBlock` are now  of the same type as the original container. PR #52
- :class:`Bytecode`, :class:`ConcreteBytecode`, :class:`BasicBlock` and
  :class:`ControlFlowGraph` have a new :meth:`legalize` method validating
  their content and removing SetLineno. PR #52
- Modify the implementation of :code:`const_key` to avoid manual
  synchronizations with :code:`_PyCode_ConstantKey` in CPython codebase and
  allow the use of arbitrary Python objects as constants of nested code
  objects. #54

API changes:

- Add :class:`Compare` enum to public API. PR #53


2019-12-01: Version 0.9.0
-------------------------

New features:

- Add support for released version of Python 3.8 and update documentation.


2019-02-18: Version 0.8.0
-------------------------

New features:

- Add support for Python 3.7 PR #29
- Add preliminary support for Python 3.8-dev PR #41
- Allow to use any Python object as constants to enable aggressive
  optimizations PR #34

API changes:

- `stack_effect` is now a method of :class:`Instr` and not as property anymore. PR #29

Bugfixes:

- Avoid throwing `OverflowError` when applying `stack_effect` on valid :class:`Instr`
  objects. PR #43, PR #44


2018-04-15: Version 0.7.0
-------------------------

New features:

- Add `compute_jumps_passes` optional argument to :meth:`Bytecode.to_code` and
  to :meth:`Bytecode.to_concrete_bytecode` to control the number of passes
  performed to compute jump targets. In theory the required number is only
  bounded by the size of the code, but usually the algorithm converges quickly
  (< 10 iterations).

Bugfixes:

- proper handling of `EXTENDED_ARG` without arguments PR #28:

  `EXTENDED_ARG` are once again removed but their presence is recorded to avoid
  having issues with offsets in jumps. Similarly when round tripping code
  through :class:`ConcreteBytecode` the `EXTENDED_ARG` without args are
  preserved while if going through :class:`Bytecode` they are removed.


2018-03-24: Version 0.6
-----------------------

* Add stack depth computation based on control flow graph analysis
* Add higher level flags handling using IntFlags enum and inference function
* Add an instructions argument to ConcreteBytecode, and validate its value
* Do not delete `EXTENDED_ARG` instructions that have no arg


2017-01-05: Version 0.5
-----------------------

* Add the new bytecode format of Python 3.6.
* Remove the ``BaseInstr`` class which became useless. It was replaced
  with the :class:`Instr` class.
* Documentation: Add a comparison with byteplay and codetransformer.
* Remove the BaseIntr class: Instr becomes the new base class.
* Fix PEP 8 issues and check PEP 8 on Travis CI.


2016-04-12: Version 0.4
-----------------------

Peephole optimizer:

* Reenable optimization on ``JUMP_IF_TRUE_OR_POP`` jumping to
  ``POP_JUMP_IF_FALSE <target>``.


2016-03-02: Version 0.3
-----------------------

New features:

- Add :meth:`ControlFlowGraph.get_block_index` method

API changes:

- Rename ``Block`` class to :class:`BasicBlock`
- Rename ``BytecodeBlocks`` class to :class:`ControlFlowGraph`
- Rename ``BaseInstr.op`` to :attr:`BaseInstr.opcode`
- Rename ``BaseBytecode.kw_only_argcount`` attribute to
  :attr:`BaseBytecode.kwonlyargcount`, name closer to the Python code object
  attribute (``co_kwonlyargcount``)
- :class:`Instr` constructor and its :meth:`~BaseInstr.set` method now
  validates the argument type
- Add :class:`Compare` enum, used for ``COMPARE_OP`` argument of :class:`Instr`
- Remove *lineno* parameter from the :meth:`BaseInstr.set` method
- Add :class:`CellVar` and :class:`FreeVar` classes: instructions having
  a cell or free variable now require a :class:`CellVar` or :class:`FreeVar`
  instance rather than a simple string (``str``). This change is required
  to handle correctly code with duplicated variable names in cell and free
  variables.
- :class:`ControlFlowGraph`: remove undocumented ``to_concrete_bytecode()``
  and ``to_code()`` methods

Bugfixes:

- Fix support of :class:`SetLineno`

Peephole optimizer:

- Better code for LOAD_CONST x n + BUILD_LIST + UNPACK_SEQUENCE: rewrite
  LOAD_CONST in the reverse order instead of using ROT_TWO and ROT_THREE.
  This optimization supports more than 3 items.
- Remove JUMP_ABSOLUTE pointing to the following code. It can occur
  after dead code was removed.
- Remove NOP instructions
- Bugfix: catch IndexError when trying to get the next instruction.


2016-02-29: Version 0.2
-----------------------

- Again, the API is deeply reworked.
- The project has now a documentation:
  `bytecode documentation <https://bytecode.readthedocs.io/>`_
- Fix bug #1: support jumps larger than 2^16.
- Add a new bytecode.peephole_opt module: a peephole
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


2016-02-26: Version 0.1
-----------------------

- Rewrite completely the API!


2016-02-23: Release 0.0
-----------------------

- First public release

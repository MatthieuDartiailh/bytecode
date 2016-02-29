************
Bytecode API
************

bytecode module version string: ``bytecode.__version__`` (ex: ``'0.1'``).

.. data:: UNSET

   Singleton used to mark the lack of value. It is different than ``None``.


Instructions
============

Instr
-----

.. class:: Instr(name, arg=UNSET, \*, lineno=None)

   Abstract instruction.

   The type of the :attr:`arg` attribute depends on the operation.

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

   Static method:

   .. staticmethod:: disassemble(code: bytes, offset: int)

      Create an instruction from a bytecode string.

   Methods:

   .. method:: copy()

      Create a copy of the instruction.


ConcreteInstr
-------------

.. class:: ConcreteInstr(name, arg=UNSET, \*, lineno=None)

   Concrete instruction, inherit from :class:`Instr`.

   If the operation has an argument, *arg* must be an integer.

   Attributes:

   .. attribute:: arg

      Argument value (``int`` in range ``0``..``2147483647``), or :data:`UNSET`.

   .. attribute:: size

      Size of the instruction in bytes: between ``1`` (no agument) and
      ``6`` (extended argument).

   Static method:

   .. staticmethod:: disassemble(code: bytes, offset: int)

      Create an instruction from a bytecode string.

   Methods:

   .. method:: copy()

      Create a copy of the instruction.


Label
-----

.. class:: Label

   Pseudo-instruction. Targets of jump instructions for :class:`Bytecode`.

   Labels must not be used in :class:`ConcreteBytecode`.


SetLineno
---------

.. class:: SetLineno(lineno: int)

   Pseudo-instruction to set the line number of following instructions.


Bytecode classes
================

Bytecode
--------

.. class:: Bytecode

   Abstract bytecode: list of abstract instructions (:class:`Instr`).

   It is possible to use concrete instructions (:class:`ConcreteInstr`), but
   abstract instructions are preferred.

   Static methods:

   .. staticmethod:: from_code()

      Create an abstract bytecode from a Python code object.

   Methods:

   .. method:: to_code()

      Convert to a Python code object (:class:`types.CodeType`).

   .. method:: to_concrete_bytecode()

      Convert to concrete bytecode with concrete instructions. Resolve jumps.


ConcreteBytecode
----------------

.. class:: ConcreteBytecode

   List of concrete instructions (:class:`ConcreteInstr`).

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


BytecodeBlocks
--------------

.. class:: BytecodeBlocks

   List of blocks, a block is a list of abstract instructions (:class:`Instr`)
   and has a label (:class:`Label`).

   It is possible to use concrete instructions (:class:`ConcreteInstr`) in
   blocks, but abstract instructions are preferred.

   Labels must not be used in blocks.

   Static methods:

   .. staticmethod:: from_bytecode(bytecode)

      Create a :class:`Bytecode` object to a :class:`BytecodeBlocks` object:
      replace labels with blocks.


Line Numbers
============

The line number can set directly on an instruction using the ``lineno``
parameter of the constructor. Otherwise, the line number if inherited from the
previous instruction, starting at ``first_lineno`` of the bytecode.

:class:`SetLineno` pseudo-instruction can be used to set the line number of
following instructions.

++++++++++++++++++++++++++++++++++++++++++++
Comparison with byteplay and codetransformer
++++++++++++++++++++++++++++++++++++++++++++

History of the bytecode API design
==================================

The design of the bytecode module started with a single use case: reimplement
the CPython peephole optimizer (implemented in C) in pure Python. The design of
the API required many iterations to get the current API.

bytecode now has a clear separation between concrete instructions using integer
arguments and abstract instructions which use Python objects for arguments.
Jump targets are labels or basic blocks. And the control flow graph abstraction
is now an API well separated from the regular abstract bytecode which is a
simple list of instructions.


byteplay and codetransformer
============================

The `byteplay <https://github.com/serprex/byteplay>`_ and `codetransformer
<https://pypi.python.org/pypi/codetransformer>`_ are clear inspiration for the
design of the bytecode API. Sadly, byteplay and codetransformer API have design
issues (at least for my specific use cases).


Free and cell variables
-----------------------

Converting a code object to bytecode and then back to code must no modify the
code object. It is an important requirement.

The LOAD_DEREF instruction supports free variables and cell variables. byteplay
and codetransformer use a simple string for the variable name. When the
bytecode is converted to a code object, they check if the variable is a free
variable, or fallback to a cell variable.

The CPython code base contains a corner case: code having a free variable and a
cell variable with the same name. The heuristic produces invalid code which
can lead to a crash.

bytecode uses :class:`FreeVar` and :class:`CellVar` classes to tag the type of
the variable. Trying to use a simple string raise a :exc:`TypeError` in the
:class:`Instr` constructor.

.. note::
   It's possible to fix this issue in byteplay and codetransformer, maybe even
   with keeping support for simple string for free/cell variables for backward
   compatibility.


Line numbers
------------

codetransformer uses internally a dictionary mapping offsets to line numbers.
It is updated when the ``.steal()`` method is used.

byteplay uses a pseudo-instruction ``SetLineno`` to set the current line number
of the following instructions. It requires to handle these pseudo-instructions
when you modify the bytecode, especially when instructions are moved.

In FAT Python, some optimizations move instructions but their line numbers must
be kept. That's also why Python 3.6 was modified to support negative line
number delta in ``code.co_lntotab``.

bytecode has a different design: line numbers are stored directly inside
instructions (:attr:`Instr.lineno` attribute). Moving an instruction keeps
the line number information by design.

bytecode also supports the pseudo-instruction :class:`SetLineno`. It was added
to simplify functions emitting bytecode. It's not used when an existing code
object is converted to bytecode.


Jump targets
------------

In codetransformer, a jump target is an instruction. Jump targets are computed
when the bytecode is converted to a code object.

byteplay and bytecode use labels. Jump targets are computed when the abstract
bytecode is converted to a code object.

.. note::
   A loop is need in the conversion from bytecode to code: if the jump target
   is larger than 2**16, the size of the jump instruction changes (from 3 to 6
   bytes). So other jump targets must be recomputed.

   bytecode handles this corner case. byteplay and codetransformer don't, but
   it should be easy to fix them.


Control flow graph
------------------

The peephole optimizer has strong requirements on the control flow: an
optimization must not modify two instructions which are part of two different
basic blocks. Otherwise, the optimizer produces invalid code.

bytecode provides a control flow graph API for this use case.

byteplay and codetransformer don't.


Functions or methods
--------------------

This point is a matter of taste.

In bytecode, instructions are objects with methods like
:meth:`~Instr.is_final`, :meth:`~Instr.has_cond_jump`, etc.

The byteplay project uses functions taking an instruction as parameter.

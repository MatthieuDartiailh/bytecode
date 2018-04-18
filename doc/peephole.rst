.. _peephole_opt:

******************
Peephole Optimizer
******************

Peephole optimizer: optimize Python code objects. It is implemented with the
:class:`BytecodeBlocks` class.

It is based on the peephole optimizer of CPython 3.6 which is written in C.


API
===

Content of the ``bytecode.peephole_opt`` module:

.. class:: PeepholeOptimizer

   .. method:: optimize(code: types.CodeType) -> types.CodeType

      Optimize a Python code object.

      Return a new optimized Python code object.

      Note:  This method will disassemble code to a ConcreteBytecode, then a
      Bytecode, then a ControlFlowGraph.  Then the CFG is optimized.  And then
      the optimized CFG is converted back to a Bytecode, ConcreteBytecode, and
      then code.  Depending on what you are doing you may get better
      performance by calling :meth:`optimize_cfg`.

   .. method:: optimize_cfg(cfg: ControlFlowGraph)

      Optimizes an existing ControlFlowGraph.  The specified CFG is modified
      in-place.

.. class:: CodeTransformer

   Code transformer for the API of the `PEP 511
   <https://www.python.org/dev/peps/pep-0511/>`_ (API for code transformers).

   .. method:: code_transformer(code, context)

      Run the :class:`PeepholeOptimizer` optimizer on the code.

      Return a new optimized Python code object.


Example
=======

Code::

    import dis
    from bytecode.peephole_opt import PeepholeOptimizer

    code = compile('print(5+5)', '<string>', 'exec')
    print("Non-optimized:")
    dis.dis(code)
    print()

    code = PeepholeOptimizer().optimize(code)
    print("Optimized:")
    dis.dis(code)

Output of Python 3.6 patched with the PEP 511 with ``python -o noopt`` (to
disable the builtin peephole optimizer)::

    Non-optimized:
      1           0 LOAD_NAME                0 (print)
                  3 LOAD_CONST               0 (5)
                  6 LOAD_CONST               0 (5)
                  9 BINARY_ADD
                 10 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
                 13 POP_TOP
                 14 LOAD_CONST               1 (None)
                 17 RETURN_VALUE

    Optimized:
      1           0 LOAD_NAME                0 (print)
                  3 LOAD_CONST               0 (10)
                  6 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
                  9 POP_TOP
                 10 LOAD_CONST               1 (None)
                 13 RETURN_VALUE


Optimizations
=============

Optimizations implemented in the peephole optimizer:

* Constant folding

  - unary operations: +a, -a, ~a
  - binary operations:

    * a + b, a - b, a * b, a / b, a // b, a % b, a ** b
    * a << b, a >> b, a & b, a | b, a ^ b

  - BUILD_TUPLE: convert to a constant
  - Replace BUILD_TUPLE <n> + UNPACK_SEQUENCE <n> and BUILD_LIST <n>
    + UNPACK_SEQUENCE <n> with ROT_TWO (2 arguments) or ROT_THREE+ROT_TWO (3
    arguments). For BUILD_LIST, if inputs are LOAD_CONST, rewrite LOAD_CONST in
    the reverse order.
  - BUILD_LIST + COMPARE_OP(in/not in): convert list to tuple
  - BUILD_SET + COMPARE_OP(in/not in): convert set to frozenset
  - COMPARE_OP:

    * replace ``not(a is b)`` with ``a is not b``
    * replace ``not(a is not b)`` with ``a is b``
    * replace ``not(a in b)`` with ``a not in b``
    * replace ``not(a not in b)`` with ``a in b``

* Remove NOP instructions
* Dead code elimination

  - Remove unreachable code after a final operation (:meth:`Instr.is_final`)
  - Remove unreachable blocks (:class:`Block`)

* Replace UNARY_NOT+POP_JUMP_IF_FALSE with POP_JUMP_IF_TRUE

* Optimize jumps

  - Replace unconditional jumps to RETURN_VALUE with RETURN_VALUE
  - Replace jumps to unconditional jumps with jumps to the final target
  - Remove unconditional jumps to the following block

For tuples, constant folding is only run if the result has 20 items or less.

By design, only basic optimizations can be implemented. A peephole optimizer
has a narrow view on the bytecode (a few instructions) and only a very limited
knownledge of the code.

.. note::
   ``3 < 5`` or ``(1, 2, 3)[1]`` are not optimized.

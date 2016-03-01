* CPython: Python/compile.c, add assertion to deny negative argument?
* ConcreteBytecode.to_code(): compute the stack level, see byteplay
  and Python/compile.c?
* ConcreteBytecode.to_code(): better error reporting on bugs in the code
* Bytecode: rename kw_only_argcount to kwonlyargcount?
* Document or expose CO_xxx flags
* COMPARE_OP argument: use an enum?
* peephole: optimize build_tuple_unpack_seq(), rewrite LOAD_CONST in the
  reverse order
* peephole: optimize_jump_to_cond_jump(), relative jump offset and negative
  jump

* CPython: Python/compile.c, add assertion to deny negative argument?
* ConcreteBytecode.to_code(): compute the stack level, see byteplay
  and Python/compile.c?
* ConcreteBytecode.to_code(): better error reporting on bugs in the code
* Bytecode: rename kw_only_argcount to kwonlyargcount?
* Document or expose CO_xxx flags
* COMPARE_OP argument: use an enum?
* peephole: optimize_jump_to_cond_jump(), relative jump offset and negative
  jump
* peephole: reorder instructions to reduce the usage of the stack. Replace:
      Instr('LOAD_NAME', 'b')
      Instr('LOAD_NAME', 'a')
      Instr('STORE_NAME', 'x')
      Instr('STORE_NAME', 'y')
  with:
      Instr('LOAD_NAME', 'a')
        Instr('STORE_NAME', 'x')
      Instr('LOAD_NAME', 'b')
        Instr('STORE_NAME', 'y')


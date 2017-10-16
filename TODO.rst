* Convert peephole_opt code to a more generic CFG optimizer?
  For example, extract code to remove unreachable blocks?
* ConcreteBytecode.to_code(): better error reporting on bugs in the code

Peephole
========

* Optimize_jump_to_cond_jump(), relative jump offset and negative
  jump
* Reorder instructions to reduce the usage of the stack. Replace:
      Instr('LOAD_NAME', 'b')
      Instr('LOAD_NAME', 'a')
      Instr('STORE_NAME', 'x')
      Instr('STORE_NAME', 'y')
  with:
      Instr('LOAD_NAME', 'a')
        Instr('STORE_NAME', 'x')
      Instr('LOAD_NAME', 'b')
        Instr('STORE_NAME', 'y')

* Don't set local varibles?
              9 STORE_FAST               1 (v)
             12 LOAD_FAST                1 (v)
             15 LOAD_ATTR                0 (phrase)
             18 LOAD_FAST                1 (v)
=>
    DUP_TOP
    LOAD_ATTR 0 (phrase)
    ROT_TWO


Fix Python compiler? Duplicated END_FINALLY
===========================================


def func():
    try:
        return data.encode("latin-1")
    except UnicodeEncodeError as err:
        print("err")


  4     >>   16 DUP_TOP
             17 LOAD_GLOBAL              2 (UnicodeEncodeError)
             20 COMPARE_OP              10 (exception match)
             23 POP_JUMP_IF_FALSE       62
             ...
             31 SETUP_FINALLY           15 (to 49)
             ...
             58 END_FINALLY
             59 JUMP_FORWARD             1 (to 63)
        >>   62 END_FINALLY
        >>   63 LOAD_CONST               0 (None)
             66 RETURN_VALUE


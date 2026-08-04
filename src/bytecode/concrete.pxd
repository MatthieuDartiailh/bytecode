from bytecode.instr cimport BaseInstr

cdef class ConcreteInstr(BaseInstr):
    cdef public object _extended_args
    cdef public int _size

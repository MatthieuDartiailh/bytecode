cdef class InstrLocation:
    cdef public object lineno
    cdef public object end_lineno
    cdef public object col_offset
    cdef public object end_col_offset

cdef class BaseInstr:
    cdef public str _name
    cdef public object _location
    cdef public int _opcode
    cdef public object _arg

cdef class Instr(BaseInstr):
    pass

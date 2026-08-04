cdef class InstrLocation:
    # Must be `object` (not `int`) because these fields are Optional[int] and can be None.
    cdef readonly object lineno
    cdef readonly object end_lineno
    cdef readonly object col_offset
    cdef readonly object end_col_offset

cdef class BaseInstr:
    cdef public str _name
    cdef public object _location
    cdef public int _opcode
    cdef public object _arg

cdef class Instr(BaseInstr):
    pass

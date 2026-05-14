cdef class InstrLocation:
    # Must be `object` (not `int`) because these fields are Optional[int] and can be None.
    # `public` (not `readonly`) is required because _from_tuple/__init__ assign via an
    # untyped `new` variable; Cython routes those through the Python descriptor, which
    # would raise for `readonly`.  Immutability is enforced only in pure-Python mode by
    # @dataclass(frozen=True).
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

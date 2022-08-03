import dis
import inspect
import opcode as _opcode
import struct
import sys
import types
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    MutableSequence,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

# alias to keep the 'bytecode' variable free
import bytecode as _bytecode
from bytecode.flags import CompilerFlags
from bytecode.instr import (
    UNSET,
    BaseInstr,
    CellVar,
    Compare,
    FreeVar,
    Instr,
    InstrArg,
    Label,
    SetLineno,
    _check_arg_int,
    const_key,
)

# - jumps use instruction
# - lineno use bytes (dis.findlinestarts(code))
# - dis displays bytes
OFFSET_AS_INSTRUCTION = sys.version_info >= (3, 10)


def _set_docstring(code: _bytecode.BaseBytecode, consts: Sequence) -> None:
    if not consts:
        return
    first_const = consts[0]
    if isinstance(first_const, str) or first_const is None:
        code.docstring = first_const


T = TypeVar("T", bound="ConcreteInstr")


class ConcreteInstr(BaseInstr[int]):
    """Concrete instruction.

    arg must be an integer in the range 0..2147483647.

    It has a read-only size attribute.

    """

    # For ConcreteInstr the argument is always an integer
    _arg: int

    __slots__ = ("_size", "_extended_args")

    def __init__(
        self,
        name: str,
        arg: int = UNSET,
        *,
        lineno: Optional[int] = None,
        extended_args: Optional[int] = None,
    ):
        # Allow to remember a potentially meaningless EXTENDED_ARG emitted by
        # Python to properly compute the size and avoid messing up the jump
        # targets
        self._extended_args = extended_args
        self._set(name, arg, lineno)

    def _check_arg(self, name: str, opcode: int, arg: int) -> None:
        if opcode >= _opcode.HAVE_ARGUMENT:
            if arg is UNSET:
                raise ValueError("operation %s requires an argument" % name)

            _check_arg_int(arg, name)
        else:
            if arg is not UNSET:
                raise ValueError("operation %s has no argument" % name)

    def _set(self, name: str, arg: int, lineno: Optional[int]) -> None:
        super()._set(name, arg, lineno)
        size = 2
        if arg is not UNSET:
            while arg > 0xFF:
                size += 2
                arg >>= 8
        if self._extended_args is not None:
            size = 2 + 2 * self._extended_args
        self._size = size

    @property
    def size(self) -> int:
        return self._size

    def _cmp_key(self) -> Tuple[Optional[int], str, int]:
        return (self._lineno, self._name, self._arg)

    def get_jump_target(self, instr_offset: int) -> Optional[int]:
        if self._opcode in _opcode.hasjrel:
            s = (self._size // 2) if OFFSET_AS_INSTRUCTION else self._size
            return instr_offset + s + self._arg
        if self._opcode in _opcode.hasjabs:
            return self._arg
        return None

    def assemble(self) -> bytes:
        if self._arg is UNSET:
            return bytes((self._opcode, 0))

        arg = self._arg
        b = [self._opcode, arg & 0xFF]
        while arg > 0xFF:
            arg >>= 8
            b[:0] = [_opcode.EXTENDED_ARG, arg & 0xFF]

        if self._extended_args:
            while len(b) < self._size:
                b[:0] = [_opcode.EXTENDED_ARG, 0x00]

        return bytes(b)

    @classmethod
    def disassemble(cls: Type[T], lineno: Optional[int], code: bytes, offset: int) -> T:
        index = 2 * offset if OFFSET_AS_INSTRUCTION else offset
        op = code[index]
        if op >= _opcode.HAVE_ARGUMENT:
            arg = code[index + 1]
        else:
            arg = UNSET
        name = _opcode.opname[op]
        return cls(name, arg, lineno=lineno)


class ExceptionTableEntry(NamedTuple):
    """Entry for a given line in the exception table.

    All offset are expressed in instructions not in bytes.

    """

    #: Offset in instruction between the beginning of the bytecode and the beginning
    #: of this entry.
    start_offset: int

    #: Offset in instruction between the beginning of the bytecode and the end
    #: of this entry. This offset is inclusive meaning that the instruction it points
    #: to is included in the try/except handling.
    stop_offset: int

    #: Offset in instruction to the first instruction of the exception handling block.
    target: int

    #: Stack depth when enter the block delineated by start and stop offset of the
    #: exception table entry.
    stack_depth: int

    #: Should the offset, at which an exception was raised, be pushed on the stack
    #: before the exception itself (which is pushed as (traceback, value, type)).
    push_lasti: bool


class ConcreteBytecode(_bytecode._BaseBytecodeList[Union[ConcreteInstr, SetLineno]]):

    #: Table describing portion of the bytecode in which exception are caught and
    #: where there are handled.
    #: Used only in Python 3.11+
    exception_table: List[ExceptionTableEntry]
    
    def __init__(
        self,
        instructions=(),
        *,
        consts: tuple = (),
        names: Tuple[str, ...] = (),
        varnames=(),
        exception_table=None,
    ):
        super().__init__()
        self.consts = list(consts)
        self.names = list(names)
        self.varnames = list(varnames)
        self.exception_table = exception_table or []
        for instr in instructions:
            self._check_instr(instr)
        self.extend(instructions)

    def __iter__(self) -> Iterator[Union[ConcreteInstr, SetLineno]]:
        instructions = super().__iter__()
        for instr in instructions:
            self._check_instr(instr)
            yield instr

    def _check_instr(self, instr: Any) -> None:
        if not isinstance(instr, (ConcreteInstr, SetLineno)):
            raise ValueError(
                "ConcreteBytecode must only contain "
                "ConcreteInstr and SetLineno objects, "
                "but %s was found" % type(instr).__name__
            )

    def _copy_attr_from(self, bytecode):
        super()._copy_attr_from(bytecode)
        if isinstance(bytecode, ConcreteBytecode):
            self.consts = bytecode.consts
            self.names = bytecode.names
            self.varnames = bytecode.varnames

    def __repr__(self) -> str:
        return "<ConcreteBytecode instr#=%s>" % len(self)

    def __eq__(self, other: Any) -> bool:
        if type(self) != type(other):
            return False

        const_keys1 = list(map(const_key, self.consts))
        const_keys2 = list(map(const_key, other.consts))
        if const_keys1 != const_keys2:
            return False

        if self.names != other.names:
            return False
        if self.varnames != other.varnames:
            return False

        return super().__eq__(other)

    @staticmethod
    def from_code(
        code: types.CodeType, *, extended_arg: bool = False
    ) -> "ConcreteBytecode":
        line_starts = dict(dis.findlinestarts(code))

        # find block starts
        instructions: MutableSequence[Union[SetLineno, ConcreteInstr]] = []
        offset = 0
        lineno = code.co_firstlineno
        while offset < (len(code.co_code) // (2 if OFFSET_AS_INSTRUCTION else 1)):
            lineno_off = (2 * offset) if OFFSET_AS_INSTRUCTION else offset
            if lineno_off in line_starts:
                lineno = line_starts[lineno_off]

            instr = ConcreteInstr.disassemble(lineno, code.co_code, offset)

            instructions.append(instr)
            offset += (instr.size // 2) if OFFSET_AS_INSTRUCTION else instr.size

        bytecode = ConcreteBytecode()

        # replace jump targets with blocks
        # HINT : in some cases Python generate useless EXTENDED_ARG opcode
        # with a value of zero. Such opcodes do not increases the size of the
        # following opcode the way a normal EXTENDED_ARG does. As a
        # consequence, they need to be tracked manually as otherwise the
        # offsets in jump targets can end up being wrong.
        if not extended_arg:
            # The list is modified in place
            bytecode._remove_extended_args(instructions)

        bytecode.name = code.co_name
        bytecode.filename = code.co_filename
        bytecode.flags = CompilerFlags(code.co_flags)
        bytecode.argcount = code.co_argcount
        bytecode.posonlyargcount = code.co_posonlyargcount
        bytecode.kwonlyargcount = code.co_kwonlyargcount
        bytecode.first_lineno = code.co_firstlineno
        bytecode.names = list(code.co_names)
        bytecode.consts = list(code.co_consts)
        bytecode.varnames = list(code.co_varnames)
        bytecode.freevars = list(code.co_freevars)
        bytecode.cellvars = list(code.co_cellvars)
        _set_docstring(bytecode, code.co_consts)
        if sys.version_info >= (3, 11):
            bytecode.exception_table = bytecode._parse_exception_table(
                code.co_exceptiontable
            )

        bytecode[:] = instructions
        return bytecode

    @staticmethod
    def _normalize_lineno(
        instructions: Sequence[Union[ConcreteInstr, SetLineno]], first_lineno: int
    ) -> Iterator[Tuple[int, ConcreteInstr]]:
        lineno = first_lineno
        for instr in instructions:
            # if instr.lineno is not set, it's inherited from the previous
            # instruction, or from self.first_lineno
            if instr.lineno is not None:
                lineno = instr.lineno

            if isinstance(instr, ConcreteInstr):
                yield (lineno, instr)

    def _assemble_code(self) -> Tuple[bytes, List[Tuple[int, int, int]]]:
        offset = 0
        code_str = []
        linenos = []
        for lineno, instr in self._normalize_lineno(self, self.first_lineno):
            code_str.append(instr.assemble())
            i_size = instr.size
            linenos.append(
                ((offset * 2) if OFFSET_AS_INSTRUCTION else offset, i_size, lineno)
            )
            offset += (i_size // 2) if OFFSET_AS_INSTRUCTION else i_size

        return (b"".join(code_str), linenos)

    @staticmethod
    def _assemble_lnotab(
        first_lineno: int, linenos: List[Tuple[int, int, int]]
    ) -> bytes:
        lnotab = []
        old_offset = 0
        old_lineno = first_lineno
        for offset, _, lineno in linenos:
            dlineno = lineno - old_lineno
            if dlineno == 0:
                continue
            old_lineno = lineno

            doff = offset - old_offset
            old_offset = offset

            while doff > 255:
                lnotab.append(b"\xff\x00")
                doff -= 255

            while dlineno < -128:
                lnotab.append(struct.pack("Bb", doff, -128))
                doff = 0
                dlineno -= -128

            while dlineno > 127:
                lnotab.append(struct.pack("Bb", doff, 127))
                doff = 0
                dlineno -= 127

            assert 0 <= doff <= 255
            assert -128 <= dlineno <= 127

            lnotab.append(struct.pack("Bb", doff, dlineno))

        return b"".join(lnotab)

    @staticmethod
    def _pack_linetable(linetable: List[bytes], doff: int, dlineno: int) -> None:
        # Ensure linenos are between -126 and +126, by using 127 lines jumps with
        # a 0 byte offset
        while dlineno < -127:
            linetable.append(struct.pack("Bb", 0, -127))
            dlineno -= -127

        while dlineno > 127:
            linetable.append(struct.pack("Bb", 0, 127))
            dlineno -= 127

        # Ensure offsets are less than 255.
        # If an offset is larger, we first mark the line change with an offset of 254
        # then use as many 254 offset with no line change to reduce the offset to
        # less than 254.
        if doff > 254:

            linetable.append(struct.pack("Bb", 254, dlineno))
            doff -= 254

            while doff > 254:
                linetable.append(b"\xfe\x00")
                doff -= 254
            linetable.append(struct.pack("Bb", doff, 0))

        else:
            linetable.append(struct.pack("Bb", doff, dlineno))

        assert 0 <= doff <= 254
        assert -127 <= dlineno <= 127

    def _assemble_linestable(
        self, first_lineno: int, linenos: Iterable[Tuple[int, int, int]]
    ) -> bytes:
        if not linenos:
            return b""

        linetable: List[bytes] = []
        old_offset = 0

        iter_in = iter(linenos)

        offset, i_size, old_lineno = next(iter_in)
        old_dlineno = old_lineno - first_lineno
        for offset, i_size, lineno in iter_in:
            dlineno = lineno - old_lineno
            if dlineno == 0:
                continue
            old_lineno = lineno

            doff = offset - old_offset
            old_offset = offset

            self._pack_linetable(linetable, doff, old_dlineno)
            old_dlineno = dlineno

        # Pack the line of the last instruction.
        doff = offset + i_size - old_offset
        self._pack_linetable(linetable, doff, old_dlineno)

        return b"".join(linetable)

    @staticmethod
    def _remove_extended_args(
        instructions: MutableSequence[Union[SetLineno, ConcreteInstr]]
    ) -> None:
        # replace jump targets with blocks
        # HINT : in some cases Python generate useless EXTENDED_ARG opcode
        # with a value of zero. Such opcodes do not increases the size of the
        # following opcode the way a normal EXTENDED_ARG does. As a
        # consequence, they need to be tracked manually as otherwise the
        # offsets in jump targets can end up being wrong.
        nb_extended_args = 0
        extended_arg = None
        index = 0
        while index < len(instructions):
            instr = instructions[index]

            # Skip SetLineno meta instruction
            if isinstance(instr, SetLineno):
                index += 1
                continue

            if instr.name == "EXTENDED_ARG":
                nb_extended_args += 1
                if extended_arg is not None:
                    extended_arg = (extended_arg << 8) + instr.arg
                else:
                    extended_arg = instr.arg

                del instructions[index]
                continue

            if extended_arg is not None:
                arg = (extended_arg << 8) + instr.arg
                extended_arg = None

                instr = ConcreteInstr(
                    instr.name,
                    arg,
                    lineno=instr.lineno,
                    extended_args=nb_extended_args,
                )
                instructions[index] = instr
                nb_extended_args = 0

            index += 1

        if extended_arg is not None:
            raise ValueError("EXTENDED_ARG at the end of the code")

    # Taken and adapted from exception_handling_notes.txt in cpython/Objects
    @staticmethod
    def _parse_varint(except_table_iterator: Iterator[int]) -> int:
        b = next(except_table_iterator)
        val = b & 63
        while b & 64:
            val <<= 6
            b = next(except_table_iterator)
            val |= b & 63
        return val

    def _parse_exception_table(
        self, exception_table: bytes
    ) -> List[ExceptionTableEntry]:
        assert sys.version_info >= (3, 11)
        table = []
        iterator = iter(exception_table)
        try:
            while True:
                start = self._parse_varint(iterator)
                length = self._parse_varint(iterator)
                end = start + length - 1  # Present as inclusive
                target = self._parse_varint(iterator)
                dl = self._parse_varint(iterator)
                depth = dl >> 1
                lasti = bool(dl & 1)
                table.append(ExceptionTableEntry(start, end, target, depth, lasti))
        except StopIteration:
            return table

    @staticmethod
    def _encode_varint(value: int, set_begin_marker: bool = False) -> Iterator[int]:
        # Encode value as a varint on 7 bits (MSB should come first) and set
        # the begin marker if requested.
        temp: List[int] = []
        while value:
            temp.append(value & 63 | (64 if temp else 0))
            value >>= 6
        if set_begin_marker:
            temp[-1] |= 128
        return reversed(temp or [0])

    def _assemble_exception_table(self) -> bytes:
        table = bytearray()
        for entry in self.exception_table or []:
            size = entry.stop_offset - entry.start_offset + 1
            depth = (entry.stack_depth << 1) + entry.push_lasti
            table.extend(self._encode_varint(entry.start_offset, True))
            table.extend(self._encode_varint(size))
            table.extend(self._encode_varint(entry.target))
            table.extend(self._encode_varint(depth))

        return bytes(table)

    def compute_stacksize(self, *, check_pre_and_post: bool = True) -> int:
        bytecode = self.to_bytecode()
        cfg = _bytecode.ControlFlowGraph.from_bytecode(bytecode)
        return cfg.compute_stacksize(check_pre_and_post=check_pre_and_post)

    def to_code(
        self, stacksize: Optional[int] = None, *, check_pre_and_post: bool = True
    ) -> types.CodeType:
        code_str, linenos = self._assemble_code()
        lnotab = (
            self._assemble_linestable(self.first_lineno, linenos)
            if sys.version_info >= (3, 10)
            else self._assemble_lnotab(self.first_lineno, linenos)
        )
        nlocals = len(self.varnames)
        if stacksize is None:
            stacksize = self.compute_stacksize(check_pre_and_post=check_pre_and_post)

        if sys.version_info >= (3, 11):
            return types.CodeType(
                self.argcount,
                self.posonlyargcount,
                self.kwonlyargcount,
                nlocals,
                stacksize,
                int(self.flags),
                code_str,
                tuple(self.consts),
                tuple(self.names),
                tuple(self.varnames),
                self.filename,
                self.name,
                "",  # XXX qualname
                self.first_lineno,
                lnotab,
                self._assemble_exception_table(),
                tuple(self.freevars),
                tuple(self.cellvars),
            )
        else:
            return types.CodeType(
                self.argcount,
                self.posonlyargcount,
                self.kwonlyargcount,
                nlocals,
                stacksize,
                int(self.flags),
                code_str,
                tuple(self.consts),
                tuple(self.names),
                tuple(self.varnames),
                self.filename,
                self.name,
                self.first_lineno,
                lnotab,
                tuple(self.freevars),
                tuple(self.cellvars),
            )

    def to_bytecode(self, prune_caches: bool = True) -> _bytecode.Bytecode:

        # Copy instruction and remove extended args if any (in-place)
        c_instructions = self[:]
        self._remove_extended_args(c_instructions)

        # find jump targets
        jump_targets = set()
        offset = 0
        for c_instr in c_instructions:
            if isinstance(c_instr, SetLineno):
                continue
            target = c_instr.get_jump_target(offset)
            if target is not None:
                jump_targets.add(target)
            offset += (c_instr.size // 2) if OFFSET_AS_INSTRUCTION else c_instr.size

        # create labels
        jumps = []
        instructions: List[Union[Instr, Label, SetLineno]] = []
        labels = {}
        offset = 0
        ncells = len(self.cellvars)

        for lineno, c_instr in self._normalize_lineno(
            c_instructions, self.first_lineno
        ):
            if offset in jump_targets:
                label = Label()
                labels[offset] = label
                instructions.append(label)

            jump_target = c_instr.get_jump_target(offset)
            size = c_instr.size
            offset += (size // 2) if OFFSET_AS_INSTRUCTION else size

            # on Python 3.11+ remove CACHE opcodes if we are requested to do so.
            # We are careful to first advance the offset and check that the CACHE
            # is not a jump target. It should never be the case but we double check.
            if prune_caches and c_instr.name == "CACHE":
                assert jump_target is None
                continue

            arg: InstrArg
            c_arg = c_instr.arg
            # FIXME: better error reporting
            if c_instr.opcode in _opcode.hasconst:
                arg = self.consts[c_arg]
            elif c_instr.opcode in _opcode.haslocal:
                arg = self.varnames[c_arg]
            elif c_instr.opcode in _opcode.hasname:
                if sys.version_info >= (3, 11) and c_instr.name == "LOAD_GLOBAL":
                    arg = (bool(c_arg & 1), self.names[c_arg >> 1])
                else:
                    arg = self.names[c_arg]
            elif c_instr.opcode in _opcode.hasfree:
                if c_arg < ncells:
                    name = self.cellvars[c_arg]
                    arg = CellVar(name)
                else:
                    name = self.freevars[c_arg - ncells]
                    arg = FreeVar(name)
            elif c_instr.opcode in _opcode.hascompare:
                arg = Compare(c_arg)
            else:
                arg = c_arg

            if jump_target is None:
                new_instr = Instr(c_instr.name, arg, lineno=lineno)
            else:
                instr_index = len(instructions)
                # This is a hack but going around it just for typing would be a pain
                new_instr = c_instr  # type: ignore
            instructions.append(new_instr)

            if jump_target is not None:
                jumps.append((instr_index, jump_target))

        # replace jump targets with labels
        for index, jump_target in jumps:
            instr = instructions[index]
            assert isinstance(instr, ConcreteInstr)
            # FIXME: better error reporting on missing label
            label = labels[jump_target]
            instructions[index] = Instr(instr.name, label, lineno=instr.lineno)

        bytecode = _bytecode.Bytecode()
        bytecode._copy_attr_from(self)

        nargs = bytecode.argcount + bytecode.kwonlyargcount
        nargs += bytecode.posonlyargcount
        if bytecode.flags & inspect.CO_VARARGS:
            nargs += 1
        if bytecode.flags & inspect.CO_VARKEYWORDS:
            nargs += 1
        bytecode.argnames = self.varnames[:nargs]
        _set_docstring(bytecode, self.consts)

        bytecode.extend(instructions)
        return bytecode


class _ConvertBytecodeToConcrete:

    # Default number of passes of compute_jumps() before giving up.  Refer to
    # assemble_jump_offsets() in compile.c for background.
    _compute_jumps_passes = 10

    def __init__(self, code: _bytecode.Bytecode) -> None:
        assert isinstance(code, _bytecode.Bytecode)
        self.bytecode = code

        # temporary variables
        self.instructions: List[ConcreteInstr] = []
        self.jumps: List[Tuple[int, Label, ConcreteInstr]] = []
        self.labels: Dict[Label, int] = {}
        self.required_caches = 0
        self.seen_manual_cache = False

        # used to build ConcreteBytecode() object
        self.consts_indices: Dict[Union[bytes, Tuple[type, int]], int] = {}
        self.consts_list: List[Any] = []
        self.names: List[str] = []
        self.varnames: List[str] = []

    def add_const(self, value: Any) -> int:
        key = const_key(value)
        if key in self.consts_indices:
            return self.consts_indices[key]
        index = len(self.consts_indices)
        self.consts_indices[key] = index
        self.consts_list.append(value)
        return index

    @staticmethod
    def add(names: List[str], name: str) -> int:
        try:
            index = names.index(name)
        except ValueError:
            index = len(names)
            names.append(name)
        return index

    def concrete_instructions(self) -> None:
        ncells = len(self.bytecode.cellvars)
        lineno = self.bytecode.first_lineno

        for instr in self.bytecode:

            if isinstance(instr, Label):
                self.labels[instr] = len(self.instructions)
                continue

            if isinstance(instr, SetLineno):
                lineno = instr.lineno
                continue

            # Enforce proper use of CACHE opcode on Python 3.11+ by checking we get the
            # number we expect or directly generate the needed ones.
            if instr.name == "CACHE":
                if not self.required_caches:
                    raise RuntimeError("Found a CACHE opcode when none was expected.")
                self.seen_manual_cache = True
                self.required_caches -= 1

            elif self.required_caches:
                if not self.seen_manual_cache:
                    self.instructions.extend(
                        [ConcreteInstr("CACHE") for i in range(self.required_caches)]
                    )
                    self.required_caches = 0
                    self.seen_manual_cache = False
                else:
                    raise RuntimeError(
                        "Found some manual opcode but less than expected. "
                        f"Missing {self.required_caches} CACHE opcodes."
                    )

            if isinstance(instr, ConcreteInstr):
                c_instr: ConcreteInstr = instr.copy()
            else:
                assert isinstance(instr, Instr)

                if instr.lineno is not None:
                    lineno = instr.lineno

                arg = instr.arg
                is_jump = False
                if isinstance(arg, Label):
                    label = arg
                    # fake value, real value is set in compute_jumps()
                    arg = 0
                    is_jump = True
                elif instr.opcode in _opcode.hasconst:
                    arg = self.add_const(arg)
                elif instr.opcode in _opcode.haslocal:
                    assert isinstance(arg, str)
                    arg = self.add(self.varnames, arg)
                elif instr.opcode in _opcode.hasname:
                    if sys.version_info >= (3, 11) and instr.name == "LOAD_GLOBAL":
                        assert (
                            isinstance(arg, tuple)
                            and len(arg) == 2
                            and isinstance(arg[0], bool)
                            and isinstance(arg[1], str)
                        )
                        index = self.add(self.names, arg[1])
                        arg = int(arg[0]) + (index << 1)
                    else:
                        assert isinstance(arg, str)
                        arg = self.add(self.names, arg)
                elif instr.opcode in _opcode.hasfree:
                    if isinstance(arg, CellVar):
                        arg = self.bytecode.cellvars.index(arg.name)
                    else:
                        assert isinstance(arg, FreeVar)
                        arg = ncells + self.bytecode.freevars.index(arg.name)
                elif instr.opcode in _opcode.hascompare:
                    if isinstance(arg, Compare):
                        arg = arg.value

                # The above should have performed all the necessary conversion
                assert isinstance(arg, int)
                c_instr = ConcreteInstr(instr.name, arg, lineno=lineno)
                if is_jump:
                    self.jumps.append((len(self.instructions), label, c_instr))

            # If the instruction expect some cache
            if sys.version_info >= (3, 11):
                self.required_caches = dis._inline_cache_entries[c_instr.opcode]
                self.seen_manual_cache = False

            self.instructions.append(c_instr)

    def compute_jumps(self) -> bool:
        offsets = []
        offset = 0
        for index, instr in enumerate(self.instructions):
            offsets.append(offset)
            offset += instr.size // 2 if OFFSET_AS_INSTRUCTION else instr.size
        # needed if a label is at the end
        offsets.append(offset)

        # fix argument of jump instructions: resolve labels
        modified = False
        for index, label, instr in self.jumps:
            target_index = self.labels[label]
            target_offset = offsets[target_index]

            if instr.opcode in _opcode.hasjrel:
                instr_offset = offsets[index]
                target_offset -= instr_offset + (
                    instr.size // 2 if OFFSET_AS_INSTRUCTION else instr.size
                )

            old_size = instr.size
            # FIXME: better error report if target_offset is negative
            instr.arg = target_offset
            if instr.size != old_size:
                modified = True

        return modified

    def to_concrete_bytecode(self, compute_jumps_passes=None) -> ConcreteBytecode:
        if compute_jumps_passes is None:
            compute_jumps_passes = self._compute_jumps_passes

        first_const = self.bytecode.docstring
        if first_const is not UNSET:
            self.add_const(first_const)

        self.varnames.extend(self.bytecode.argnames)

        self.concrete_instructions()
        for pas in range(0, compute_jumps_passes):
            modified = self.compute_jumps()
            if not modified:
                break
        else:
            raise RuntimeError(
                "compute_jumps() failed to converge after" " %d passes" % (pas + 1)
            )

        concrete = ConcreteBytecode(
            self.instructions,
            consts=tuple(self.consts_list),
            names=tuple(self.names),
            varnames=self.varnames,
        )
        concrete._copy_attr_from(self.bytecode)
        return concrete

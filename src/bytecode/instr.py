import dis
import enum
import opcode as _opcode
import sys
from abc import abstractmethod
from dataclasses import dataclass
from marshal import dumps as _dumps
from typing import Any, Generic, Optional, Tuple, TypeVar, Union

try:
    from typing import TypeGuard
except ImportError:
    from typing_extensions import TypeGuard  # type: ignore

import bytecode as _bytecode


@enum.unique
class Compare(enum.IntEnum):
    LT = 0
    LE = 1
    EQ = 2
    NE = 3
    GT = 4
    GE = 5
    if sys.version_info < (3, 9):
        IN = 6
        NOT_IN = 7
        IS = 8
        IS_NOT = 9
        EXC_MATCH = 10


# This make type checking happy but means it won't catch attempt to manipulate an unset
# statically. We would need guard on object attribute narrowed down through methods
class _UNSET(int):

    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __eq__(self, other) -> bool:
        return self is other


for op in [
    "__abs__",
    "__add__",
    "__and__",
    "__bool__",
    "__ceil__",
    "__divmod__",
    "__float__",
    "__floor__",
    "__floordiv__",
    "__ge__",
    "__gt__",
    "__hash__",
    "__index__",
    "__int__",
    "__invert__",
    "__le__",
    "__lshift__",
    "__lt__",
    "__mod__",
    "__mul__",
    "__ne__",
    "__neg__",
    "__or__",
    "__pos__",
    "__pow__",
    "__radd__",
    "__rand__",
    "__rdivmod__",
    "__rfloordiv__",
    "__rlshift__",
    "__rmod__",
    "__rmul__",
    "__ror__",
    "__round__",
    "__rpow__",
    "__rrshift__",
    "__rshift__",
    "__rsub__",
    "__rtruediv__",
    "__rxor__",
    "__sub__",
    "__truediv__",
    "__trunc__",
    "__xor__",
]:
    setattr(_UNSET, op, lambda *args: NotImplemented)


UNSET = _UNSET()


def const_key(obj: Any) -> Union[bytes, Tuple[type, int]]:
    try:
        return _dumps(obj)
    except ValueError:
        # For other types, we use the object identifier as an unique identifier
        # to ensure that they are seen as unequal.
        return (type(obj), id(obj))


def _pushes_back(opname: str) -> bool:
    if opname in ["CALL_FINALLY"]:
        # CALL_FINALLY pushes the address of the "finally" block instead of a
        # value, hence we don't treat it as pushing back op
        return False
    return (
        opname.startswith("UNARY_")
        or opname.startswith("GET_")
        # BUILD_XXX_UNPACK have been removed in 3.9
        or opname.startswith("BINARY_")
        or opname.startswith("INPLACE_")
        or opname.startswith("BUILD_")
        or opname.startswith("CALL_")
    ) or opname in (
        "LIST_TO_TUPLE",
        "LIST_EXTEND",
        "SET_UPDATE",
        "DICT_UPDATE",
        "DICT_MERGE",
        "COMPARE_OP",
        "IS_OP",
        "CONTAINS_OP",
        "FORMAT_VALUE",
        "MAKE_FUNCTION",
        "IMPORT_NAME",
        # technically, these three do not push back, but leave the container
        # object on TOS
        "SET_ADD",
        "LIST_APPEND",
        "MAP_ADD",
        "LOAD_ATTR",
    )


def _check_location(
    location: Optional[int], location_name: str, min_value: int
) -> None:
    if location is None:
        return
    if not isinstance(location, int):
        raise TypeError(f"{location_name} must be an int, got {type(location)}")
    if location < min_value:
        raise ValueError(
            f"invalid {location_name}, expected >= {min_value}, got {location}"
        )


class SetLineno:
    __slots__ = ("_lineno",)

    def __init__(self, lineno: int) -> None:
        _check_location(lineno, "lineno", 1)
        self._lineno: int = lineno

    @property
    def lineno(self) -> int:
        return self._lineno

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, SetLineno):
            return False
        return self._lineno == other._lineno


class Label:
    __slots__ = ()


class TryBegin:
    __slots__ = ("target", "push_lasti", "stack_depth")

    def __init__(
        self, target: Label, push_lasti: bool, stack_depth: Union[int, _UNSET] = UNSET
    ) -> None:
        self.target: Label = target
        self.push_lasti: bool = push_lasti
        self.stack_depth: Union[int, _UNSET] = stack_depth


class TryEnd:
    __slots__ = "entry"

    def __init__(self, entry: TryBegin) -> None:
        self.entry: TryBegin = entry


class _Variable:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name: str = name

    def __eq__(self, other: Any) -> bool:
        if type(self) != type(other):
            return False
        return self.name == other.name

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return "<%s %r>" % (self.__class__.__name__, self.name)


class CellVar(_Variable):
    __slots__ = ()


class FreeVar(_Variable):
    __slots__ = ()


def _check_arg_int(arg: Any, name: str) -> TypeGuard[int]:
    if not isinstance(arg, int):
        raise TypeError(
            "operation %s argument must be an int, "
            "got %s" % (name, type(arg).__name__)
        )

    if not (0 <= arg <= 2147483647):
        raise ValueError(
            "operation %s argument must be in " "the range 0..2,147,483,647" % name
        )

    return True


T = TypeVar("T", bound="BaseInstr")
A = TypeVar("A", bound=object)


@dataclass(frozen=True)
class InstrLocation:
    """Location information for an instruction."""

    #: Lineno at which the instruction corresponds
    lineno: Optional[int]

    #: End lineno at which the instruction corresponds (Python 3.11+ only)
    end_lineno: Optional[int]

    #: Column offset at which the instruction corresponds (Python 3.11+ only)
    col_offset: Optional[int]

    #: End column offset at which the instruction corresponds (Python 3.11+ only)
    end_col_offset: Optional[int]

    __slots__ = ["lineno", "end_lineno", "col_offset", "end_col_offset"]

    def __init__(
        self,
        lineno: Optional[int],
        end_lineno: Optional[int],
        col_offset: Optional[int],
        end_col_offset: Optional[int],
    ) -> None:
        # Needed because we want the class to be frozen
        object.__setattr__(self, "lineno", lineno)
        object.__setattr__(self, "end_lineno", end_lineno)
        object.__setattr__(self, "col_offset", col_offset)
        object.__setattr__(self, "end_col_offset", end_col_offset)
        _check_location(lineno, "lineno", 1)
        _check_location(end_lineno, "end_lineno", 1)
        _check_location(col_offset, "col_offset", 0)
        _check_location(end_col_offset, "end_col_offset", 0)
        if end_lineno:
            if lineno is None:
                raise ValueError("End lineno specified with no lineno.")
            elif lineno > end_lineno:
                raise ValueError(
                    f"End lineno {end_lineno} cannot be smaller than lineno {lineno}."
                )
        if end_col_offset:
            if col_offset is None:
                raise ValueError("End col offset specified with no col offset.")
            elif col_offset > end_col_offset:
                raise ValueError(
                    f"End col offset {end_col_offset} cannot be smaller than "
                    "col offset {col_offset}."
                )


class BaseInstr(Generic[A]):
    """Abstract instruction."""

    __slots__ = ("_name", "_opcode", "_arg", "_location")

    # Work around an issue with the default value of arg
    def __init__(
        self,
        name: str,
        arg: A = UNSET,  # type: ignore
        *,
        lineno: Union[int, None, _UNSET] = UNSET,
        location: Optional[InstrLocation] = None,
    ) -> None:
        self._set(name, arg)
        if location:
            self._location = location
        elif lineno is UNSET:
            self._location = None
        else:
            self._location = InstrLocation(lineno, None, None, None)

    # Work around an issue with the default value of arg
    def set(self, name: str, arg: A = UNSET) -> None:  # type: ignore
        """Modify the instruction in-place.

        Replace name and arg attributes. Don't modify lineno.

        """
        self._set(name, arg)

    def require_arg(self) -> bool:
        """Does the instruction require an argument?"""
        return self._opcode >= _opcode.HAVE_ARGUMENT

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._set(name, self._arg)

    @property
    def opcode(self) -> int:
        return self._opcode

    @opcode.setter
    def opcode(self, op: int) -> None:
        if not isinstance(op, int):
            raise TypeError("operator code must be an int")
        if 0 <= op <= 255:
            name = _opcode.opname[op]
            valid = name != "<%r>" % op
        else:
            valid = False
        if not valid:
            raise ValueError("invalid operator code")

        self._set(name, self._arg)

    @property
    def arg(self) -> A:
        return self._arg

    @arg.setter
    def arg(self, arg: A):
        self._set(self._name, arg)

    @property
    def lineno(self) -> Union[int, _UNSET, None]:
        return self._location.lineno if self._location is not None else UNSET

    @lineno.setter
    def lineno(self, lineno: Union[int, _UNSET, None]) -> None:
        loc = self._location
        if loc and (
            loc.end_lineno is not None
            or loc.col_offset is not None
            or loc.end_col_offset is not None
        ):
            raise RuntimeError(
                "The lineno of an instruction with detailed location information "
                "cannot be set."
            )

        if lineno is UNSET:
            self._location = None
        else:
            self._location = InstrLocation(lineno, None, None, None)

    @property
    def location(self) -> Optional[InstrLocation]:
        return self._location

    @location.setter
    def location(self, location: Optional[InstrLocation]) -> None:
        if location and not isinstance(location, InstrLocation):
            raise TypeError(
                "The instr location must be an instance of InstrLocation or None."
            )
        self._location = location

    def stack_effect(self, jump: Optional[bool] = None) -> int:
        if self._opcode < _opcode.HAVE_ARGUMENT:
            arg = None
        elif not isinstance(self._arg, int) or self._opcode in _opcode.hasconst:
            # Argument is either a non-integer or an integer constant,
            # not oparg.
            arg = 0
        else:
            arg = self._arg

        return dis.stack_effect(self._opcode, arg, jump=jump)

    def pre_and_post_stack_effect(self, jump: Optional[bool] = None) -> Tuple[int, int]:
        _effect = self.stack_effect(jump=jump)

        # To compute pre size and post size to avoid segfault cause by not enough
        # stack element
        _opname = _opcode.opname[self._opcode]
        # Handles DUP_TOP and DUP_TOP_TWO
        if _opname.startswith("DUP_TOP"):
            return _effect * -1, _effect * 2
        if _pushes_back(_opname):
            # if the op pushes a value back to the stack, then the stack effect
            # given by dis.stack_effect actually equals pre + post effect,
            # therefore we need -1 from the stack effect as a pre condition.
            return _effect - 1, 1
        if _opname == "COPY_DICT_WITHOUT_KEYS":  # New in 3.10
            # Replace TOS based on TOS and TOS1
            return -2, 2
        if _opname == "WITH_EXCEPT_START":
            # Call a function at position 7 on the stack and push the return value
            return -7, 8
        if _opname == "MATCH_CLASS":
            # Starting with Python 3.11 MATCH_CLASS does not push a boolean anymore
            return -3, 1 if sys.version_info >= (3, 11) else 2
        if _opname.startswith("MATCH_"):  # New in 3.10
            # Match opcodes (MATCH_MAPPING, MATCH_SEQUENCE, MATCH_KEYS) use as
            # many values as pre condition as they will push on the stack
            return -_effect, 2 * _effect
        if _opname.startswith("UNPACK_"):
            # Instr(UNPACK_* , n) pops 1 and pushes n
            # _effect = n - 1
            # hence we return -1, _effect + 1
            return -1, _effect + 1
        if _opname == "FOR_ITER" and not jump:
            # Since FOR_ITER needs TOS to be an iterator, which basically means
            # a prerequisite of 1 on the stack
            return -1, 2
        if _opname == "IMPORT_FROM":  # New in 3.10
            # Replace TOS based on TOS and TOS1
            return -1, 2
        if _opname == "BEFORE_ASYNC_WITH":
            # Pop TOS and push TOS.__aexit__ and result of TOS.__aenter__()
            return -1, 2
        if _opname == "ROT_N":
            arg = self._arg
            assert isinstance(arg, int)
            return (-arg, arg)
        return {"ROT_TWO": (-2, 2), "ROT_THREE": (-3, 3), "ROT_FOUR": (-4, 4)}.get(
            _opname, (_effect, 0)
        )

    def copy(self: T) -> T:
        return self.__class__(self._name, self._arg, location=self._location)

    def has_jump(self) -> bool:
        return self._has_jump(self._opcode)

    def is_cond_jump(self) -> bool:
        """Is a conditional jump?"""
        # Ex: POP_JUMP_IF_TRUE, JUMP_IF_FALSE_OR_POP
        # IN 3.11+ the JUMP and the IF are no necessary adjacent in the name.
        name = self._name
        return "JUMP_" in name and "IF_" in name

    def is_uncond_jump(self) -> bool:
        """Is an unconditional jump?"""
        # JUMP_BACKWARD has been introduced in 3.11+
        # JUMP_ABSOLUTE was removed in 3.11+
        return self.name in {"JUMP_FORWARD", "JUMP_ABSOLUTE", "JUMP_BACKWARD"}

    def is_final(self) -> bool:
        if self._name in {
            "RETURN_VALUE",
            "RAISE_VARARGS",
            "RERAISE",
            "BREAK_LOOP",
            "CONTINUE_LOOP",
        }:
            return True
        if self.is_uncond_jump():
            return True
        return False

    def __repr__(self) -> str:
        if self._arg is not UNSET:
            return "<%s arg=%r location=%s>" % (self._name, self._arg, self._location)
        else:
            return "<%s location=%s>" % (self._name, self._location)

    def __eq__(self, other: Any) -> bool:
        if type(self) != type(other):
            return False
        return self._cmp_key() == other._cmp_key()

    # --- Private API

    _name: str

    _location: Optional[InstrLocation]

    _opcode: int

    _arg: A

    def _set(self, name: str, arg: A) -> None:
        if not isinstance(name, str):
            raise TypeError("operation name must be a str")
        try:
            opcode = _opcode.opmap[name]
        except KeyError:
            raise ValueError("invalid operation name")

        self._check_arg(name, opcode, arg)

        self._name = name
        self._opcode = opcode
        self._arg = arg

    @staticmethod
    def _has_jump(opcode) -> bool:
        return opcode in _opcode.hasjrel or opcode in _opcode.hasjabs

    @abstractmethod
    def _check_arg(self, name: str, opcode: int, arg: A) -> None:
        pass

    @abstractmethod
    def _cmp_key(self) -> Tuple[Optional[InstrLocation], str, Any]:
        pass


InstrArg = Union[
    int, str, Label, CellVar, FreeVar, "_bytecode.BasicBlock", Compare, Tuple[bool, str]
]


class Instr(BaseInstr[InstrArg]):

    __slots__ = ()

    def _cmp_key(self) -> Tuple[Optional[InstrLocation], str, Any]:
        arg: Any = self._arg
        if self._opcode in _opcode.hasconst:
            arg = const_key(arg)
        return (self._location, self._name, arg)

    def _check_arg(self, name: str, opcode: int, arg: InstrArg) -> None:
        if name == "EXTENDED_ARG":
            raise ValueError(
                "only concrete instruction can contain EXTENDED_ARG, "
                "highlevel instruction can represent arbitrary argument without it"
            )

        if opcode >= _opcode.HAVE_ARGUMENT:
            if arg is UNSET:
                raise ValueError("operation %s requires an argument" % name)
        else:
            if arg is not UNSET:
                raise ValueError("operation %s has no argument" % name)

        if self._has_jump(opcode):
            if not isinstance(arg, (Label, _bytecode.BasicBlock)):
                raise TypeError(
                    "operation %s argument type must be "
                    "Label or BasicBlock, got %s" % (name, type(arg).__name__)
                )

        elif opcode in _opcode.hasfree:
            if not isinstance(arg, (CellVar, FreeVar)):
                raise TypeError(
                    "operation %s argument must be CellVar "
                    "or FreeVar, got %s" % (name, type(arg).__name__)
                )

        elif opcode in _opcode.haslocal or opcode in _opcode.hasname:
            if sys.version_info >= (3, 11) and name == "LOAD_GLOBAL":
                if not (
                    isinstance(arg, tuple)
                    and len(arg) == 2
                    and isinstance(arg[0], bool)
                    and isinstance(arg[1], str)
                ):
                    raise TypeError(
                        "operation %s argument must be a tuple[bool, str], "
                        "got %s (value=%s)" % (name, type(arg).__name__, str(arg))
                    )

            elif not isinstance(arg, str):
                raise TypeError(
                    "operation %s argument must be a str, "
                    "got %s" % (name, type(arg).__name__)
                )

        elif opcode in _opcode.hasconst:
            if isinstance(arg, Label):
                raise ValueError(
                    "label argument cannot be used " "in %s operation" % name
                )
            if isinstance(arg, _bytecode.BasicBlock):
                raise ValueError(
                    "block argument cannot be used " "in %s operation" % name
                )

        elif opcode in _opcode.hascompare:
            if not isinstance(arg, Compare):
                raise TypeError(
                    "operation %s argument type must be "
                    "Compare, got %s" % (name, type(arg).__name__)
                )

        elif opcode >= _opcode.HAVE_ARGUMENT:
            _check_arg_int(arg, name)
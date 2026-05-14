"""Type stubs for instr.py.

Cython cdef classes cannot inherit from Generic[], so this stub restores the
generic type-checking behaviour for BaseInstr[A] and Instr.
"""

import enum
import types
from typing import Any, Final, Generic, Optional, TypeGuard, TypeVar, Union

import bytecode as _bytecode

# ── type variables ────────────────────────────────────────────────────────────

A = TypeVar("A", bound=object)
T = TypeVar("T", bound="BaseInstr[Any]")

# ── opcode sets / constants ───────────────────────────────────────────────────

MIN_INSTRUMENTED_OPCODE: Final[int]
BITFLAG_OPCODES: Final[set[int]]
BITFLAG2_OPCODES: Final[set[int]]
BINARY_OPS: Final[set[int]]
INTRINSIC_1OP: Final[set[int]]
INTRINSIC_2OP: Final[set[int]]
INTRINSIC: Final[set[int]]
COMMON_CONSTANT_OPS: Final[set[int]]
FORMAT_VALUE_OPS: Final[set[int]]
SMALL_INT_OPS: Final[set[int]]
SPECIAL_OPS: Final[set[int]]
HAS_ABSOLUTE_JUMP: Final[set[int]]
HAS_FORWARD_RELATIVE_JUMP: Final[set[int]]
HAS_BACKWARD_RELATIVE_JUMP: Final[set[int]]
HAS_JUMP: Final[set[int]]
HAS_CONDITIONAL_JUMP: Final[set[int]]
HAS_UNCONDITIONAL_JUMP: Final[set[int]]
IS_INSTR_FINAL: Final[set[int]]
DUAL_ARG_OPCODES: Final[set[int]]
DUAL_ARG_OPCODES_SINGLE_OPS: Final[dict[int, tuple[str, str]]]
EXTENDEDARG_OPCODE: Final[int]
NOP_OPCODE: Final[int]
CACHE_OPCODE: Final[int]
RESUME_OPCODE: Final[int]
STATIC_STACK_EFFECTS: Final[dict[int, tuple[int, int]]]
DYNAMIC_STACK_EFFECTS: Final[dict[int, Any]]

# ── enums ─────────────────────────────────────────────────────────────────────

class Compare(enum.IntEnum):
    LT = 0
    LE = 1
    EQ = 2
    NE = 3
    GT = 4
    GE = 5
    LT_CAST = 16
    LE_CAST = 17
    EQ_CAST = 18
    NE_CAST = 19
    GT_CAST = 20
    GE_CAST = 21

class BinaryOp(enum.IntEnum): ...
class Intrinsic1Op(enum.IntEnum): ...
class Intrinsic2Op(enum.IntEnum): ...
class FormatValue(enum.IntEnum): ...
class SpecialMethod(enum.IntEnum): ...
class CommonConstant(enum.IntEnum): ...

# ── sentinel ──────────────────────────────────────────────────────────────────

class _UNSET(int): ...

UNSET: _UNSET

# ── helpers ───────────────────────────────────────────────────────────────────

def const_key(obj: Any) -> bytes | tuple[type, int]: ...
def _check_arg_int(arg: Any, name: str) -> TypeGuard[int]: ...
def opcode_has_argument(opcode: int) -> bool: ...

# ── label / variable types ────────────────────────────────────────────────────

class Label: ...

PLACEHOLDER_LABEL: Label

class _Variable:
    name: str
    def __init__(self, name: str) -> None: ...
    def __eq__(self, other: Any) -> bool: ...
    def __ne__(self, other: Any) -> bool: ...
    def __repr__(self) -> str: ...

class CellVar(_Variable): ...
class FreeVar(_Variable): ...

# ── InstrLocation ─────────────────────────────────────────────────────────────

class InstrLocation:
    lineno: Optional[int]
    end_lineno: Optional[int]
    col_offset: Optional[int]
    end_col_offset: Optional[int]
    def __init__(
        self,
        lineno: Optional[int],
        end_lineno: Optional[int],
        col_offset: Optional[int],
        end_col_offset: Optional[int],
    ) -> None: ...
    @classmethod
    def from_positions(cls, position: Any) -> InstrLocation: ...
    @classmethod
    def _from_tuple(
        cls,
        lineno: Optional[int],
        end_lineno: Optional[int],
        col_offset: Optional[int],
        end_col_offset: Optional[int],
    ) -> InstrLocation: ...

# ── pseudo-instructions ───────────────────────────────────────────────────────

class SetLineno:
    def __init__(self, lineno: int) -> None: ...
    @property
    def lineno(self) -> int: ...
    def __eq__(self, other: Any) -> bool: ...

class TryBegin:
    target: Label | _bytecode.BasicBlock
    push_lasti: bool
    stack_depth: int | _UNSET
    def __init__(
        self,
        target: Label | _bytecode.BasicBlock,
        push_lasti: bool,
        stack_depth: int | _UNSET = ...,
    ) -> None: ...
    def copy(self) -> TryBegin: ...

class TryEnd:
    entry: TryBegin
    def __init__(self, entry: TryBegin) -> None: ...
    def copy(self) -> TryEnd: ...

# ── InstrArg ──────────────────────────────────────────────────────────────────

InstrArg = Union[
    int,
    str,
    Label,
    CellVar,
    FreeVar,
    _bytecode.BasicBlock,
    Compare,
    FormatValue,
    BinaryOp,
    Intrinsic1Op,
    Intrinsic2Op,
    CommonConstant,
    SpecialMethod,
    tuple[bool, str],
    tuple[bool, bool, str],
    tuple[bool, FormatValue],
    tuple[str | CellVar | FreeVar, str | CellVar | FreeVar],
]

# ── BaseInstr / Instr ─────────────────────────────────────────────────────────

class BaseInstr(Generic[A]):
    def __init__(
        self,
        name: str,
        arg: A = ...,
        *,
        lineno: int | None | _UNSET = ...,
        location: Optional[InstrLocation] = None,
    ) -> None: ...
    def __class_getitem__(cls, item: Any) -> types.GenericAlias: ...
    def set(self, name: str, arg: A = ...) -> None: ...
    def require_arg(self) -> bool: ...
    @property
    def name(self) -> str: ...
    @name.setter
    def name(self, name: str) -> None: ...
    @property
    def opcode(self) -> int: ...
    @opcode.setter
    def opcode(self, op: int) -> None: ...
    @property
    def arg(self) -> A: ...
    @arg.setter
    def arg(self, arg: A) -> None: ...
    @property
    def lineno(self) -> int | _UNSET | None: ...
    @lineno.setter
    def lineno(self, lineno: int | _UNSET | None) -> None: ...
    @property
    def location(self) -> Optional[InstrLocation]: ...
    @location.setter
    def location(self, location: Optional[InstrLocation]) -> None: ...
    def stack_effect(self, jump: Optional[bool] = None) -> int: ...
    def pre_and_post_stack_effect(
        self, jump: Optional[bool] = None
    ) -> tuple[int, int]: ...
    def copy(self: T) -> T: ...
    @classmethod
    def _from_trusted(
        cls: type[T],
        name: str,
        opcode: int,
        arg: A,
        location: Optional[InstrLocation],
    ) -> T: ...
    def has_jump(self) -> bool: ...
    def is_cond_jump(self) -> bool: ...
    def is_uncond_jump(self) -> bool: ...
    def is_abs_jump(self) -> bool: ...
    def is_forward_rel_jump(self) -> bool: ...
    def is_backward_rel_jump(self) -> bool: ...
    def is_final(self) -> bool: ...

class Instr(BaseInstr[InstrArg]): ...

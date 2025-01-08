import opcode
import sys
from enum import IntFlag
from typing import Optional, Union

# alias to keep the 'bytecode' variable free
import bytecode as _bytecode


class CompilerFlags(IntFlag):
    """Possible values of the co_flags attribute of Code object.

    Note: We do not rely on inspect values here as some of them are missing and
    furthermore would be version dependent.

    """

    OPTIMIZED = 0x00001
    NEWLOCALS = 0x00002
    VARARGS = 0x00004
    VARKEYWORDS = 0x00008
    NESTED = 0x00010
    GENERATOR = 0x00020
    NOFREE = 0x00040
    # New in Python 3.5
    # Used for coroutines defined using async def ie native coroutine
    COROUTINE = 0x00080
    # Used for coroutines defined as a generator and then decorated using
    # types.coroutine
    ITERABLE_COROUTINE = 0x00100
    # New in Python 3.6
    # Generator defined in an async def function
    ASYNC_GENERATOR = 0x00200

    # __future__ flags
    # future flags changed in Python 3.9
    if sys.version_info < (3, 9):
        FUTURE_GENERATOR_STOP = 0x80000
        FUTURE_ANNOTATIONS = 0x100000
    else:
        FUTURE_GENERATOR_STOP = 0x800000
        FUTURE_ANNOTATIONS = 0x1000000


def ignored_instruction(i) -> bool:
    return isinstance(
        i,
        (
            _bytecode.SetLineno,
            _bytecode.Label,
            _bytecode.TryBegin,
            _bytecode.TryEnd,
        ),
    )


def is_generator(instructions) -> bool:
    # Look for a YIELD_VALUE that is not for an await
    found_yield = False
    for i in instructions:
        if ignored_instruction(i):
            continue
        if found_yield:
            if i.name == "RESUME" and i.arg & 3 == 3:
                found_yield = False  # yield was for an await
                continue
            break
        if i.name == "YIELD_VALUE":
            found_yield = True
    return found_yield


def infer_flags(
    bytecode: Union[
        "_bytecode.Bytecode", "_bytecode.ConcreteBytecode", "_bytecode.ControlFlowGraph"
    ],
    is_async: Optional[bool] = None,
):
    """Infer the proper flags for a bytecode based on the instructions.

    Because the bytecode does not have enough context to guess if a function
    is asynchronous the algorithm tries to be conservative and will never turn
    a previously async code into a sync one.

    Parameters
    ----------
    bytecode : Bytecode | ConcreteBytecode | ControlFlowGraph
        Bytecode for which to infer the proper flags
    is_async : bool | None, optional
        Force the code to be marked as asynchronous if True, prevent it from
        being marked as asynchronous if False and simply infer the best
        solution based on the opcode and the existing flag if None.

    """
    flags = CompilerFlags(0)
    if not isinstance(
        bytecode,
        (_bytecode.Bytecode, _bytecode.ConcreteBytecode, _bytecode.ControlFlowGraph),
    ):
        msg = (
            "Expected a Bytecode, ConcreteBytecode or ControlFlowGraph "
            "instance not %s"
        )
        raise ValueError(msg % bytecode)

    instructions = (
        bytecode._get_instructions()
        if isinstance(bytecode, _bytecode.ControlFlowGraph)
        else bytecode
    )
    instr_names = {i.name for i in instructions if not ignored_instruction(i)}

    # Identify optimized code
    if not (instr_names & {"STORE_NAME", "LOAD_NAME", "DELETE_NAME"}):
        flags |= CompilerFlags.OPTIMIZED

    # Check for free variables
    if not (instr_names & {opcode.opname[i] for i in opcode.hasfree}):
        flags |= CompilerFlags.NOFREE

    # Copy flags for which we cannot infer the right value
    flags |= bytecode.flags & (
        CompilerFlags.NEWLOCALS
        | CompilerFlags.VARARGS
        | CompilerFlags.VARKEYWORDS
        | CompilerFlags.NESTED
    )

    maybe_generator = instr_names & {"YIELD_VALUE", "YIELD_FROM", "RETURN_GENERATOR"}

    sure_async = instr_names & {
        "GET_AWAITABLE",
        "GET_AITER",
        "GET_ANEXT",
        "BEFORE_ASYNC_WITH",
        "SETUP_ASYNC_WITH",
        "END_ASYNC_FOR",
        "ASYNC_GEN_WRAP",  # New in 3.11
    }

    # If performing inference or forcing an async behavior, first inspect
    # the flags since this is the only way to identify iterable coroutines
    if is_async in (None, True):
        sure_generator = is_generator(instructions)
        if bytecode.flags & CompilerFlags.COROUTINE:
            if sure_generator:
                flags |= CompilerFlags.ASYNC_GENERATOR
            else:
                flags |= CompilerFlags.COROUTINE
        elif bytecode.flags & CompilerFlags.ITERABLE_COROUTINE:
            if sure_async:
                msg = (
                    "The ITERABLE_COROUTINE flag is set but bytecode that"
                    "can only be used in async functions have been "
                    "detected. Please unset that flag before performing "
                    "inference."
                )
                raise ValueError(msg)
            flags |= CompilerFlags.ITERABLE_COROUTINE
        elif bytecode.flags & CompilerFlags.ASYNC_GENERATOR:
            if not sure_generator:
                flags |= CompilerFlags.COROUTINE
            else:
                flags |= CompilerFlags.ASYNC_GENERATOR

        # If the code was not asynchronous before determine if it should now be
        # asynchronous based on the opcode and the is_async argument.
        else:
            if sure_async:
                # YIELD_FROM is not allowed in async generator
                if sure_generator:
                    flags |= CompilerFlags.ASYNC_GENERATOR
                else:
                    flags |= CompilerFlags.COROUTINE

            elif maybe_generator:
                if is_async:
                    if sure_generator:
                        flags |= CompilerFlags.ASYNC_GENERATOR
                    else:
                        flags |= CompilerFlags.COROUTINE
                else:
                    flags |= CompilerFlags.GENERATOR

            elif is_async:
                flags |= CompilerFlags.COROUTINE

    # If the code should not be asynchronous, check first it is possible and
    # next set the GENERATOR flag if relevant
    else:
        if sure_async:
            raise ValueError(
                "The is_async argument is False but bytecodes "
                "that can only be used in async functions have "
                "been detected."
            )

        if maybe_generator:
            flags |= CompilerFlags.GENERATOR

    flags |= bytecode.flags & CompilerFlags.FUTURE_GENERATOR_STOP

    return flags

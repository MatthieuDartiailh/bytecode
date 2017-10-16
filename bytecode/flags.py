# alias to keep the 'bytecode' variable free
import bytecode as _bytecode
from aenum import IntFlag


class CompilerFlags(IntFlag):
    """Possible values of the co_flags attribute of Code object.

    Note: We do not rely on inspect values here as some of them are missing and
    furthermore would be version dependent.

    """
    OPTIMIZED             = 0x00001  # noqa
    NEWLOCALS             = 0x00002  # noqa
    VARARGS               = 0x00004  # noqa
    VARKEYWORDS           = 0x00008  # noqa
    NESTED                = 0x00010  # noqa
    GENERATOR             = 0x00020  # noqa
    NOFREE                = 0x00040  # noqa
    # New in Python 3.5
    COROUTINE             = 0x00080  # noqa
    ITERABLE_COROUTINE    = 0x00100  # noqa
    # New in Python 3.6
    ASYNC_GENERATOR       = 0x00200  # noqa

    # __future__ flags
    FUTURE_GENERATOR_STOP = 0x80000  # noqa


def infer_flags(bytecode, is_async=False):
    """Infer the proper flags for a bytecode based on the instructions.

    """
    flags = CompilerFlags(0)
    if not isinstance(bytecode, (_bytecode.Bytecode,
                                 _bytecode.ConcreteBytecode,
                                 _bytecode.ControlFlowGraph)):
        msg = ('Expected a Bytecode, ConcreteBytecode or ControlFlowGraph '
               'instance not %s')
        raise ValueError(msg % bytecode)

    instructions = (bytecode.get_instructions()
                    if isinstance(bytecode, _bytecode.ControlFlowGraph) else
                    bytecode)
    instr_names = {i.name for i in instructions
                   if not isinstance(i, (_bytecode.SetLineno,
                                         _bytecode.Label))}

    if not (instr_names & {'STORE_NAME', 'LOAD_NAME', 'DELETE_NAME'}):
        flags |= CompilerFlags.OPTIMIZED

    flags |= bytecode.flags & (CompilerFlags.NEWLOCALS |
                               CompilerFlags.VARARGS |
                               CompilerFlags.VARKEYWORDS |
                               CompilerFlags.NESTED)

    if instr_names & {'YIELD_VALUE', 'YIELD_FROM'}:
        if not is_async and not bytecode.flags & CompilerFlags.ASYNC_GENERATOR:
            flags |= CompilerFlags.GENERATOR
        else:
            flags |= CompilerFlags.ASYNC_GENERATOR

    if not (instr_names & {'LOAD_CLOSURE', 'LOAD_DEREF', 'STORE_DEREF',
                           'DELETE_DEREF', 'LOAD_CLASSDEREF'}):
        flags |= CompilerFlags.NOFREE

    if (not (bytecode.flags & CompilerFlags.ITERABLE_COROUTINE or
             flags & CompilerFlags.ASYNC_GENERATOR) and
            (instr_names & {'GET_AWAITABLE', 'GET_AITER', 'GET_ANEXT',
                            'BEFORE_ASYNC_WITH', 'SETUP_ASYNC_WITH'} or
             bytecode.flags & CompilerFlags.COROUTINE)):
        flags |= CompilerFlags.COROUTINE

    flags |= bytecode.flags & CompilerFlags.ITERABLE_COROUTINE

    flags |= bytecode.flags & CompilerFlags.FUTURE_GENERATOR_STOP

    if ([bool(flags & getattr(CompilerFlags, k))
         for k in ('COROUTINE', 'ITERABLE_COROUTINE', 'GENERATOR',
                   'ASYNC_GENERATOR')].count(True) > 1):
        raise ValueError("Code should not have more than one of the "
                         "following flag set : generator, coroutine, "
                         "iterable coroutine and async generator, got:"
                         "%s" % flags)

    return flags

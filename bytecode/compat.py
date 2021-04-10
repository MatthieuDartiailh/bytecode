import dis
import sys

import opcode as _opcode

if sys.version_info < (3, 0):
    _stack_effects = {
        _opcode.opmap["POP_TOP"]: (-1, -1),
        _opcode.opmap["ROT_TWO"]: (0, 0),
        _opcode.opmap["ROT_THREE"]: (0, 0),
        _opcode.opmap["DUP_TOP"]: (1, 1),
        _opcode.opmap["ROT_FOUR"]: (0, 0),
        _opcode.opmap["UNARY_POSITIVE"]: (0, 0),
        _opcode.opmap["UNARY_NEGATIVE"]: (0, 0),
        _opcode.opmap["UNARY_NOT"]: (0, 0),
        _opcode.opmap["UNARY_CONVERT"]: (0, 0),
        _opcode.opmap["UNARY_INVERT"]: (0, 0),
        _opcode.opmap["SET_ADD"]: (-1, -1),
        _opcode.opmap["LIST_APPEND"]: (-1, -1),
        _opcode.opmap["MAP_ADD"]: (-2, -2),
        _opcode.opmap["BINARY_POWER"]: (-1, -1),
        _opcode.opmap["BINARY_MULTIPLY"]: (-1, -1),
        _opcode.opmap["BINARY_DIVIDE"]: (-1, -1),
        _opcode.opmap["BINARY_MODULO"]: (-1, -1),
        _opcode.opmap["BINARY_ADD"]: (-1, -1),
        _opcode.opmap["BINARY_SUBTRACT"]: (-1, -1),
        _opcode.opmap["BINARY_SUBSCR"]: (-1, -1),
        _opcode.opmap["BINARY_FLOOR_DIVIDE"]: (-1, -1),
        _opcode.opmap["BINARY_TRUE_DIVIDE"]: (-1, -1),
        _opcode.opmap["INPLACE_FLOOR_DIVIDE"]: (-1, -1),
        _opcode.opmap["INPLACE_TRUE_DIVIDE"]: (-1, -1),
        _opcode.opmap["SLICE+0"]: (0, 0),
        _opcode.opmap["SLICE+1"]: (-1, -1),
        _opcode.opmap["SLICE+2"]: (-1, -1),
        _opcode.opmap["SLICE+3"]: (-2, -2),
        _opcode.opmap["STORE_SLICE+0"]: (-2, -2),
        _opcode.opmap["STORE_SLICE+1"]: (-3, -3),
        _opcode.opmap["STORE_SLICE+2"]: (-3, -3),
        _opcode.opmap["STORE_SLICE+3"]: (-4, -4),
        _opcode.opmap["DELETE_SLICE+0"]: (-1, -1),
        _opcode.opmap["DELETE_SLICE+1"]: (-2, -2),
        _opcode.opmap["DELETE_SLICE+2"]: (-2, -2),
        _opcode.opmap["DELETE_SLICE+3"]: (-3, -3),
        _opcode.opmap["INPLACE_ADD"]: (-1, -1),
        _opcode.opmap["INPLACE_SUBTRACT"]: (-1, -1),
        _opcode.opmap["INPLACE_MULTIPLY"]: (-1, -1),
        _opcode.opmap["INPLACE_DIVIDE"]: (-1, -1),
        _opcode.opmap["INPLACE_MODULO"]: (-1, -1),
        _opcode.opmap["STORE_SUBSCR"]: (-3, -3),
        _opcode.opmap["STORE_MAP"]: (-2, -2),
        _opcode.opmap["DELETE_SUBSCR"]: (-2, -2),
        _opcode.opmap["BINARY_LSHIFT"]: (-1, -1),
        _opcode.opmap["BINARY_RSHIFT"]: (-1, -1),
        _opcode.opmap["BINARY_AND"]: (-1, -1),
        _opcode.opmap["BINARY_XOR"]: (-1, -1),
        _opcode.opmap["BINARY_OR"]: (-1, -1),
        _opcode.opmap["INPLACE_POWER"]: (-1, -1),
        _opcode.opmap["GET_ITER"]: (0, 0),
        _opcode.opmap["PRINT_EXPR"]: (-1, -1),
        _opcode.opmap["PRINT_ITEM"]: (-1, -1),
        _opcode.opmap["PRINT_NEWLINE"]: (0, 0),
        _opcode.opmap["PRINT_ITEM_TO"]: (-2, -2),
        _opcode.opmap["PRINT_NEWLINE_TO"]: (-1, -1),
        _opcode.opmap["INPLACE_LSHIFT"]: (-1, -1),
        _opcode.opmap["INPLACE_RSHIFT"]: (-1, -1),
        _opcode.opmap["INPLACE_AND"]: (-1, -1),
        _opcode.opmap["INPLACE_XOR"]: (-1, -1),
        _opcode.opmap["INPLACE_OR"]: (-1, -1),
        _opcode.opmap["BREAK_LOOP"]: (0, 0),
        _opcode.opmap["SETUP_WITH"]: (4, 4),
        _opcode.opmap["WITH_CLEANUP"]: (-1, -1),  # XXX Sometimes more
        _opcode.opmap["LOAD_LOCALS"]: (1, 1),
        _opcode.opmap["RETURN_VALUE"]: (-1, -1),
        _opcode.opmap["IMPORT_STAR"]: (-1, -1),
        _opcode.opmap["EXEC_STMT"]: (-3, -3),
        _opcode.opmap["YIELD_VALUE"]: (0, 0),
        _opcode.opmap["POP_BLOCK"]: (0, 0),
        _opcode.opmap["END_FINALLY"]: (-3, -3),
        # END_FINALLY: or -1 or -2 if no exception occurred or return/break/continue
        _opcode.opmap["BUILD_CLASS"]: (-2, -2),
        _opcode.opmap["STORE_NAME"]: (-1, -1),
        _opcode.opmap["DELETE_NAME"]: (0, 0),
        _opcode.opmap["FOR_ITER"]: (1, -1),
        _opcode.opmap["STORE_ATTR"]: (-2, -2),
        _opcode.opmap["DELETE_ATTR"]: (-1, -1),
        _opcode.opmap["STORE_GLOBAL"]: (-1, -1),
        _opcode.opmap["DELETE_GLOBAL"]: (0, 0),
        _opcode.opmap["LOAD_CONST"]: (1, 1),
        _opcode.opmap["LOAD_NAME"]: (1, 1),
        _opcode.opmap["BUILD_MAP"]: (1, 1),
        _opcode.opmap["LOAD_ATTR"]: (0, 0),
        _opcode.opmap["COMPARE_OP"]: (-1, -1),
        _opcode.opmap["IMPORT_NAME"]: (-1, -1),
        _opcode.opmap["IMPORT_FROM"]: (1, 1),
        _opcode.opmap["JUMP_FORWARD"]: (0, 0),
        _opcode.opmap["JUMP_IF_TRUE_OR_POP"]: (-1, 0),
        _opcode.opmap["JUMP_IF_FALSE_OR_POP"]: (-1, 0),
        _opcode.opmap["JUMP_ABSOLUTE"]: (0, 0),
        _opcode.opmap["POP_JUMP_IF_FALSE"]: (-1, -1),
        _opcode.opmap["POP_JUMP_IF_TRUE"]: (-1, -1),
        _opcode.opmap["LOAD_GLOBAL"]: (1, 1),
        _opcode.opmap["CONTINUE_LOOP"]: (0, 0),
        _opcode.opmap["SETUP_LOOP"]: (0, 0),
        _opcode.opmap["SETUP_EXCEPT"]: (0, 3),
        _opcode.opmap["SETUP_FINALLY"]: (0, 3),
        _opcode.opmap["LOAD_FAST"]: (1, 1),
        _opcode.opmap["STORE_FAST"]: (-1, -1),
        _opcode.opmap["DELETE_FAST"]: (0, 0),
        _opcode.opmap["LOAD_CLOSURE"]: (1, 1),
        _opcode.opmap["LOAD_DEREF"]: (1, 1),
        _opcode.opmap["STORE_DEREF"]: (-1, -1),
    }

    def stack_effect(opcode, oparg=None, jump=None):
        def nargs(o):
            return int((o % 256) + 2 * (o / 256))

        oparg = oparg or 0
        # TODO: Can add check for when oparg is required
        _stack_effects.update(
            {
                _opcode.opmap["UNPACK_SEQUENCE"]: (oparg - 1, oparg - 1),
                _opcode.opmap["DUP_TOPX"]: (oparg, oparg),
                _opcode.opmap["BUILD_TUPLE"]: (1 - oparg, 1 - oparg),
                _opcode.opmap["BUILD_LIST"]: (1 - oparg, 1 - oparg),
                _opcode.opmap["BUILD_SET"]: (1 - oparg, 1 - oparg),
                _opcode.opmap["RAISE_VARARGS"]: (-oparg, -oparg),
                _opcode.opmap["CALL_FUNCTION"]: (-nargs(oparg), -nargs(oparg)),
                _opcode.opmap["CALL_FUNCTION_VAR"]: (
                    -nargs(oparg) - 1,
                    -nargs(oparg) - 1,
                ),
                _opcode.opmap["CALL_FUNCTION_KW"]: (
                    -nargs(oparg) - 1,
                    -nargs(oparg) - 1,
                ),
                _opcode.opmap["CALL_FUNCTION_VAR_KW"]: (
                    -nargs(oparg) - 2,
                    -nargs(oparg) - 2,
                ),
                _opcode.opmap["MAKE_FUNCTION"]: (-oparg, -oparg),
                _opcode.opmap["BUILD_SLICE"]: (
                    -2 if oparg == 3 else -1,
                    -2 if oparg == 3 else -1,
                ),
                _opcode.opmap["MAKE_CLOSURE"]: (-oparg - 1, -oparg - 1),
            }
        )
        effect = _stack_effects.get(opcode, None)
        if effect is not None:
            return max(effect) if jump is None else effect[jump]
        return (0, 0)


elif sys.version_info < (3, 8):
    _stack_effects = {
        # NOTE: the entries are all 2-tuples.  Entry[0/False] is non-taken jumps.
        # Entry[1/True] is for taken jumps.
        # opcodes not in dis.stack_effect
        _opcode.opmap["EXTENDED_ARG"]: (0, 0),
        _opcode.opmap["NOP"]: (0, 0),
        # Jump taken/not-taken are different:
        _opcode.opmap["JUMP_IF_TRUE_OR_POP"]: (-1, 0),
        _opcode.opmap["JUMP_IF_FALSE_OR_POP"]: (-1, 0),
        _opcode.opmap["FOR_ITER"]: (1, -1),
        _opcode.opmap["SETUP_WITH"]: (1, 6),
        _opcode.opmap["SETUP_ASYNC_WITH"]: (0, 5),
        _opcode.opmap["SETUP_EXCEPT"]: (0, 6),  # as of 3.7, below for <=3.6
        _opcode.opmap["SETUP_FINALLY"]: (0, 6),  # as of 3.7, below for <=3.6
    }

    # More stack effect values that are unique to the version of Python.
    if sys.version_info < (3, 7):
        _stack_effects.update(
            {
                _opcode.opmap["SETUP_WITH"]: (7, 7),
                _opcode.opmap["SETUP_EXCEPT"]: (6, 9),
                _opcode.opmap["SETUP_FINALLY"]: (6, 9),
            }
        )

    def stack_effect(opcode, oparg, jump=None):
        effect = _stack_effects.get(opcode, None)
        if effect is not None:
            return max(effect) if jump is None else effect[jump]
        return dis.stack_effect(opcode, oparg)


else:
    stack_effect = dis.stack_effect

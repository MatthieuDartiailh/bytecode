"""
Peephole optimizer of CPython 3.6 reimplemented in pure Python using
the bytecode module.
"""
import opcode
import operator
import sys
from bytecode import Instr, Bytecode, BytecodeBlocks, Label, Block

PyCmp_IN = 6
PyCmp_NOT_IN = 7
PyCmp_IS = 8
PyCmp_IS_NOT = 9

JUMPS_ON_TRUE = frozenset((
    'POP_JUMP_IF_TRUE',
    'JUMP_IF_TRUE_OR_POP',
))

NOT_PyCmp = {
    PyCmp_IN: PyCmp_NOT_IN,
    PyCmp_NOT_IN: PyCmp_IN,
    PyCmp_IS: PyCmp_IS_NOT,
    PyCmp_IS_NOT: PyCmp_IS,
}

MAX_SIZE = 20


class ExitUnchanged(Exception):
    """Exception used to skip the peephole optimizer"""
    pass


class PeepholeOptimizer:
    """Python reimplementation of the peephole optimizer.

    Copy of the C comment:

    Perform basic peephole optimizations to components of a code object.
    The consts object should still be in list form to allow new constants
    to be appended.

    To keep the optimizer simple, it bails out (does nothing) for code that
    has a length over 32,700, and does not calculate extended arguments.
    That allows us to avoid overflow and sign issues. Likewise, it bails when
    the lineno table has complex encoding for gaps >= 255. EXTENDED_ARG can
    appear before MAKE_FUNCTION; in this case both opcodes are skipped.
    EXTENDED_ARG preceding any other opcode causes the optimizer to bail.

    Optimizations are restricted to simple transformations occuring within a
    single basic block.  All transformations keep the code size the same or
    smaller.  For those that reduce size, the gaps are initially filled with
    NOPs.  Later those NOPs are removed and the jump addresses retargeted in
    a single pass.  Code offset is adjusted accordingly.
    """

    def __init__(self):
        # bytecode.BytecodeBlocks instance
        self.code = None
        self.const_stack = None
        self.block_index = None
        self.block = None
        # index of the current instruction in self.block instructions
        self.index = None
        # whether we are in a LOAD_CONST sequence
        self.in_consts = False

    def check_result(self, value):
        try:
            size = len(value)
        except TypeError:
            return True
        return (size <= MAX_SIZE)

    def replace_load_const(self, nconst, instr, result):
        # FIXME: remove temporary computed constants?
        # FIXME: or at least reuse existing constants?

        self.in_consts = True

        load_const = Instr('LOAD_CONST', result, lineno=instr.lineno)
        start = self.index - nconst - 1
        self.block[start:self.index] = (load_const,)
        self.index -= nconst

        if nconst:
            del self.const_stack[-nconst:]
        self.const_stack.append(result)
        self.in_consts = True

    def eval_LOAD_CONST(self, instr):
        self.in_consts = True
        value = instr.arg
        self.const_stack.append(value)
        self.in_consts = True

    def unaryop(self, op, instr):
        try:
            value = self.const_stack[-1]
            result = op(value)
        except IndexError:
            return

        if not self.check_result(result):
            return

        self.replace_load_const(1, instr, result)

    def eval_UNARY_POSITIVE(self, instr):
        return self.unaryop(operator.pos, instr)

    def eval_UNARY_NEGATIVE(self, instr):
        return self.unaryop(operator.neg, instr)

    def eval_UNARY_INVERT(self, instr):
        return self.unaryop(operator.invert, instr)

    def eval_UNARY_NOT(self, instr):
        # Note: UNARY_NOT <const> is not optimized

        try:
            next_instr = self.block[self.index]
        except IndexError:
            return None
        if next_instr.name == 'POP_JUMP_IF_FALSE':
            # Replace UNARY_NOT+POP_JUMP_IF_FALSE with POP_JUMP_IF_TRUE
            instr.name = 'POP_JUMP_IF_TRUE'
            instr.arg = next_instr.arg
            self.block[self.index-1:self.index+1] = (instr,)
            self.index -= 1

    def binop(self, op, instr):
        try:
            left = self.const_stack[-2]
            right = self.const_stack[-1]
        except IndexError:
            return

        try:
            result = op(left, right)
        except Exception:
            return

        if not self.check_result(result):
            return

        self.replace_load_const(2, instr, result)

    def eval_BINARY_ADD(self, instr):
        return self.binop(operator.add, instr)

    def eval_BINARY_SUBTRACT(self, instr):
        return self.binop(operator.sub, instr)

    def eval_BINARY_MULTIPLY(self, instr):
        return self.binop(operator.mul, instr)

    def eval_BINARY_TRUE_DIVIDE(self, instr):
        return self.binop(operator.truediv, instr)

    def eval_BINARY_FLOOR_DIVIDE(self, instr):
        return self.binop(operator.floordiv, instr)

    def eval_BINARY_MODULO(self, instr):
        return self.binop(operator.mod, instr)

    def eval_BINARY_POWER(self, instr):
        return self.binop(operator.pow, instr)

    def eval_BINARY_LSHIFT(self, instr):
        return self.binop(operator.lshift, instr)

    def eval_BINARY_RSHIFT(self, instr):
        return self.binop(operator.rshift, instr)

    def eval_BINARY_AND(self, instr):
        return self.binop(operator.and_, instr)

    def eval_BINARY_OR(self, instr):
        return self.binop(operator.or_, instr)

    def eval_BINARY_XOR(self, instr):
        return self.binop(operator.xor, instr)

    def eval_BINARY_SUBSCR(self, instr):
        return self.binop(operator.getitem, instr)

    def replace_container_of_consts(self, instr, container_type):
        items = self.const_stack[-instr.arg:]
        value = container_type(items)
        self.replace_load_const(instr.arg, instr, value)

    def build_tuple_unpack_seq(self, instr):
        if not(1 <= instr.arg <= 3):
            return

        next_instr = self.block[self.index]
        if not(next_instr.name == 'UNPACK_SEQUENCE'
               and next_instr.arg == instr.arg):
            return

        if instr.arg == 1:
            # Replace BUILD_TUPLE 1 + UNPACK_SEQUENCE 1 with NOP
            del self.block[self.index-1:self.index+1]
        elif instr.arg == 2:
            # Replace BUILD_TUPLE 2 + UNPACK_SEQUENCE 2 with ROT_TWO
            rot2 = Instr('ROT_TWO', lineno=instr.lineno)
            self.block[self.index - 1:self.index+1] = (rot2,)
            self.index -= 1
            self.const_stack.clear()
        elif instr.arg == 3:
            # Replace BUILD_TUPLE 3 + UNPACK_SEQUENCE 3
            # with ROT_THREE + ROT_TWO
            rot3 = Instr('ROT_THREE', lineno=instr.lineno)
            rot2 = Instr('ROT_TWO', lineno=instr.lineno)
            self.block[self.index-1:self.index+1] = (rot3, rot2)
            self.index -= 1
            self.const_stack.clear()

        # FIXME: why not rewriting LOAD_CONST in the reverse order to support
        # any number of aguments, rather than using ROT_TWO/ROT_THREE tricks?

    def build_tuple(self, instr, container_type):
        if instr.arg > len(self.const_stack):
            return

        next_instr = self.block[self.index]
        if not next_instr.name == 'COMPARE_OP':
            return

        if next_instr.arg not in (PyCmp_IN, PyCmp_NOT_IN):
            return

        self.replace_container_of_consts(instr, container_type)
        return True

    def eval_BUILD_TUPLE(self, instr):
        if not instr.arg:
            return

        if instr.arg <= len(self.const_stack):
            self.replace_container_of_consts(instr, tuple)
        else:
            self.build_tuple_unpack_seq(instr)

    def eval_BUILD_LIST(self, instr):
        if not instr.arg:
            return

        if not self.build_tuple(instr, tuple):
            self.build_tuple_unpack_seq(instr)

    def eval_BUILD_SET(self, instr):
        if not instr.arg:
            return

        self.build_tuple(instr, frozenset)

    # Note: BUILD_SLICE is not optimized

    def eval_COMPARE_OP(self, instr):
        # Note: COMPARE_OP: 2 < 3 is not optimized

        if instr.arg not in NOT_PyCmp:
            return
        new_arg = NOT_PyCmp[instr.arg]

        try:
            next_instr = self.block[self.index]
        except IndexError:
            return
        if next_instr.name != 'UNARY_NOT':
            return

        # not (a is b) -->  a is not b
        # not (a in b) -->  a not in b
        # not (a is not b) -->  a is b
        # not (a not in b) -->  a in b
        instr.arg = new_arg
        self.block[self.index-1:self.index+1] = (instr,)

    def jump_if_or_pop(self, instr):
        # Simplify conditional jump to conditional jump where the
        # result of the first test implies the success of a similar
        # test or the failure of the opposite test.
        #
        # Arises in code like:
        # "if a and b:"
        # "if a or b:"
        # "a and b or c"
        # "(a and b) and c"
        #
        # x:JUMP_IF_FALSE_OR_POP y   y:JUMP_IF_FALSE_OR_POP z
        #    -->  x:JUMP_IF_FALSE_OR_POP z
        #
        # x:JUMP_IF_FALSE_OR_POP y   y:JUMP_IF_TRUE_OR_POP z
        #    -->  x:POP_JUMP_IF_FALSE y+3
        # where y+3 is the instruction following the second test.
        target_block = instr.arg
        target_instr = target_block[0]
        if not target_instr.is_cond_jump():
            self.optimize_jump_to_cond_jump(instr)
            return

        if (target_instr.name in JUMPS_ON_TRUE) == (instr.name in JUMPS_ON_TRUE):
            # The second jump will be taken iff the first is.

            target2 = target_instr.arg
            # The current opcode inherits its target's stack behaviour
            instr.name = target_instr.name
            instr.arg = target2
            self.block[self.index-1] = instr
            self.index -= 1
        else:
            # The second jump is not taken if the first is (so jump past it),
            # and all conditional jumps pop their argument when they're not
            # taken (so change the first jump to pop its argument when it's
            # taken).
            if instr.name in JUMPS_ON_TRUE:
                name = 'POP_JUMP_IF_TRUE'
            else:
                name = 'POP_JUMP_IF_FALSE'

            try:
                new_label = self.code.split_block(target_block, 1)
            except ValueError:
                # FIXME: ValueError: cannot create a label at the end of a block
                return

            instr.name = name
            instr.arg = new_label
            self.block[self.index-1] = instr
            self.index -= 1

    def eval_JUMP_IF_FALSE_OR_POP(self, instr):
        self.jump_if_or_pop(instr)

    def eval_JUMP_IF_TRUE_OR_POP(self, instr):
        self.jump_if_or_pop(instr)

    def check_bypass_optim(self, code_obj):
        # Bypass optimization when the lnotab table is too complex
        if 255 in code_obj.co_lnotab:
            # 255 value are used for multibyte bytecode instructions
            return True
        # Note: -128 and 127 special values for line number delta are ok,
        # the peephole optimizer doesn't modify line numbers.

        # Avoid situations where jump retargeting could overflow
        code = code_obj.co_code
        codelen = len(code)
        if codelen > 32700:
            return True

        # Verify that RETURN_VALUE terminates the codestring. This allows
        # the various transformation patterns to look ahead several
        # instructions without additional checks to make sure they are not
        # looking beyond the end of the code string.
        if code[codelen-1] != opcode.opmap['RETURN_VALUE']:
            return True

        return False

    def optimize_jump_to_cond_jump(self, instr):
        # Replace jumps to unconditional jumps
        jump_label = instr.arg
        assert isinstance(jump_label, Block), jump_label

        target_instr = jump_label[0]
        if (instr.is_uncond_jump()
           and target_instr.name == 'RETURN_VALUE'):
            # Replace JUMP_ABSOLUTE => RETURN_VALUE with RETURN_VALUE
            self.block[self.index-1] = target_instr

        elif target_instr.is_uncond_jump():
            # Replace JUMP_FORWARD t1 => JUMP_FORWARD t2
            # with JUMP_FORWARD t2 (and keep JUMP_FORWARD t2)
            jump_target2 = target_instr.arg

            name = instr.name
            if instr.name == 'JUMP_FORWARD':
                name = 'JUMP_ABSOLUTE'

            # FIXME: reimplement this check
            #if jump_target2 < 0:
            #    # No backward relative jumps
            #    return

            # FIXME: remove this workaround and implement comment code ^^
            if instr.op in opcode.hasjrel:
                return

            instr.name = name
            instr.arg = jump_target2
            self.block[self.index-1] = instr

    def iterblock(self, block):
        self.block = block
        self.index = 0
        while self.index < len(block):
            instr = self.block[self.index]
            self.index += 1
            yield instr

    def optimize_block(self, block):
        for instr in self.iterblock(block):
            if not self.in_consts:
                self.const_stack.clear()
            self.in_consts = False

            meth_name = 'eval_%s' % instr.name
            meth = getattr(self, meth_name, None)
            if meth is not None:
                meth(instr)
            elif instr.has_jump():
                self.optimize_jump_to_cond_jump(instr)

            # Note: Skipping over LOAD_CONST trueconst; POP_JUMP_IF_FALSE
            # <target> is not implemented, since it looks like the optimization
            # is never trigerred in practice. The compiler already optimizes if
            # and while statements.

    def remove_dead_blocks(self):
        # FIXME: remove empty blocks?

        # FIXME: rewrite this
        used_blocks = {id(self.code[0])}
        for block in self.code:
            if block.next_block is not None:
                used_blocks.add(id(block.next_block))
            for instr in block:
                if isinstance(instr, Instr) and isinstance(instr.arg, Block):
                    used_blocks.add(id(instr.arg))

        block_index = 0
        while block_index < len(self.code):
            block = self.code[block_index]
            if id(block) not in used_blocks:
                del self.code[block_index]
            else:
                block_index += 1

    def _optimize(self, code):
        self.code = code
        self.const_stack = []

        self.block_index = 0
        while self.block_index < len(self.code):
            block = self.code[self.block_index]
            self.block_index += 1
            self.optimize_block(block)

        self.remove_dead_blocks()

    def optimize(self, code_obj):
        bytecode = Bytecode.from_code(code_obj)
        bytecode = BytecodeBlocks.from_bytecode(bytecode)
        self._optimize(bytecode)
        return bytecode.to_code()


# Code transformer for the PEP 511
class CodeTransformer:
    name = "pyopt"

    def code_transformer(self, code, context):
        if sys.flags.verbose:
            print("Optimize %s:%s: %s"
                  % (code.co_filename, code.co_firstlineno, code.co_name))
        optimizer = PeepholeOptimizer()
        return optimizer.optimize(code)

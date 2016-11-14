import dis
import inspect
import opcode as _opcode
import struct
import sys
import types
from enum import Enum

# alias to keep the 'bytecode' variable free
import bytecode as _bytecode
from bytecode.instr import (UNSET, Instr, Label, SetLineno,
                            FreeVar, CellVar, Compare,
                            const_key, _check_arg_int)

_WORDCODE = (sys.version_info >= (3, 6))


def _set_docstring(code, consts):
    if not consts:
        return
    first_const = consts[0]
    if isinstance(first_const, str) or first_const is None:
        code.docstring = first_const


class ConcreteInstr(Instr):
    """Concrete instruction.

    arg must be an integer in the range 0..2147483647.

    It has a read-only size attribute.
    """

    __slots__ = ('_size',)

    def __init__(self, name, arg=UNSET, *, lineno=None):
        self._set(name, arg, lineno)

    def _check_arg(self, name, opcode, arg):
        if opcode >= _opcode.HAVE_ARGUMENT:
            if arg is UNSET:
                raise ValueError("operation %s requires an argument" % name)

            _check_arg_int(name, arg)
        else:
            if arg is not UNSET:
                raise ValueError("operation %s has no argument" % name)

    def _set(self, name, arg, lineno):
        super()._set(name, arg, lineno)
        if _WORDCODE:
            size = 2
            if arg is not UNSET:
                while arg > 0xff:
                    size += 2
                    arg >>= 8
        else:
            size = 1
            if arg is not UNSET:
                size += 2
                if arg > 0xffff:
                    size += 3
        self._size = size

    @property
    def size(self):
        return self._size

    def _cmp_key(self, labels=None):
        return (self._lineno, self._name, self._arg)

    def get_jump_target(self, instr_offset):
        if self._opcode in _opcode.hasjrel:
            return instr_offset + self._size + self._arg
        if self._opcode in _opcode.hasjabs:
            return self._arg
        return None

    if _WORDCODE:
        def assemble(self):
            if self._arg is UNSET:
                return bytes((self._opcode, 0))

            arg = self._arg
            b = [self._opcode, arg & 0xff]
            while arg > 0xff:
                arg >>= 8
                b[:0] = [_opcode.EXTENDED_ARG, arg & 0xff]

            return bytes(b)
    else:
        def assemble(self):
            if self._arg is UNSET:
                return struct.pack('<B', self._opcode)

            arg = self._arg
            if arg > 0xffff:
                return struct.pack('<BHBH',
                                   _opcode.EXTENDED_ARG, arg >> 16,
                                   self._opcode, arg & 0xffff)
            else:
                return struct.pack('<BH', self._opcode, arg)

    @classmethod
    def disassemble(cls, lineno, code, offset):
        op = code[offset]
        if op >= _opcode.HAVE_ARGUMENT:
            if _WORDCODE:
                arg = code[offset + 1]
            else:
                arg = code[offset + 1] + code[offset + 2] * 256
        else:
            arg = UNSET
        name = _opcode.opname[op]
        return cls(name, arg, lineno=lineno)


class ConcreteBytecode(_bytecode.BaseBytecode, list):

    def __init__(self):
        super().__init__()
        self.consts = []
        self.names = []
        self.varnames = []

    def __iter__(self):
        instructions = super().__iter__()
        for instr in instructions:
            if not isinstance(instr, (ConcreteInstr, SetLineno)):
                raise ValueError("ConcreteBytecode must only contain "
                                 "ConcreteInstr and SetLineno objects, "
                                 "but %s was found"
                                 % instr.__class__.__name__)

            yield instr

    def __repr__(self):
        return '<ConcreteBytecode instr#=%s>' % len(self)

    def __eq__(self, other):
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
    def from_code(code, *, extended_arg=False):
        line_starts = dict(dis.findlinestarts(code))

        # find block starts
        instructions = []
        offset = 0
        lineno = code.co_firstlineno
        while offset < len(code.co_code):
            if offset in line_starts:
                lineno = line_starts[offset]

            instr = ConcreteInstr.disassemble(lineno, code.co_code, offset)

            instructions.append(instr)
            offset += instr.size

        # replace jump targets with blocks
        if not extended_arg:
            extended_arg = None
            index = 0
            while index < len(instructions):
                instr = instructions[index]

                if instr.name == 'EXTENDED_ARG':
                    if extended_arg is not None:
                        if not _WORDCODE:
                            raise ValueError("EXTENDED_ARG followed "
                                             "by EXTENDED_ARG")
                        extended_arg = (extended_arg << 8) + instr.arg
                    else:
                        extended_arg = instr.arg
                    del instructions[index]
                    continue

                if extended_arg is not None:
                    if _WORDCODE:
                        arg = (extended_arg << 8) + instr.arg
                    else:
                        arg = (extended_arg << 16) + instr.arg
                    extended_arg = None

                    instr = ConcreteInstr(instr.name, arg, lineno=instr.lineno)
                    instructions[index] = instr

                index += 1

            if extended_arg is not None:
                raise ValueError("EXTENDED_ARG at the end of the code")

        bytecode = ConcreteBytecode()
        bytecode.name = code.co_name
        bytecode.filename = code.co_filename
        bytecode.flags = code.co_flags
        bytecode.argcount = code.co_argcount
        bytecode.kwonlyargcount = code.co_kwonlyargcount
        bytecode._stacksize = code.co_stacksize
        bytecode.first_lineno = code.co_firstlineno
        bytecode.names = list(code.co_names)
        bytecode.consts = list(code.co_consts)
        bytecode.varnames = list(code.co_varnames)
        bytecode.freevars = list(code.co_freevars)
        bytecode.cellvars = list(code.co_cellvars)
        _set_docstring(bytecode, code.co_consts)

        bytecode[:] = instructions
        return bytecode

    def _normalize_lineno(self):
        lineno = self.first_lineno
        for instr in self:
            # if instr.lineno is not set, it's inherited from the previous
            # instruction, or from self.first_lineno
            if instr.lineno is not None:
                lineno = instr.lineno

            if isinstance(instr, ConcreteInstr):
                yield (lineno, instr)

    def _assemble_code(self):
        offset = 0
        code_str = []
        linenos = []
        for lineno, instr in self._normalize_lineno():
            code_str.append(instr.assemble())
            linenos.append((offset, lineno))
            offset += instr.size
        code_str = b''.join(code_str)
        return (code_str, linenos)

    @staticmethod
    def _assemble_lnotab(first_lineno, linenos):
        lnotab = []
        old_offset = 0
        old_lineno = first_lineno
        for offset, lineno in linenos:
            dlineno = lineno - old_lineno
            if dlineno == 0:
                continue
            # FIXME: be kind, force monotonic line numbers? add an option?
            if dlineno < 0 and sys.version_info < (3, 6):
                raise ValueError("negative line number delta is not supported "
                                 "on Python < 3.6")
            old_lineno = lineno

            doff = offset - old_offset
            old_offset = offset

            while doff > 255:
                lnotab.append(b'\xff\x00')
                doff -= 255

            while dlineno < -127:
                lnotab.append(struct.pack('Bb', 0, -127))
                dlineno -= -127

            while dlineno > 126:
                lnotab.append(struct.pack('Bb', 0, 126))
                dlineno -= 126

            assert 0 <= doff <= 255
            assert -127 <= dlineno <= 126

            lnotab.append(struct.pack('Bb', doff, dlineno))

        return b''.join(lnotab)

    def _find_jump_targets(self, opcodes=None, mapping=False):
        jump_targets = set() if not mapping else dict()
        offset = 0
        for instr in self:
            if isinstance(instr, SetLineno):
                continue
            target = instr.get_jump_target(offset)
            if target is not None and (opcodes is None or
                                       instr.name in opcodes):
                if mapping:
                    jump_targets[id(instr)] = target
                else:
                    jump_targets.add(target)
            offset += instr.size

        return jump_targets

    def _compute_addresses(self):
        offset = 0
        addresses = dict()
        for instr in self:
            if isinstance(instr, SetLineno):
                continue
            addresses[offset] = instr
            offset += instr.size

        return addresses

    def _compute_stacksize(self, logging=False):

        # sf_targets are the targets of SETUP_FINALLY opcodes. They are
        # recorded because they have special stack behaviour. If an exception
        # was raised in the block pushed by a SETUP_FINALLY opcode, the block
        # is popped and 3 objects are pushed. On return or continue, the block
        # is popped and 2 objects are pushed. If nothing happened, the block is
        # popped by a POP_BLOCK opcode and 1 object is pushed by a
        # (LOAD_CONST, None) operation
        # Our solution is to record the stack state of SETUP_FINALLY targets
        # as having 3 objects pushed, which is the maximum. However, to make
        # stack recording consistent, the get_next_stacks function will always
        # yield the stack state of the target as if 1 object was pushed, but
        # this will be corrected in the actual stack recording
        finally_opcodes = ('SETUP_FINALLY', 'SETUP_WITH')
        if sys.version_info > (3, 5):
            finally_opcodes += ('SETUP_ASYNC_WITH',)
        sf_targets = self._find_jump_targets(finally_opcodes)

        jump_targets = self._find_jump_targets(mapping=True)

        # Determine the addresses of each opcode
        addresses = self._compute_addresses()
        last_address = max(addresses)

        # Container for the stack state at each address
        states = [None] * (last_address + 1)
        maxsize = 0

        # Analysis to carry out to determine the stack depth
        ops = [_StackState(self, logging=logging)]
        add_op = ops.append

        while ops:
            # Get the nex analysis to run and update the stack depth if
            # necessary
            cur_state = ops.pop()
            o = sum(cur_state.stack)
            if o > maxsize:
                maxsize = o

            # Make sure we never go to far in the address space
            cur_addr = cur_state.addr
            if cur_addr > last_address:
                msg = 'Stack depth computation failed to complete.'
                raise RuntimeError(msg)
            # Get the opcode to analyse
            o = addresses.get(cur_state.addr)

            if id(o) in jump_targets:
                # If it is a target of SETUP_FINALLY increase stack
                if cur_state.addr in sf_targets:
                    cur_state.stack = cur_state.newstack(5)
                # If we encounter this label for the first time, start tracking
                # the stack state.
                if states[cur_state.addr] is None:
                    states[cur_state.addr] = cur_state
                # If we have already analysed this target run some sanity
                # checks
                elif states[cur_state.addr].stack != cur_state.stack:
                    check_addr = cur_state.addr + 1
                    while (not addresses.get(check_addr) or
                           not addresses.get(check_addr).has_flow()):
                        check_addr += 1
                        if check_addr > last_address:
                            raise RuntimeError('Failed to find has flow op.')

                    if addresses[check_addr].name not in ('RETURN_VALUE',
                                                          'RAISE_VARARGS'):
                        if cur_state.addr not in sf_targets:
                            msg = "Inconsistent code at %s %s %s\n%s"
                            args = (cur_state.addr, cur_state.stack,
                                    states[cur_state.addr].stack,
                                    cur_state.neighnouring_ops(5, 4))
                            raise ValueError(msg % args)
                        else:
                            # SETUP_FINALLY target inconsistent code!
                            #
                            # Since Python 3.2 assigned exception is cleared at
                            # the end of the except clause (named exception
                            # handler). To perform this CPython (checked in
                            # version 3.4.3) adds special bytecode in exception
                            # handler which currently breaks 'regularity' of
                            # bytecode. Exception handler is wrapped in
                            # try/finally block and POP_EXCEPT opcode is
                            # inserted before END_FINALLY, as a result
                            # cleanup-finally block is executed outside except
                            # handler. It's not a bug, as it doesn't cause
                            # any problems during execution, but it breaks
                            # 'regularity' and we can't check inconsistency
                            # here. Maybe issue should be posted to Python bug
                            # tracker.
                            pass
                    continue
                else:
                    continue

            # Nothing to do here
            if isinstance(o, Instr) and o.name in ('BREAK_LOOP',
                                                   'RETURN_VALUE',
                                                   'RAISE_VARARGS'):
                continue

            next_addr = cur_state.addr + 1
            # Those can be SetLineno or None because we are looking at a
            # meaningless address, simply go to next opcode
            if not isinstance(o, Instr):
                add_op(_StackState(self, next_addr, cur_state.stack,
                                   cur_state.block_stack, cur_state.log,
                                   logging))
                continue

            o_name = o.name
            o_opcode = o.opcode
            # For opcode without flow control simply compute their stack effect
            if not o.has_flow():
                if o_name in {'LOAD_GLOBAL', 'LOAD_CONST', 'LOAD_NAME',
                              'LOAD_FAST', 'LOAD_ATTR', 'LOAD_DEREF',
                              'LOAD_CLASSDEREF', 'LOAD_CLOSURE',
                              'STORE_GLOBAL', 'STORE_NAME', 'STORE_FAST',
                              'STORE_ATTR', 'STORE_DEREF', 'DELETE_GLOBAL',
                              'DELETE_NAME', 'DELETE_FAST', 'DELETE_ATTR',
                              'DELETE_DEREF', 'IMPORT_NAME', 'IMPORT_FROM',
                              'COMPARE_OP'}:
                    se = dis.stack_effect(o_opcode, 0)
                else:
                    # XXX SHOULD probably be fixed in Instr
                    arg = o.arg
                    se = dis.stack_effect(o_opcode,
                                          arg if arg is not UNSET else None)

                log = cur_state.newlog("non-flow command (" + str(o) +
                                       ", se = " + str(se) + ")")
                add_op(_StackState(self, next_addr, cur_state.newstack(se),
                                   cur_state.block_stack, log, logging))

            elif o_name == 'FOR_ITER':
                # FOR_ITER pushes next(TOS) on success, and pops TOS and jumps
                # on failure
                inside_for_log = cur_state.newlog("FOR_ITER (+1)")
                ops += (_StackState(self, jump_targets[id(o)],
                                    cur_state.newstack(-1),
                                    cur_state.block_stack, cur_state.log,
                                    logging),
                        _StackState(self, next_addr, cur_state.newstack(1),
                                    cur_state.block_stack, inside_for_log,
                                    logging))

            elif o_name in {'JUMP_FORWARD', 'JUMP_ABSOLUTE'}:
                # One possibility for a jump
                after_jump_log = cur_state.newlog(str(o))
                add_op(_StackState(self, jump_targets[id(o)],
                                   cur_state.stack, cur_state.block_stack,
                                   after_jump_log, logging))

            elif o_name in {'JUMP_IF_FALSE_OR_POP', 'JUMP_IF_TRUE_OR_POP'}:
                # Two possibilities for a jump
                after_jump_log = cur_state.newlog(str(o) + ", jumped")
                log = cur_state.newlog(str(o) + ", not jumped (-1)")
                ops += (_StackState(self, jump_targets[id(o)],
                                    cur_state.stack, cur_state.block_stack,
                                    after_jump_log, logging),
                        _StackState(self, next_addr, cur_state.newstack(-1),
                                    cur_state.block_stack, log, logging))

            elif o_name in {'POP_JUMP_IF_TRUE', 'POP_JUMP_IF_FALSE'}:
                # Two possibilities for a jump
                after_jump_log = cur_state.newlog(str(o) + ", jumped (-1)")
                log = cur_state.newlog(str(o) + ", not jumped (-1)")
                ops += (_StackState(self, jump_targets[id(o)],
                                    cur_state.newstack(-1),
                                    cur_state.block_stack, after_jump_log,
                                    logging),
                        _StackState(self, next_addr, cur_state.newstack(-1),
                                    cur_state.block_stack, log, logging))

            elif o_name == 'CONTINUE_LOOP':
                # CONTINUE_LOOP jumps to the beginning of a loop which should
                # already ave been discovered, but we verify anyway.
                # It pops a block.
                next_stack, next_block_stack =\
                    cur_state.stack, cur_state.block_stack
                last_popped_block = None
                while next_block_stack[-1] != _BlockType.LOOP_BODY:
                    last_popped_block = next_block_stack[-1]
                    next_stack, next_block_stack =\
                        next_stack[:-1], next_block_stack[:-1]

                if next_stack != cur_state.stack:
                    msg = "CONTINUE_LOOP, from non-loop block"
                    log = cur_state.newlog(msg)
                else:
                    log = cur_state.newlog("CONTINUE_LOOP")

                if last_popped_block == _BlockType.WITH_BLOCK:
                    next_stack = next_stack[:-1] + (next_stack[-1] - 1,)
                add_op(_StackState(self, jump_targets[id(o)], next_stack,
                                   next_block_stack, log, logging))

            elif o_name == 'SETUP_LOOP':
                # We continue with a new block.
                # On break, we jump to the label and return to current stack
                # state.
                inside_loop_log = cur_state.newlog("SETUP_LOOP (+block)")
                ops += (_StackState(self, jump_targets[id(o)],
                                    cur_state.stack, cur_state.block_stack,
                                    cur_state.log, logging),
                        _StackState(self, next_addr, cur_state.stack + (0,),
                                    cur_state.block_stack +
                                    (_BlockType.LOOP_BODY,),
                                    inside_loop_log, logging))

            elif o_name == 'SETUP_EXCEPT':
                # We continue with a new block.
                # On exception, we jump to the label with 3 extra objects on
                # stack
                # FIXME : why use 6 here ?
                inside_except_log = cur_state.newlog("SETUP_EXCEPT, "
                                                     "exception (+6, +block)")
                inside_try_log = cur_state.newlog("SETUP_EXCEPT, "
                                                  "try-block (+block)")
                ops += (_StackState(self, jump_targets[id(o)],
                                    cur_state.stack + (6,),
                                    cur_state.block_stack +
                                    (_BlockType.EXCEPTION,),
                                    inside_except_log, logging),
                        _StackState(self, next_addr, cur_state.stack + (0,),
                                    cur_state.block_stack +
                                    (_BlockType.TRY_EXCEPT,), inside_try_log,
                                    logging))

            elif o_name == 'SETUP_FINALLY':
                # We continue with a new block.
                # On exception, we jump to the label with 3 extra objects on
                # stack, but to keep stack recording consistent, we behave as
                # if we add only 1 object. Extra 2 will be added to the actual
                # recording.
                inside_finally_block = cur_state.newlog("SETUP_FINALLY (+1)")
                inside_try_log = cur_state.newlog("SETUP_FINALLY "
                                                  "try-block (+block)")
                ops += (_StackState(self, jump_targets[id(o)],
                                    cur_state.newstack(1),
                                    cur_state.block_stack,
                                    inside_finally_block, logging),
                        _StackState(self, next_addr, cur_state.stack + (0,),
                                    cur_state.block_stack +
                                    (_BlockType.TRY_FINALLY,), inside_try_log,
                                    logging))

            elif o_name == 'POP_BLOCK':
                # Just pop the block
                log = cur_state.newlog("POP_BLOCK (-block)")
                add_op(_StackState(self, next_addr, cur_state.stack[:-1],
                                   cur_state.block_stack[:-1], log, logging))

            elif o_name == 'POP_EXCEPT':
                log = cur_state.newlog("POP_EXCEPT (-block)")
                add_op(_StackState(self, next_addr, cur_state.stack[:-1],
                                   cur_state.block_stack[:-1], log, logging))

            elif o_name == 'END_FINALLY':
                # Since stack recording of SETUP_FINALLY targets is of 3 pushed
                # objects (as when an exception is raised), we pop 3 objects.
                # FIXME : comment is wrong ! what changed between 2 and 3
                if (cur_state.block_stack[-1] ==
                        _BlockType.SILENCED_EXCEPTION_BLOCK):
                    msg = "END_FINALLY pop silenced exception block (-block)"
                    log = cur_state.newlog(msg)
                    add_op(_StackState(next_addr, cur_state.stack[:-1],
                                       cur_state.block_stack[:-1], log,
                                       logging))
                elif cur_state.block_stack[-1] == _BlockType.EXCEPTION:
                    # Reraise exception
                    pass
                else:
                    log = cur_state.newlog("END_FINALLY (-6)")
                    add_op(_StackState(next_addr, cur_state.newstack(-6),
                                       cur_state.block_stack, log, logging))

            elif o_name == 'SETUP_WITH' or (sys.version >= (3, 5) and
                                            o_name == 'SETUP_ASYNC_WITH'):
                inside_with_block = cur_state.newlog("SETUP_WITH, "
                                                     "with-block (+1, +block)")
                inside_finally_block = cur_state.newlog("SETUP_WITH, "
                                                        "finally (+1)")
                ops += (_StackState(self, jump_targets[id(o)],
                                    cur_state.newstack(1),
                                    cur_state.block_stack,
                                    inside_finally_block, logging),
                        _StackState(self, next_addr, cur_state.stack + (1,),
                                    cur_state.block_stack +
                                    (_BlockType.WITH_BLOCK,),
                                    inside_with_block, logging))

            elif sys.version_info < (3, 5) and o_name == 'WITH_CLEANUP':
                # There is special case when 'with' __exit__ function returns
                # True, that's the signal to silence exception, in this case
                # additional element is pushed and next END_FINALLY command
                # won't reraise exception.
                log = cur_state.newlog("WITH_CLEANUP (-1)")
                msg = "WITH_CLEANUP silenced_exception (+1, +block)"
                silenced_exception_log = cur_state.newlog(msg)
                ops += (_StackState(self, next_addr, cur_state.newstack(-1),
                                    cur_state.block_stack, log, logging),
                        _StackState(self, next_addr,
                                    cur_state.newstack(-7) + (8,),
                                    cur_state.block_stack +
                                    (_BlockType.SILENCED_EXCEPTION_BLOCK,),
                                    silenced_exception_log, logging))

            elif sys.version_info >= (3, 5) and o_name == 'WITH_CLEANUP_START':
                # There is special case when 'with' __exit__ function returns
                # True, that's the signal to silence exception, in this case
                # additional element is pushed and next END_FINALLY command
                # won't reraise exception. Emulate this situation on
                # WITH_CLEANUP_START with creating special block which will be
                # handled differently by WITH_CLEANUP_FINISH and will cause
                # END_FINALLY not to reraise exception.
                log = cur_state.newlog("WITH_CLEANUP_START (+1)")
                msg = "WITH_CLEANUP_START silenced_exception (+block)"
                silenced_exception_log = cur_state.newlog(msg)
                ops += (_StackState(self, next_addr, cur_state.newstack(1),
                                    cur_state.block_stack, log, logging),
                        _StackState(self, next_addr,
                                    cur_state.newstack(-7) + (9,),
                                    cur_state.block_stack +
                                    (_BlockType.SILENCED_EXCEPTION_BLOCK,),
                                    silenced_exception_log, logging))

            elif (sys.version_info >= (3, 5) and
                  o_name == 'WITH_CLEANUP_FINISH'):
                if (cur_state.block_stack[-1] ==
                        _BlockType.SILENCED_EXCEPTION_BLOCK):
                    # See comment in WITH_CLEANUP_START handler
                    log = cur_state.newlog("WITH_CLEANUP_FINISH "
                                           "silenced_exception (-1)")
                    add_op(_StackState(self, next_addr, cur_state.newstack(-1),
                                       cur_state.block_stack, log, logging))
                else:
                    log = cur_state.newlog("WITH_CLEANUP_FINISH (-2)")
                    add_op(_StackState(self, next_addr, cur_state.newstack(-2),
                                       cur_state.block_stack, log, logging))

            else:
                raise ValueError("Unhandled opcode %s" % o)

        return maxsize + 6  # for exception raise in deepest place

    def to_code(self):
        code_str, linenos = self._assemble_code()
        lnotab = self._assemble_lnotab(self.first_lineno, linenos)
        nlocals = len(self.varnames)
        return types.CodeType(self.argcount,
                              self.kwonlyargcount,
                              nlocals,
                              self._compute_stacksize(),
                              self.flags,
                              code_str,
                              tuple(self.consts),
                              tuple(self.names),
                              tuple(self.varnames),
                              self.filename,
                              self.name,
                              self.first_lineno,
                              lnotab,
                              tuple(self.freevars),
                              tuple(self.cellvars))

    def to_bytecode(self):
        # find jump targets
        jump_targets = self._find_jump_targets()

        # create labels
        jumps = []
        instructions = []
        labels = {}
        offset = 0
        ncells = len(self.cellvars)

        for lineno, instr in self._normalize_lineno():
            if offset in jump_targets:
                label = Label()
                labels[offset] = label
                instructions.append(label)

            jump_target = instr.get_jump_target(offset)
            size = instr.size

            arg = instr.arg
            # FIXME: better error reporting
            if instr.opcode in _opcode.hasconst:
                arg = self.consts[arg]
            elif instr.opcode in _opcode.haslocal:
                arg = self.varnames[arg]
            elif instr.opcode in _opcode.hasname:
                arg = self.names[arg]
            elif instr.opcode in _opcode.hasfree:
                if arg < ncells:
                    name = self.cellvars[arg]
                    arg = CellVar(name)
                else:
                    name = self.freevars[arg - ncells]
                    arg = FreeVar(name)
            elif instr.opcode in _opcode.hascompare:
                arg = Compare(arg)

            if jump_target is None:
                instr = Instr(instr.name, arg, lineno=lineno)
            else:
                instr_index = len(instructions)
            instructions.append(instr)
            offset += size

            if jump_target is not None:
                jumps.append((instr_index, jump_target))

        # replace jump targets with labels
        for index, jump_target in jumps:
            instr = instructions[index]
            # FIXME: better error reporting on missing label
            label = labels[jump_target]
            instructions[index] = Instr(instr.name, label, lineno=instr.lineno)

        bytecode = _bytecode.Bytecode()
        bytecode._copy_attr_from(self)

        nargs = bytecode.argcount + bytecode.kwonlyargcount
        if bytecode.flags & inspect.CO_VARARGS:
            nargs += 1
        if bytecode.flags & inspect.CO_VARKEYWORDS:
            nargs += 1
        bytecode.argnames = self.varnames[:nargs]
        _set_docstring(bytecode, self.consts)

        bytecode.extend(instructions)
        return bytecode


class _BlockType(Enum):
    """Helper to compute stack size.

    """
    DEFAULT = 0,
    TRY_FINALLY = 1,
    TRY_EXCEPT = 2,
    LOOP_BODY = 3,
    WITH_BLOCK = 4,
    EXCEPTION = 5,
    SILENCED_EXCEPTION_BLOCK = 6,


class _StackState(object):
    """Helper to compute the stack size of a code object.

    """
    __slots__ = ('_addresses', '_addr', '_stack', '_block_stack', '_log',
                 '_logging')

    def __init__(self, addresses, addr=0, stack=(0,),
                 block_stack=(_BlockType.DEFAULT,), log=[], logging=False):
        self._addresses = addresses
        self._addr = addr
        self._stack = stack
        self._block_stack = block_stack
        self._log = log
        self._logging = logging

    @property
    def addr(self):
        return self._addr

    @property
    def stack(self):
        return self._stack

    @stack.setter
    def stack(self, val):
        self._stack = val

    def newstack(self, n):
        if self._stack[-1] < -n:
            raise ValueError("Popped a non-existing element at %s %s" %
                             (self._addr,
                              self.neighnouring_ops(4, 3)))
        return self._stack[:-1] + (self._stack[-1] + n,)

    @property
    def block_stack(self):
        return self._block_stack

    @property
    def log(self):
        return self._log

    def neighnouring_ops(self, n_previous, n_next):
        ops = []
        for i in range(self._addr - n_previous, self._addr + n_next):
            if i in self._addresses:
                ops.append((i, self._addresses[i]))

        return ops

    def newlog(self, msg):
        if not self._logging:
            return None

        log_msg = str(self._addr) + ": " + msg
        if self._stack:
            log_msg += " (on stack: "
            log_depth = 2
            log_depth = min(log_depth, len(self._stack))
            for pos in range(-1, -log_depth, -1):
                log_msg += str(self._stack[pos]) + ", "
            log_msg += str(self._stack[-log_depth])
            log_msg += ")"
        else:
            log_msg += " (empty stack)"
        return [log_msg] + self._log


class _ConvertBytecodeToConcrete:

    def __init__(self, code):
        assert isinstance(code, _bytecode.Bytecode)
        self.bytecode = code

        # temporary variables
        self.instructions = []
        self.jumps = []
        self.labels = {}

        # used to build ConcreteBytecode() object
        self.consts = {}
        self.names = []
        self.varnames = []

    def add_const(self, value):
        key = const_key(value)
        if key in self.consts:
            return self.consts[key]
        index = len(self.consts)
        self.consts[key] = index
        return index

    @staticmethod
    def add(names, name):
        try:
            index = names.index(name)
        except ValueError:
            index = len(names)
            names.append(name)
        return index

    def concrete_instructions(self):
        ncells = len(self.bytecode.cellvars)
        lineno = self.bytecode.first_lineno

        for instr in self.bytecode:
            if isinstance(instr, Label):
                self.labels[instr] = len(self.instructions)
                continue

            if isinstance(instr, SetLineno):
                lineno = instr.lineno
                continue

            if isinstance(instr, ConcreteInstr):
                instr = instr.copy()
            else:
                assert isinstance(instr, Instr)

                if instr.lineno is not None:
                    lineno = instr.lineno

                arg = instr.arg
                is_jump = isinstance(arg, Label)
                if is_jump:
                    label = arg
                    # fake value, real value is set in compute_jumps()
                    arg = 0
                elif instr.opcode in _opcode.hasconst:
                    arg = self.add_const(arg)
                elif instr.opcode in _opcode.haslocal:
                    arg = self.add(self.varnames, arg)
                elif instr.opcode in _opcode.hasname:
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

                instr = ConcreteInstr(instr.name, arg, lineno=lineno)
                if is_jump:
                    self.jumps.append((len(self.instructions), label, instr))

            self.instructions.append(instr)

    def compute_jumps(self):
        offsets = []
        offset = 0
        for index, instr in enumerate(self.instructions):
            offsets.append(offset)
            offset += instr.size
        # needed if a label is at the end
        offsets.append(offset)

        # fix argument of jump instructions: resolve labels
        modified = False
        for index, label, instr in self.jumps:
            target_index = self.labels[label]
            target_offset = offsets[target_index]

            if instr.opcode in _opcode.hasjrel:
                instr_offset = offsets[index]
                target_offset -= (instr_offset + instr.size)

            old_size = instr.size
            # FIXME: better error report if target_offset is negative
            instr.arg = target_offset
            if instr.size != old_size:
                modified = True

        return modified

    def to_concrete_bytecode(self):
        first_const = self.bytecode.docstring
        if first_const is not UNSET:
            self.add_const(first_const)

        self.varnames.extend(self.bytecode.argnames)

        self.concrete_instructions()
        modified = self.compute_jumps()
        if modified:
            modified = self.compute_jumps()
            if modified:
                raise RuntimeError("compute_jumps() must not modify jumps "
                                   "at the second iteration")

        consts = [None] * len(self.consts)
        for item, index in self.consts.items():
            # const_key(value)[1] is value: see const_key() function
            consts[index] = item[1]

        concrete = ConcreteBytecode()
        concrete._copy_attr_from(self.bytecode)
        concrete.consts = consts
        concrete.names = self.names
        concrete.varnames = self.varnames

        # copy instructions
        concrete[:] = self.instructions
        return concrete

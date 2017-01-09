************************
Control Flow Graph (CFG)
************************

To analyze or optimize existing code, ``bytecode`` provides a
:class:`ControlFlowGraph` class which is a `control flow graph (CFG)
<https://en.wikipedia.org/wiki/Control_flow_graph>`_.

The control flow graph is used to perform the stack depth analysis when
converting to code. Because it is better at identifying dead code than CPython
it can lead to reduced stack size.

Example
=======

Dump the control flow graph of the :ref:`conditional jump example
<ex-cond-jump>`::

    from bytecode import Label, Instr, Bytecode, ControlFlowGraph, dump_bytecode

    label_else = Label()
    label_print = Label()
    bytecode = Bytecode([Instr('LOAD_NAME', 'print'),
                         Instr('LOAD_NAME', 'test'),
                         Instr('POP_JUMP_IF_FALSE', label_else),
                             Instr('LOAD_CONST', 'yes'),
                             Instr('JUMP_FORWARD', label_print),
                         label_else,
                             Instr('LOAD_CONST', 'no'),
                         label_print,
                             Instr('CALL_FUNCTION', 1),
                         Instr('LOAD_CONST', None),
                         Instr('RETURN_VALUE')])

    blocks = ControlFlowGraph.from_bytecode(bytecode)
    dump_bytecode(blocks)

Output::

    block1:
        LOAD_NAME 'print'
        LOAD_NAME 'test'
        POP_JUMP_IF_FALSE <block3>
        -> block2

    block2:
        LOAD_CONST 'yes'
        JUMP_FORWARD <block4>

    block3:
        LOAD_CONST 'no'
        -> block4

    block4:
        CALL_FUNCTION 1
        LOAD_CONST None
        RETURN_VALUE

We get 4 blocks:

* block #1 is the start block and ends with ``POP_JUMP_IF_FALSE`` conditional
  jump and is followed by the block #2
* block #2 ends with ``JUMP_FORWARD`` uncondition jump
* block #3 does not contain jump and is followed by the block #4
* block #4 is the final block

The start block is always the first block.


Analyze the control flow graph
==============================

The ``bytecode`` module provides two ways to iterate on blocks:

* iterate on the basic block as a sequential list
* browse the graph by following jumps and links to next blocks

Iterate on basic blocks
-----------------------

Iterating on basic blocks is a simple as this loop::

    for block in blocks:
        ...

Example of a ``display_blocks()`` function::

    from bytecode import UNSET, Label, Instr, Bytecode, BasicBlock, ControlFlowGraph

    def display_blocks(blocks):
        for block in blocks:
            print("Block #%s" % (1 + blocks.get_block_index(block)))
            for instr in block:
                if isinstance(instr.arg, BasicBlock):
                    arg = "<block #%s>" % (1 + blocks.get_block_index(instr.arg))
                elif instr.arg is not UNSET:
                    arg = repr(instr.arg)
                else:
                    arg = ''
                print("    %s %s" % (instr.name, arg))

            if block.next_block is not None:
                print("    => <block #%s>"
                      % (1 + blocks.get_block_index(block.next_block)))

            print()

    label_else = Label()
    label_print = Label()
    bytecode = Bytecode([Instr('LOAD_NAME', 'print'),
                         Instr('LOAD_NAME', 'test'),
                         Instr('POP_JUMP_IF_FALSE', label_else),
                             Instr('LOAD_CONST', 'yes'),
                             Instr('JUMP_FORWARD', label_print),
                         label_else,
                             Instr('LOAD_CONST', 'no'),
                         label_print,
                             Instr('CALL_FUNCTION', 1),
                         Instr('LOAD_CONST', None),
                         Instr('RETURN_VALUE')])

    blocks = ControlFlowGraph.from_bytecode(bytecode)
    display_blocks(blocks)

Output::

    Block #1
        LOAD_NAME 'print'
        LOAD_NAME 'test'
        POP_JUMP_IF_FALSE <block #3>
        => <block #2>

    Block #2
        LOAD_CONST 'yes'
        JUMP_FORWARD <block #4>

    Block #3
        LOAD_CONST 'no'
        => <block #4>

    Block #4
        CALL_FUNCTION 1
        LOAD_CONST None
        RETURN_VALUE

.. note::
   :class:`SetLineno` is not handled in the example to keep it simple.


Browse the graph
----------------

Recursive function is a simple solution to browse the control flow graph.

Example to a recursive ``display_block()`` function::

    from bytecode import UNSET, Label, Instr, Bytecode, BasicBlock, ControlFlowGraph

    def display_block(blocks, block, seen=None):
        # avoid loop: remember which blocks were already seen
        if seen is None:
            seen = set()
        if id(block) in seen:
            return
        seen.add(id(block))

        # display instructions of the block
        print("Block #%s" % (1 + blocks.get_block_index(block)))
        for instr in block:
            if isinstance(instr.arg, BasicBlock):
                arg = "<block #%s>" % (1 + blocks.get_block_index(instr.arg))
            elif instr.arg is not UNSET:
                arg = repr(instr.arg)
            else:
                arg = ''
            print("    %s %s" % (instr.name, arg))

        # is the block followed directly by another block?
        if block.next_block is not None:
            print("    => <block #%s>"
                  % (1 + blocks.get_block_index(block.next_block)))

        print()

        # display the next block
        if block.next_block is not None:
            display_block(blocks, block.next_block, seen)

        # display the block linked by jump (if any)
        target_block = block.get_jump()
        if target_block is not None:
            display_block(blocks, target_block, seen)

    label_else = Label()
    label_print = Label()
    bytecode = Bytecode([Instr('LOAD_NAME', 'print'),
                         Instr('LOAD_NAME', 'test'),
                         Instr('POP_JUMP_IF_FALSE', label_else),
                             Instr('LOAD_CONST', 'yes'),
                             Instr('JUMP_FORWARD', label_print),
                         label_else,
                             Instr('LOAD_CONST', 'no'),
                         label_print,
                             Instr('CALL_FUNCTION', 1),
                         Instr('LOAD_CONST', None),
                         Instr('RETURN_VALUE')])

    blocks = ControlFlowGraph.from_bytecode(bytecode)
    display_block(blocks, blocks[0])

Output::

    Block #1
        LOAD_NAME 'print'
        LOAD_NAME 'test'
        POP_JUMP_IF_FALSE <block #3>
        => <block #2>

    Block #2
        LOAD_CONST 'yes'
        JUMP_FORWARD <block #4>

    Block #4
        CALL_FUNCTION 1
        LOAD_CONST None
        RETURN_VALUE

    Block #3
        LOAD_CONST 'no'
        => <block #4>

Block numbers are no displayed in the sequential order: block #4 is displayed
before block #3.

.. note::
   Dead code (unreachable blocks) is not displayed by ``display_block``.

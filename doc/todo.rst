TODO list
=========

* Compute the stack size of an overall bytecode object: Bytecode.to_concrete_bytecode()
* Add stack effect: use ``opcode.stack_effect(opcode)``
* Add instruction constants/enums? ex:
  ``bytecode.instructions.LOAD_CONST("text", lineno=3)``
* Nicer API for function arguments? Bytecode has argcount, kwonlyargcount and
  argnames. 4 types of parameters: indexed, ``*args``, ``**kwargs`` and ``*,
  kwonly=3``. See inspect.signature()

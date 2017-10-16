TODO list
=========

* Remove Bytecode.cellvars and Bytecode.freevars?
* Remove Bytecode.first_lineno? Compute it on conversions.
* Add instruction constants/enums? Example::

    from bytecode import instructions as i

    bytecode = Bytecode([i.LOAD_NAME('print'),
                         i.LOAD_CONST('Hello World!'),
                         i.CALL_FUNCTION(1),
                         i.POP_TOP(),
                         i.LOAD_CONST(None),
                         i.RETURN_VALUE()])

  Should we support instructions without parenthesis for instruction with no
  parameter? Example with POP_TOP and RETURN_VALUE::

    from bytecode import instructions as i

    bytecode = Bytecode([i.LOAD_NAME('print'),
                         i.LOAD_CONST('Hello World!'),
                         i.CALL_FUNCTION(1),
                         i.POP_TOP,
                         i.LOAD_CONST(None),
                         i.RETURN_VALUE])


* Nicer API for function arguments in bytecode object? Bytecode has argcount,
  kwonlyargcount and argnames. 4 types of parameters: indexed, ``*args``,
  ``**kwargs`` and ``*, kwonly=3``. See inspect.signature()

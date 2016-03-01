********
bytecode
********

``bytecode`` is a Python module to generate and modify bytecode.

* `bytecode project homepage at GitHub
  <https://github.com/haypo/bytecode>`_ (code, bugs)
* `bytecode documentation
  <https://bytecode.readthedocs.org/>`_
* `Download latest bytecode release at the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/bytecode>`_

Install bytecode: ``python3 -m pip install bytecode``. It requires Python 3.4
or newer.

Example executing ``print('Hello World!')``::

    from bytecode import Instr, Bytecode

    bytecode = Bytecode([Instr("LOAD_NAME", 'print'),
                         Instr("LOAD_CONST", 'Hello World!'),
                         Instr("CALL_FUNCTION", 1),
                         Instr("POP_TOP"),
                         Instr("LOAD_CONST", None),
                         Instr("RETURN_VALUE")])
    code = bytecode.to_code()
    exec(code)

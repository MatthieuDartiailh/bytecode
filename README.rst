********
bytecode
********

.. image:: https://img.shields.io/pypi/v/bytecode.svg
   :alt: Latest release on the Python Cheeseshop (PyPI)
   :target: https://pypi.python.org/pypi/bytecode

.. image:: https://img.shields.io/travis/vstinner/bytecode/master.svg
   :alt: Build status of bytecode on Travis CI
   :target: https://travis-ci.org/vstinner/bytecode

.. image:: https://img.shields.io/codecov/c/github/vstinner/bytecode/master.svg
   :alt: Code coverage of bytecode on codecov.io
   :target: https://codecov.io/github/vstinner/bytecode

``bytecode`` is a Python module to generate and modify bytecode.

* `bytecode project homepage at GitHub
  <https://github.com/vstinner/bytecode>`_ (code, bugs)
* `bytecode documentation
  <https://bytecode.readthedocs.io/>`_
* `Download latest bytecode release at the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/bytecode>`_

Install bytecode: ``python3 -m pip install bytecode``. It requires Python 3.4
or newer.

Example executing ``print('Hello World!')``:

.. code:: python

    from bytecode import Instr, Bytecode

    bytecode = Bytecode([Instr("LOAD_NAME", 'print'),
                         Instr("LOAD_CONST", 'Hello World!'),
                         Instr("CALL_FUNCTION", 1),
                         Instr("POP_TOP"),
                         Instr("LOAD_CONST", None),
                         Instr("RETURN_VALUE")])
    code = bytecode.to_code()
    exec(code)

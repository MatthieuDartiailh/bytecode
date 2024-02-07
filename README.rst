********
bytecode
********

.. image:: https://img.shields.io/pypi/v/bytecode.svg
   :alt: Latest release on the Python Cheeseshop (PyPI)
   :target: https://pypi.python.org/pypi/bytecode

.. image:: https://github.com/MatthieuDartiailh/bytecode/workflows/Continuous%20Integration/badge.svg
    :target: https://github.com/MatthieuDartiailh/bytecode/actions
    :alt: Continuous integration

.. image:: https://github.com/MatthieuDartiailh/bytecode/workflows/Documentation%20building/badge.svg
    :target: https://github.com/MatthieuDartiailh/bytecode/actions
    :alt: Documentation building

.. image:: https://img.shields.io/codecov/c/github/MatthieuDartiailh/bytecode/master.svg
   :alt: Code coverage of bytecode on codecov.io
   :target: https://codecov.io/github/MatthieuDartiailh/bytecode

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Ruff

``bytecode`` is a Python module to generate and modify bytecode.

* `bytecode project homepage at GitHub
  <https://github.com/MatthieuDartiailh/bytecode>`_ (code, bugs)
* `bytecode documentation
  <https://bytecode.readthedocs.io/>`_
* `Download latest bytecode release at the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/bytecode>`_

Install bytecode: ``python3 -m pip install bytecode``. It requires Python 3.8
or newer. The latest release that supports Python 3.7 and 3.6 is 0.13.0.
The latest release that supports Python 3.5 is 0.12.0. For Python 2.7 support,
have a look at `dead-bytecode <https://github.com/p403n1x87/dead-bytecode>`_
instead.

Example executing ``print('Hello World!')``:

.. code:: python

    from bytecode import Instr, Bytecode

    bytecode = Bytecode([Instr("LOAD_GLOBAL", (True, 'print')),
                         Instr("LOAD_CONST", 'Hello World!'),
                         Instr("CALL", 1),
                         Instr("POP_TOP"),
                         Instr("LOAD_CONST", None),
                         Instr("RETURN_VALUE")])
    code = bytecode.to_code()
    exec(code)

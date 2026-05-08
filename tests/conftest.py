import bytecode


def pytest_report_header():
    import importlib.util

    spec = importlib.util.find_spec("bytecode.concrete")
    kind = "pure-Python" if (spec and spec.origin and spec.origin.endswith(".py")) else "Cython"
    return f"bytecode: {kind} build ({bytecode.__file__})"

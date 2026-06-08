def pytest_report_header():
    import importlib.util

    spec = importlib.util.find_spec("bytecode.concrete")
    is_pure = spec and spec.origin and spec.origin.endswith(".py")
    kind = "pure-Python" if is_pure else "Cython"
    return f"bytecode: {kind} build"

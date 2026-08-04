"""Round-trip decompile/recompile benchmarks.

Run with:  pytest tests/test_bench_roundtrip.py --benchmark-compare
"""

import types

import pytest

from bytecode import Bytecode


def _collect_code_objects(root: types.CodeType, depth: int = 1) -> list[types.CodeType]:
    result = [root]
    if depth > 0:
        for const in root.co_consts:
            if isinstance(const, types.CodeType):
                result.extend(_collect_code_objects(const, depth - 1))
    return result


def _dis_corpus() -> list[types.CodeType]:
    import importlib.util

    spec = importlib.util.find_spec("dis")
    assert spec and spec.origin
    src = open(spec.origin).read()
    top = compile(src, spec.origin, "exec")
    return _collect_code_objects(top)


_CORPUS = _dis_corpus()


@pytest.fixture(params=_CORPUS, ids=[c.co_name for c in _CORPUS])
def code_object(request):
    return request.param


def test_roundtrip(benchmark, code_object):
    def roundtrip():
        Bytecode.from_code(code_object).to_code()

    benchmark(roundtrip)

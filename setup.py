import os

from setuptools import setup  # isort: skip

from pathlib import Path

import Cython.Distutils
from Cython.Build import cythonize  # noqa: I100

ROOT = Path(__file__).parent / "src"


# Get all the py files under the src folder
def get_py_files(path):
    return [
        p.relative_to(ROOT) for p in Path(path).rglob("*.py") if p.name != "__init__.py"
    ]


def pretend_cython():
    return [
        Cython.Distutils.Extension(
            str(p.with_suffix("")).replace(os.sep, "."),
            sources=[str(Path("src") / p)],
            language="c",
        )
        for p in get_py_files(ROOT)
    ]


_pure_python = os.getenv("BYTECODE_PURE_PYTHON")
print(f"bytecode: building {'pure-Python' if _pure_python else 'Cython'} version")

# Always include .pyi stubs; also include .pxd declaration files in Cython
# builds so downstream Cython users can cimport from bytecode.
_package_data: dict = {"bytecode": ["*.pyi"]}
if not _pure_python:
    _package_data["bytecode"].append("*.pxd")

setup(
    name="bytecode",
    setup_requires=["setuptools_scm[toml]>=4"] + ([] if _pure_python else ["cython"]),
    package_data=_package_data,
    ext_modules=[] if _pure_python else cythonize(
        pretend_cython(),
        force=True,
        compiler_directives={
            "language_level": "3",
            "annotation_typing": False,
        },
    ),
)

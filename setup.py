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


setup(
    name="bytecode",
    setup_requires=["setuptools_scm[toml]>=4", "cython", "cmake>=3.24.2,<3.28"],
    ext_modules=cythonize(
        pretend_cython(),
        force=True,
        compiler_directives={
            "language_level": "3",
            "annotation_typing": False,
        },
    ),
)

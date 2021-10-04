#!/usr/bin/env python3

# Prepare a release:
#
#  - git pull --rebase
#  - update version in setup.py, bytecode/__init__.py and doc/conf.py
#  - run tests: tox
#  - set release date in the changelog
#  - git commit -a
#  - git push
#  - check GHA CI status:
#    https://github.com/MatthieuDartiailh/bytecode/actions
#
# Release a new version:
#
#  - git tag VERSION
#  - git push --tags
#  - rm -rf dist/
#  - python3 setup.py sdist bdist_wheel
#  - twine upload dist/*
#
# After the release:
#
#  - set version to n+1
#  - git commit -a -m "post-release"
#  - git push

VERSION = "0.13.0"

DESCRIPTION = "Python module to generate and modify bytecode"
CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Natural Language :: English",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Topic :: Software Development :: Libraries :: Python Modules",
]

# put most of the code inside main() to be able to import setup.py in
# test_bytecode.py, to ensure that VERSION is the same than
# bytecode.__version__.


def main():
    try:
        from setuptools import setup
    except ImportError:
        from distutils.core import setup

    with open("README.rst") as fp:
        long_description = fp.read().strip()

    options = {
        "name": "bytecode",
        "version": VERSION,
        "license": "MIT license",
        "description": DESCRIPTION,
        "long_description": long_description,
        "url": "https://github.com/MatthieuDartiailh/bytecode",
        "author": "Victor Stinner",
        "author_email": "victor.stinner@gmail.com",
        "maintainer": "Matthieu C. Dartiailh",
        "maintainer_email": "m.dartiailh@gmail.com",
        "classifiers": CLASSIFIERS,
        "packages": ["bytecode", "bytecode.tests"],
        "python_requires": ">=3.6",
    }
    setup(**options)


if __name__ == "__main__":
    main()

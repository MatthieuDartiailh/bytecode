#!/usr/bin/env python3

# Prepare a release:
#
#  - git pull --rebase
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
#
# After the release:
#
#  - set version to n+1
#  - git commit -a -m "post-release"
#  - git push

from setuptools import setup

if __name__ == "__main__":
    setup()

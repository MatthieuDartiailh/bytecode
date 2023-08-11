#!/bin/bash -eu

set -e
set -u

PREFIX=${1}-${2}
PY=${2}

# Clone boto3
test -d ${PREFIX}/boto3 || git clone --depth=1 https://github.com/boto/boto3.git ${PREFIX}/boto3

# Create venv
python$PY -m venv ${PREFIX}/.venv
source ${PREFIX}/.venv/bin/activate

# Install bytecode
pip install setuptools wheel
pip install -e .

# Install dependencies
cd ${PREFIX}/boto3
    python scripts/ci/install
cd -

deactivate

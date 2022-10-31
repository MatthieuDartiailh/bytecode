#!/bin/bash -eu

set -e
set -u

PREFIX=${1}-${2}
PY=${2}

cd ${PREFIX}/boto3
    source ${PREFIX}/.venv/bin/activate
    python scripts/ci/run-tests
    deactivate
cd -

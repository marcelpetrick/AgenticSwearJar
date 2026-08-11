#!/usr/bin/env bash
set -euo pipefail
export GIT_PAGER=cat

python3 -m unittest discover -v
shellcheck ./*.sh
ruff check .
ruff format --check .
mypy
git --no-pager diff --no-ext-diff --check

printf '\nLocal pipeline passed.\n'
exit 0

#!/usr/bin/env bash
set -euo pipefail

python3 -m unittest discover -v
shellcheck ./*.sh
ruff check .
ruff format --check .
mypy
git diff --check

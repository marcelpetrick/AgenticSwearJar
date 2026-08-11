#!/usr/bin/env bash
set -euo pipefail

python3 -m unittest discover -v
ruff check .
ruff format --check .
mypy
git diff --check

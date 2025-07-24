#!/usr/bin/env bash
set -euo pipefail

python -m build

twine upload -u keytonweissinger@gmail.com dist/*

#!/bin/sh
set -eu

cd "$(dirname "$0")"

# Build and validate locally; publishing is a separate, explicit action.
python3 -m build
python3 -m twine check dist/*

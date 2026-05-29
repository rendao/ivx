#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
VENV_PY="$PROJECT_ROOT/.venv/bin/python"

cd "$PROJECT_ROOT" || exit 1
if [ -x "$VENV_PY" ]; then
	"$VENV_PY" scripts/workflow.py "$@"
else
	python scripts/workflow.py "$@"
fi

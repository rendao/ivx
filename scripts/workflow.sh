#!/usr/bin/env sh
set -eu

if [ "$#" -eq 0 ]; then
	echo "Usage:"
	echo "  sh scripts/workflow.sh local"
	echo "  sh scripts/workflow.sh weekly-trend --samples 3"
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
VENV_PY="$PROJECT_ROOT/.venv/bin/python"

cd "$PROJECT_ROOT" || exit 1
if [ -x "$VENV_PY" ]; then
	"$VENV_PY" scripts/workflow.py "$@"
else
	python scripts/workflow.py "$@"
fi

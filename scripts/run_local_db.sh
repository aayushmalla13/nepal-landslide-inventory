#!/usr/bin/env bash
# Run any pipeline command using the active SQLite database.
# The historical script name is retained for command compatibility. The
# default database is now the uncompressed copy inside the Box workspace;
# LS_SQLITE_PATH can still override it explicitly when needed.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOX_DB_PATH="$PROJECT_ROOT/data/raw_sqlite/landslide_inventory.sqlite"
ACTIVE_DB_PATH="${LS_SQLITE_PATH:-$BOX_DB_PATH}"
if [[ ! -f "$ACTIVE_DB_PATH" ]]; then
  echo "SQLite database not found: $ACTIVE_DB_PATH" >&2
  exit 1
fi
export LS_SQLITE_PATH="$ACTIVE_DB_PATH"
cd "$PROJECT_ROOT"
# Prevent an inherited PYTHONPATH or relative interpreter from selecting an
# older clone of this repository.
unset PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT/src"
if [[ "$1" == ".venv/bin/python" ]]; then
  set -- "$PROJECT_ROOT/.venv/bin/python" "${@:2}"
fi
exec "$@"

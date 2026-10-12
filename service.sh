#!/bin/sh
set -eu
here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x "$here/.venv/bin/python" ]; then
    echo "Environment missing. Run ./setup.sh first." >&2
    exit 1
fi
exec "$here/.venv/bin/python" "$here/scripts/service.py" "$@"

#!/bin/sh
set -eu
here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$here"
if [ ! -x .venv/bin/litellm ]; then
    echo "Environment missing. Run ./setup.sh first." >&2
    exit 1
fi
if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi
export LITELLM_REQUEST_LOG="${LITELLM_REQUEST_LOG:-$here/logs/requests.jsonl}"
export PYTHONPATH="$here${PYTHONPATH:+:$PYTHONPATH}"
exec "$here/.venv/bin/litellm" --config "$here/config.yaml" \
    --host "${LITELLM_BIND_HOST:-127.0.0.1}" --port "${LITELLM_PORT:-4000}" "$@"

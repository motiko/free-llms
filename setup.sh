#!/bin/sh
# Install a checkout-local environment without changing shell profiles.
set -eu
here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$here"
export UV_CACHE_DIR="$here/.tools/cache"
export UV_PYTHON_INSTALL_DIR="$here/.tools/python"
export UV_PROJECT_ENVIRONMENT="$here/.venv"

if [ -x "$here/.tools/bin/uv" ]; then
    uv_bin="$here/.tools/bin/uv"
elif command -v uv >/dev/null 2>&1; then
    uv_bin="$(command -v uv)"
else
    mkdir -p "$here/.tools/bin"
    echo "Installing uv into .tools/bin (requires curl and internet access)..."
    curl -LsSf https://astral.sh/uv/install.sh -o "$here/.tools/install-uv.sh"
    UV_UNMANAGED_INSTALL="$here/.tools/bin" sh "$here/.tools/install-uv.sh"
    uv_bin="$here/.tools/bin/uv"
fi

"$uv_bin" sync --locked
if [ ! -e .env ]; then
    (umask 077; set -C; cat .env.example > .env)
    echo "Created .env; add your provider API keys before starting the proxy."
fi
mkdir -p logs
printf '\nEnvironment ready. Start with ./run.sh, or ./service.sh start on macOS.\n'

#!/bin/zsh
# LiteLLM router. Put secrets (e.g. ANTHROPIC_API_KEY=sk-ant-...) in ~/litellm/.env
[ -f "$HOME/litellm/.env" ] && set -a && source "$HOME/litellm/.env" && set +a
exec "$HOME/.local/bin/litellm" --config "$HOME/litellm/config.yaml" --host 0.0.0.0 --port 4000

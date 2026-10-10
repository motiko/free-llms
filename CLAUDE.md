# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A LiteLLM proxy configuration, not an application codebase. The only files that matter are
`config.yaml` (model list + routing), `run.sh` (launcher), and `.env` (provider API keys, never commit).
`config.local.yaml` (gitignored) holds the disabled local-model entries.
`config.yaml.bak-*` files are manual backups taken before edits; keep making one before rewriting the config.
`bench/bench.py` benchmarks every model through the proxy (see the `bench` skill); results live in `bench/results/`.
`claude-free` launches Claude Code against the proxy at `http://$LITELLM_HOST:4000` (`LITELLM_HOST` from the env or `.env`,
default localhost; main model `smart`, Haiku slot `fast`; override with `CLAUDE_FREE_MODEL=code`).

## How the proxy runs

- It is a **launchd daemon** with `KeepAlive`: `/Library/LaunchDaemons/com.local.litellm.plist` runs `run.sh`,
  which sources `.env` and execs `~/.local/bin/litellm --config ~/litellm/config.yaml --host 0.0.0.0 --port 4000`.
- **Restart = kill the process.** launchd relaunches it within ~1s with the current config:
  `pkill -f "bin/litellm"`. Do not start a second instance manually; it will fight over port 4000.
- Logs (stdout+stderr): `~/llm/logs/litellm.log`.
- Clients authenticate with the `master_key` from `general_settings` (`sk-local-anything`).
- LiteLLM is installed as a `uv` tool. Its interpreter (which has `pyyaml` and `litellm`; system python does not)
  is `~/.local/share/uv/tools/litellm/bin/python`.

## Validating and testing config changes

Offline check (parses YAML and builds the Router without network calls):

```sh
cd ~/litellm; set -a; source .env; set +a
~/.local/share/uv/tools/litellm/bin/python - <<'PY'
import yaml; from litellm import Router
cfg = yaml.safe_load(open('config.yaml'))
r = Router(model_list=cfg['model_list'], **cfg['router_settings'])
print(sorted(r.get_model_names()))
PY
```

Live checks after a restart:

```sh
curl -s -H "Authorization: Bearer sk-local-anything" http://localhost:4000/v1/models
curl -s http://localhost:4000/v1/chat/completions -H "Authorization: Bearer sk-local-anything" \
  -H "Content-Type: application/json" \
  -d '{"model":"fast","max_tokens":64,"messages":[{"role":"user","content":"Reply with OK"}]}'
```

`gpt-oss` models spend tokens on reasoning first; a smoke test with `max_tokens` below ~30 returns an empty reply.

## Routing structure in config.yaml

- **Naming:** every `model_name` follows `provider-model-size` (e.g. `groq-gptoss-120b`, `google-gemini-flashlite`,
  `local-gemma-4b`). Model tokens are collapsed to one word (`gptoss`, `flashlite`). Keep this when adding models.
- **Providers:** Google AI Studio (`google-*`, `GEMINI_API_KEY`), Groq (`groq-*`, `GROQ_API_KEY`),
  Ollama Cloud (`ollama-*`, OpenAI-compatible at `https://ollama.com/v1`, `OLLAMA_API_KEY`),
  OpenRouter (`openrouter-*`, `OPENROUTER_API_KEY`; free-tier `:free` models, rate limited and the
  free list changes often; `openrouter-glm-flash` is paid, there is no free GLM there),
  Z.ai (`zai-*`, `ZAI_API_KEY`; the GLM `*-Flash` models are free, GLM 5.x is paid),
  Mistral (`mistral-*`, `MISTRAL_API_KEY`; free tier covers Codestral and Ministral only, Small/Medium 429),
  NVIDIA NIM (`nvidia-*`, `NVIDIA_API_KEY`; ~40 req/min, has the full GLM 5.3 and the embedding model `nvidia-nemotron-embed`).
- **Role aliases** (`router_settings.model_group_alias`): `smart`, `fast`, `code`, `cheap`, `embed`.
  Clients should prefer aliases over provider names.
- **Fallbacks** are defined for every model *and* every alias, because LiteLLM looks up fallbacks by the
  name the client sent, not the alias target. When adding a model, add it to both lists.
- **Local models** (`local-*`, `agent-remote`) live commented out in `config.local.yaml` (gitignored, not in the
  repo), together with their fallback rules. They target machines `mlx-host.local` (M5 Pro, mlx_lm), `ollama-host.local` (M3 Pro, Ollama) and `localhost`
  (M1, llama-server). `enable_tag_filtering` and the `from-ollama-host`/`from-mlx-host` tags exist only for `agent-remote`.
  With local models disabled the only embedding model is `nvidia-nemotron-embed`.

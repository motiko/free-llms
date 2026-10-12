# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A LiteLLM proxy configuration, not an application codebase. The only files that matter are
`config.yaml` (model list + routing), `run.sh` (launcher), and `.env` (provider API keys, never commit).
`config.local.yaml` (gitignored) holds the disabled local-model entries.
`config.yaml.bak-*` files are manual backups taken before edits; keep making one before rewriting the config.
`bench/bench.py` benchmarks every model through the proxy (see the `bench` skill); results live in `bench/results/`.
`request_log.py` is a LiteLLM callback (registered in `litellm_settings.callbacks`) that appends one JSON line per
request to `logs/requests.jsonl`: alias asked for, deployment/provider that served it, tokens, cost, latency,
fallback count, errors. Fallback chains share one `call_id`; a restart is needed after editing the callback.
`./reqlog` queries that log (`reqlog -h`): `models`, `aliases`, `fallbacks`, `latency`, `errors`, `rate`, `cost`, `quota` (live
provider quota probe), with `--since 24h`, `--alias`, `--model`, `--provider` filters. Known daily caps live in its `DAILY_CAPS`.
`claude-free` launches Claude Code against the proxy at `http://$LITELLM_HOST:4000` (`LITELLM_HOST` from the env or `.env`,
default localhost; main model `smart`, Haiku slot `fast`; override with `CLAUDE_FREE_MODEL=code`).

## How the proxy runs

- Run `./setup.sh` from any checkout to sync locked dependencies into `.venv` and create `.env`
  if missing. uv and managed Python downloads/cache stay in `.tools`; existing credentials are preserved.
- `run.sh` resolves its own directory, sources that checkout's `.env`, and starts `.venv/bin/litellm`
  with the adjacent `config.yaml`. It defaults to `127.0.0.1:4000`; configure `LITELLM_BIND_HOST` and
  `LITELLM_PORT` in `.env` for another listener.
- Use `./service.sh start` for the macOS user LaunchAgent with startup at login; `stop` also disables
  login startup, and `restart` reloads configuration. Inspect `status` and `logs`; `uninstall` preserves
  credentials and logs. Do not start a second instance on the same port. A legacy system daemon must
  be stopped separately before switching. See README.md.
- Request logs: `logs/requests.jsonl` in the checkout, overridable with `LITELLM_REQUEST_LOG`.
  Daemon stdout/stderr: `logs/litellm.log`.
- Clients authenticate with the `master_key` in `general_settings` (default `sk-local-anything`).
- Run Python utilities with `.venv/bin/python`; no globally installed LiteLLM tool is required.

## Validating and testing config changes

Offline check (parses YAML and builds the Router without network calls):

```sh
set -a; source .env; set +a
.venv/bin/python - <<'PY'
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
  The 2026-10-12 benchmark excludes exhausted Ollama deployments from automatic fallback targets;
  revalidate after monthly quota renewal before restoring them. The agentic code chain uses
  Ministral 14B instead of Codestral because Codestral repeatedly missed the tool-call probe.
- **Fallbacks** are defined for every model *and* every alias, because LiteLLM looks up fallbacks by the
  name the client sent, not the alias target. When adding a model, add it to both lists.
- **Local models** (`local-*`, `agent-remote`) live commented out in `config.local.yaml` (gitignored, not in the
  repo), together with their fallback rules. They target machines `mlx-host.local` (M5 Pro, mlx_lm), `ollama-host.local` (M3 Pro, Ollama) and `localhost`
  (M1, llama-server). `enable_tag_filtering` and the `from-ollama-host`/`from-mlx-host` tags exist only for `agent-remote`.
  With local models disabled the only embedding model is `nvidia-nemotron-embed`.

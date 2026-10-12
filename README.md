# litellm-free-router

A [LiteLLM](https://docs.litellm.ai/) proxy config that fronts the **free tiers of seven LLM providers** behind one
OpenAI-compatible (and Anthropic-compatible) endpoint, with role aliases and benchmark-ordered fallback chains.
Point Claude Code, Cursor, aider or any SDK at `http://localhost:4000`, ask for `smart`, `fast`, `code`, `cheap`
or `embed`, and the proxy picks a working free model and fails over when a provider throttles you.

Everything here is free-tier only (one paid entry is clearly marked). It is meant for small tasks and
experiments, not production.

## Providers and models

| Prefix | Provider | Free tier (checked Oct 2026) | Models |
|---|---|---|---|
| `groq-*` | Groq | generous, no card | gpt-oss 120B / 20B, Qwen 3.8 27B |
| `google-*` | Google AI Studio | Flash-Lite ~500 req/day | Gemini 3.5 Flash-Lite, Gemma 4 31B / 26B |
| `ollama-*` | Ollama Cloud | plan dependent | gpt-oss 120B, Gemma 4 31B |
| `nvidia-*` | NVIDIA NIM | ~40 req/min, no card | GLM 5.3, GLM 5.3 Flash, Nemotron 3 550B / 120B / Lightning, Gemma 4 31B, gpt-oss 20B, Nemotron Embed |
| `mistral-*` | Mistral | 750 req/min, 1.3M tok/min, data-training opt-in | Codestral, Ministral 14B / 8B / 3B |
| `zai-*` | Z.ai | free Flash models, 1 concurrent request | GLM 4.7 / 4.5 / 4.6V Flash |
| `openrouter-*` | OpenRouter `:free` | ~50 req/day (1000 with $10 credit) | Nemotron 3, Ling 3.1 Flash, North Mini Code, Laguna, Apodex, dots, plus the `openrouter/free` auto-router. `openrouter-glm-flash` is **paid** |

Naming is `provider-model-size` (`groq-gptoss-120b`, `nvidia-glm-53`). See the comments in `config.yaml` for the
quirks of each provider and the models that were tried and rejected.

## Aliases and fallback chains

| Alias | Target | Falls back to |
|---|---|---|
| `smart` | Groq gpt-oss 120B | NVIDIA Nemotron 120B, NVIDIA GLM 5.3, Nemotron 550B, Groq Qwen, ... |
| `fast` | Groq gpt-oss 20B | Gemini Flash-Lite, Ministral 14B, NVIDIA Nemotron 120B, ... |
| `code` | Groq Qwen 3.8 27B | NVIDIA GLM 5.3, Z.ai GLM 4.7 Flash, Groq gpt-oss 120B, Ministral 14B, ... |
| `cheap` | Gemini 3.5 Flash-Lite | Ministral 8B, Groq gpt-oss 20B, Ministral 3B, ... |
| `embed` | NVIDIA Nemotron 3 Embed 1B (2048 dims) | none |

Ollama deployments remain available for direct requests, but are temporarily excluded from automatic
fallback targets after this account reached its monthly quota on 2026-10-12. Restore them after quota
renews and a successful recheck. Codestral remains available directly; the `code` chain uses models
that passed the tool-call probe.

Every model and every alias has its own fallback list because LiteLLM looks fallbacks up by the name the client
sent, not by the alias target. Chains are ordered by the benchmark below.

## Setup

```sh
git clone https://github.com/motiko/free-llms.git
cd free-llms
./setup.sh
# Fill in provider API keys in .env, then:
./run.sh
```

`./setup.sh` works on macOS and Linux with `sh`, `curl`, and internet access. It uses an existing
`uv` or downloads it into `.tools/bin`, installs Python 3.12 if needed, and syncs the locked dependencies
into `.venv`. It creates `.env` only when absent and keeps logs in `logs/`. No activation or global
Python packages are needed. Run setup again after pulling dependency changes. Provider keys must still
be supplied by you; remove unconfigured provider entries as described in `.env.example`.

The checkout can live anywhere. Launchers resolve paths from their own location, even when called
from another directory. The listener defaults to `127.0.0.1:4000`; set `LITELLM_BIND_HOST=0.0.0.0`
and optionally `LITELLM_PORT` in `.env` for remote access. `LITELLM_REQUEST_LOG` overrides the log path.

Change `general_settings.master_key` in `config.yaml` if the proxy is reachable from other machines. Clients send
it as their API key.

Offline validation (no network, catches YAML and fallback typos):

```sh
set -a; source .env; set +a
.venv/bin/python - <<'PY'
import yaml; from litellm import Router
cfg = yaml.safe_load(open('config.yaml'))
r = Router(model_list=cfg['model_list'], **cfg['router_settings'])
print(sorted(r.get_model_names()))
PY
```

Smoke test:

```sh
curl -s http://localhost:4000/v1/chat/completions -H "Authorization: Bearer sk-local-anything" \
  -H "Content-Type: application/json" \
  -d '{"model":"fast","max_tokens":200,"messages":[{"role":"user","content":"Reply with OK"}]}'
```

Reasoning models (gpt-oss, GLM, Nemotron) spend output tokens on thinking first; a `max_tokens` below ~100 can
return an empty reply.

### Run in the background on macOS

After setup and adding your provider keys, run:

```sh
./service.sh start       # install the user LaunchAgent, start now, and enable login startup
./service.sh status      # show launchd state, PID, and last exit code
./service.sh logs        # follow stdout/stderr; Ctrl-C only stops the log viewer
./service.sh restart     # apply config, .env, or callback changes
./service.sh stop        # stop now and disable login startup until the next start
./service.sh uninstall   # remove the LaunchAgent; preserve .env, .venv, and logs
```

`./service.sh install` is an alias for `start`. These commands use your macOS login session and require
no sudo. The generated `~/Library/LaunchAgents/com.motiko.free-llms.plist` points to this checkout,
handles spaces/XML characters in paths, and keeps the process running after you close Terminal.
It starts when you log in; it does not run before login or while the Mac is asleep. macOS uses
[launchd to manage user agents](https://support.apple.com/en-ca/guide/terminal/apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac).

Service output goes to `logs/litellm.log`; request records remain in `logs/requests.jsonl`.
`start` is safe to repeat; `restart` explicitly replaces the running process. If the checkout is moved,
uninstall from the original location before moving, then rerun setup/start at the new location.
One checkout can own this user service at a time. Stop any manually started proxy or legacy
`com.local.litellm` system daemon on the same port before starting the user service.

The optional `com.local.litellm.plist.example` remains available for administrators who need a system
daemon before login. Replace its path/user placeholders before using it; it is separate from these commands.

## Using it with Claude Code

`claude-free` wraps Claude Code with the env vars that point it at the proxy. The host comes from `LITELLM_HOST`
(environment or `.env` next to the script, default `localhost`), the port from `LITELLM_PORT` (default 4000):

```sh
./claude-free                              # main model = smart, Haiku slot = fast
CLAUDE_FREE_MODEL=code ./claude-free       # or any model name the proxy lists
LITELLM_HOST=proxybox.local ./claude-free   # proxy on another machine
```

It sets `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, the model slots, and disables prompt caching and
non-essential traffic (no free provider honours Anthropic cache control, and the extra calls only burn quota).
Keep OpenRouter and Z.ai out of the main path for agentic use: one Claude Code turn can be 5 to 20 requests.
`litellm_settings.drop_params: true` strips parameters a provider rejects instead of failing the request.

## Benchmark

`bench/bench.py` runs three probes per model through the proxy: a tool call on the Anthropic `/v1/messages`
endpoint (the path Claude Code uses), a FizzBuzz code task whose output is executed, and a JSON output check. A
probe fails if the proxy had to fall back to another deployment, even when the final answer was right.

```sh
.venv/bin/python bench/bench.py                   # everything
.venv/bin/python bench/bench.py --skip openrouter-   # spare the OpenRouter quota
```

Results land in `bench/results/<timestamp>.md` and `.json`; `bench/results/NOTES.md` has the conclusions.
Latest run (`20261012-0239`): 28/33 models passed every probe (77/88 probes passed); the paid
OpenRouter GLM entry was excluded. Groq and Gemini Flash-Lite answered in under 1s; NVIDIA Nemotron
120B averaged 0.9s. Ollama quota was exhausted, Codestral missed the tool call, Laguna XS hit an
upstream rate limit, and NVIDIA Gemma timed out at 150s on all probes. Google Gemma passed but
averaged 81s. The `embed` alias passed a separate 2048-dimension check.

If you use Claude Code, `.claude/skills/bench/SKILL.md` lets it run and interpret the benchmark with `/bench`.

## Layout

```
config.yaml                     model list, aliases, fallbacks
setup.sh                        installs the checkout-local environment
pyproject.toml / uv.lock        dependencies and reproducible versions
run.sh                          sources .env, starts the proxy
service.sh / scripts/service.py macOS background service commands
.env.example                    provider keys template
claude-free                     Claude Code launcher
bench/bench.py                  benchmark script
bench/results/                  benchmark history + NOTES.md
.claude/skills/bench/SKILL.md   Claude Code skill for the benchmark
com.local.litellm.plist.example launchd daemon
CLAUDE.md                       notes for Claude Code when editing this repo
```

Local models (`local-*`, `agent-remote`) for machines on the LAN live commented out in `config.local.yaml`, which is gitignored.

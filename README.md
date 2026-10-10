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
| `smart` | Groq gpt-oss 120B | Ollama gpt-oss 120B, NVIDIA Nemotron 120B, NVIDIA GLM 5.3, Nemotron 550B, ... |
| `fast` | Groq gpt-oss 20B | Gemini Flash-Lite, Ministral 14B, NVIDIA Nemotron 120B, ... |
| `code` | Groq Qwen 3.8 27B | Ollama Gemma 31B, NVIDIA GLM 5.3, Z.ai GLM 4.7 Flash, Codestral, ... |
| `cheap` | Gemini 3.5 Flash-Lite | Ministral 8B, Groq gpt-oss 20B, Ministral 3B, ... |
| `embed` | NVIDIA Nemotron 3 Embed 1B (2048 dims) | none |

Every model and every alias has its own fallback list because LiteLLM looks fallbacks up by the name the client
sent, not by the alias target. Chains are ordered by the benchmark below.

## Setup

```sh
git clone <this repo> ~/litellm && cd ~/litellm
cp .env.example .env            # fill in the keys you have, delete config entries for the rest
uv tool install litellm[proxy]  # or pip install 'litellm[proxy]'
./run.sh                        # serves on 0.0.0.0:4000
```

Change `general_settings.master_key` in `config.yaml` if the proxy is reachable from other machines. Clients send
it as their API key.

Offline validation (no network, catches YAML and fallback typos):

```sh
set -a; source .env; set +a
~/.local/share/uv/tools/litellm/bin/python - <<'PY'
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

### Run as a macOS launchd daemon

`com.local.litellm.plist.example` runs `run.sh` with `KeepAlive`, so a restart is just killing the process:

```sh
sed "s#YOUR_USER#$USER#g" com.local.litellm.plist.example | sudo tee /Library/LaunchDaemons/com.local.litellm.plist
mkdir -p ~/llm/logs
sudo launchctl bootstrap system /Library/LaunchDaemons/com.local.litellm.plist
pkill -f "bin/litellm"     # restart after editing config.yaml; launchd relaunches it within ~1s
```

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
~/.local/share/uv/tools/litellm/bin/python bench/bench.py                   # everything
~/.local/share/uv/tools/litellm/bin/python bench/bench.py --skip openrouter-   # spare the OpenRouter quota
```

Results land in `bench/results/<timestamp>.md` and `.json`; `bench/results/NOTES.md` has the conclusions.
Headline from Oct 2026: Groq answers in under 1s, Ollama Cloud and NVIDIA Nemotron 120B in about 1s, GLM
models in 4 to 20s because of reasoning tokens, and Gemma 4 31B on Google and NVIDIA takes 30 to 130s per call
while the same model on Ollama Cloud takes under 1s.

If you use Claude Code, `.claude/skills/bench/SKILL.md` lets it run and interpret the benchmark with `/bench`.

## Layout

```
config.yaml                     model list, aliases, fallbacks
run.sh                          sources .env, starts the proxy
.env.example                    provider keys template
claude-free                     Claude Code launcher
bench/bench.py                  benchmark script
bench/results/                  benchmark history + NOTES.md
.claude/skills/bench/SKILL.md   Claude Code skill for the benchmark
com.local.litellm.plist.example launchd daemon
CLAUDE.md                       notes for Claude Code when editing this repo
```

Local models (`local-*`, `agent-remote`) for machines on the LAN live commented out in `config.local.yaml`, which is gitignored.

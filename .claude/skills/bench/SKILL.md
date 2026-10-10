---
name: bench
description: Benchmark every model behind the local LiteLLM proxy (tool call, code generation, JSON output, latency), save results to bench/results/, and compare with the previous run. Use when asked to benchmark, compare, re-check or rank the proxy's models, or after adding/changing models in config.yaml.
---

# Proxy model benchmark

Script: `bench/bench.py` (run with the LiteLLM tool interpreter, it needs `httpx` and `pyyaml`).
Results: `bench/results/<YYYYMMDD-HHMM>.json` (raw) and `.md` (table). Keep them; they are the history.

## Run

```sh
~/.local/share/uv/tools/litellm/bin/python ~/litellm/bench/bench.py            # everything in config.yaml
~/.local/share/uv/tools/litellm/bin/python ~/litellm/bench/bench.py --only mistral-,zai-   # a subset
~/.local/share/uv/tools/litellm/bin/python ~/litellm/bench/bench.py --skip openrouter-     # spare OpenRouter quota
```

The proxy must be running (it is a launchd daemon on port 4000; restart = `pkill -f "bin/litellm"`).
A full run is ~90 requests and takes 5-15 minutes; run it in the background and read the `.md` afterwards.

## What it measures

- `tool`: Anthropic-format `/v1/messages` with one tool. This is the path Claude Code uses. PASS = correct tool_use block.
- `code`: asks for `fizzbuzz(n)`, extracts the code block, executes it with a check. PASS = runs and matches.
- `json`: asks for a JSON object, parses it. PASS = valid JSON with the right value. Skipped for `openrouter-*`.
- Latency is wall-clock per request through the proxy, single request at a time, so it includes reasoning tokens.
- A probe is marked FAIL with "fell back to ..." when `x-litellm-attempted-fallbacks` > 0, i.e. the primary
  deployment errored and another model answered. That is a config or provider problem for that model, even if the
  final answer was right.

## Interpreting and acting

- Compare the newest `.md` with the previous one; call out models that changed from PASS to FAIL or whose latency
  moved by more than ~2x.
- A model that fails `tool` should not be first in the `code`/`smart` chains (Claude Code needs tool calls).
- Reasoning models (gpt-oss, GLM, Nemotron, gpt-oss on Ollama) spend output tokens on thinking; the `code` column's
  out-token count shows how expensive they are per answer.
- Free-tier quotas: OpenRouter ~50 req/day (1000 with $10 credit), Z.ai 1 concurrent request, Google Flash-Lite
  ~500 req/day. Do not loop the benchmark; one run per config change is enough.
- Summarise findings for the user in a short table and suggest concrete chain changes in `config.yaml`
  (`router_settings.fallbacks` and `model_group_alias`), then make a `config.yaml.bak-*` before editing.

# Benchmark notes

Runs: `20261010-2349` (all models before NVIDIA), `20261011-0004` (NVIDIA only). Chains in config.yaml were
reordered from these on 2026-10-11.

## Conclusions
- Groq (gpt-oss-120b, gpt-oss-20b, qwen3.8-27b) is fastest, <1s per probe, all probes pass. Stays as every alias target.
- Ollama Cloud (gpt-oss:120b, gemma4:31b) ~0.6-1s, all pass. First fallback for smart/code.
- NVIDIA NIM: nemotron-3-super-120b ~0.9s all pass (best new general fallback); glm-5.3 ~4.7s all pass (best free
  "big" model for code); nemotron-550b ~2.6s; gemma-4-31b 30-130s per call (unusable, last resort only).
- Gemma 4 31B on Google AI Studio: 37-87s per call and one fallback. Demoted to the end of chains.
- Z.ai GLM-4.7-Flash: passes everything, 3-20s (reasoning tokens). Fine as code fallback, too slow for `fast`.
- Mistral: Ministral 14B/8B/3B <1.6s all pass; Codestral fast but answered a tool call in prose once (flaky tools).
- OpenRouter free: gemma-4-*:free hit an upstream shared-pool 429 and inkling*:free is 403 (agentic apps only);
  both removed from config. Nemotron 550B/120B, ling-flash, northcode, laguna, apodex, dots all pass. 50 req/day cap.
- Removed from consideration: NVIDIA kimi-k3 / deepseek-v4.1-flash (connection dropped), Mistral Small/Medium (0 rpm on free).

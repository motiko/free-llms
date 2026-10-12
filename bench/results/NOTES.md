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


## 2026-10-12: checkout-local proxy recheck

Report: `20261012-0239.md` / `.json`. Compared with `20261010-2349` and `20261011-0004`.
33 chat deployments, 88 probes: 28 deployments passed every probe, 77 probes passed.
The paid `openrouter-glm-flash` deployment was excluded; embeddings were checked separately.

- Primary aliases stay unchanged: Groq 120B/20B/Qwen and Gemini Flash-Lite passed all probes,
  averaging 0.2–0.6s. NVIDIA Nemotron 120B passed at 0.9s; GLM 5.3 passed at 2.4s.
- Both Ollama deployments regressed from all-pass to all-fallback. Request logs show HTTP 429
  with an exhausted monthly account quota. Remove Ollama from all automatic fallback targets,
  retaining direct deployment names and their own fallback rules. Restore automatic use only
  after quota renewal and successful revalidation. Smart now falls back first to NVIDIA Nemotron
  120B; code first to NVIDIA GLM 5.3. Keep alias and underlying deployment chains identical.
- Codestral again answered the tool request in prose, while code/JSON passed. Replace it with
  all-pass Ministral 14B in the agentic code fallback chain, behind Groq 120B.
- Laguna XS regressed on tools due to upstream shared-pool HTTP 429; code passed. Keep it
  available but put North Mini Code ahead of it in Laguna S's fallback chain.
- NVIDIA Gemma regressed from all-pass to three 150s client timeouts. It remains outside role
  fallback chains. Prefer Groq/NVIDIA Nemotron before the slow Google Gemma fallback for direct requests.
  Google Gemma passed but averaged 81.4s (70.5s tool, 55.1s code, 118.5s JSON).
- Average end-to-end latencies rose by more than 2x for Ollama 120B (0.79→6.54s), Ollama Gemma
  (0.61→5.94s), OpenRouter Nemotron 550B (1.94→9.04s), Laguna XS (3.02→11.58s), dots-note
  (3.97→10.18s), NVIDIA Gemma (64.70→150.01s), and NVIDIA gpt-oss 20B (2.03→4.54s).
  Failed probes include retry/fallback/timeout time; they do not measure primary inference speed alone.
- The separate `/v1/embeddings` check for `embed` succeeded with 2048 dimensions. Historical
  chat-probe failures for the embedding deployment are not valid embedding capability results.

- Post-change validation passed: live Anthropic tool calls on `smart` (Groq 120B, 0.47s) and
  `code` (Groq Qwen, 0.23s), with no fallback. Isolated Router forced-failure tool checks selected
  the configured first fallbacks: NVIDIA Nemotron 120B (1.27s) and NVIDIA GLM 5.3 (6.27s), exactly
  one fallback each. The live proxy retains its default mock-testing guard. Raw checks are included
  in the run's JSON report; the background service was restarted and remains running.

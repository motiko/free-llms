#!/usr/bin/env python3
"""Small capability + latency benchmark for every model behind the LiteLLM proxy.

Runs three probes per model through the proxy (so routing, fallbacks and the
Anthropic-format endpoint are exercised exactly as clients see them):

  tool  - /v1/messages (Anthropic format) with one tool; pass = model calls read_file(path=/etc/hosts)
  code  - /v1/chat/completions; pass = returned fizzbuzz(n) runs and matches expected output
  json  - /v1/chat/completions; pass = reply parses as JSON with city == Paris

OpenRouter free models only get tool + code to spare the 50 req/day quota.
A probe counts as FAILED if the proxy fell back to another deployment
(x-litellm-attempted-fallbacks > 0) even when the final answer was right.

Usage:
  bench.py [--only PREFIX,...] [--skip PREFIX,...] [--base URL] [--out DIR]
Results: <out>/<timestamp>.json and <out>/<timestamp>.md (default bench/results/).
"""
import argparse, json, os, re, subprocess, sys, tempfile, time, datetime
import httpx, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(os.path.dirname(HERE), "config.yaml")
KEY = "sk-local-anything"
TOOL = {"name": "read_file", "description": "Read a file from disk",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}
FIZZ_CHECK = """
exp = ['1','2','Fizz','4','Buzz','Fizz','7','8','Fizz','Buzz','11','Fizz','13','14','FizzBuzz']
out = fizzbuzz(15)
assert list(out) == exp, out
print("ok")
"""

def hdr(r, k):
    return r.headers.get(k, "")

def probe_tool(c, model):
    body = {"model": model, "max_tokens": 600, "tools": [TOOL],
            "messages": [{"role": "user", "content": "Read the file /etc/hosts using the tool."}]}
    r = c.post("/v1/messages", json=body, headers={"x-api-key": KEY, "anthropic-version": "2023-06-01"})
    d = r.json()
    calls = [b for b in d.get("content", []) if b.get("type") == "tool_use"]
    ok = any(b.get("name") == "read_file" and "/etc/hosts" in str(b.get("input", {}).get("path", "")) for b in calls)
    err = "" if ok else ((d.get("error") or {}).get("message") or ("no tool_use, answered in text" if not calls else "wrong tool/args"))
    return ok, r, d, err

def chat(c, model, prompt, max_tokens):
    body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    r = c.post("/v1/chat/completions", json=body, headers={"Authorization": f"Bearer {KEY}"})
    d = r.json()
    msg = (d.get("choices") or [{}])[0].get("message", {})
    return r, d, msg.get("content") or ""

def probe_code(c, model):
    r, d, txt = chat(c, model, "Write a Python function `fizzbuzz(n)` that returns a list of strings for 1..n "
                     "following FizzBuzz rules (Fizz for multiples of 3, Buzz for 5, FizzBuzz for both, "
                     "else the number as a string). Reply with only the code in one ```python block, no explanation.", 2500)
    m = re.search(r"```(?:python)?\s*(.*?)```", txt, re.S)
    code = m.group(1) if m else txt
    if not code.strip():
        return False, r, d, (d.get("error") or {}).get("message") or "empty reply"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code + "\n" + FIZZ_CHECK); path = f.name
    try:
        p = subprocess.run([sys.executable, "-I", path], capture_output=True, text=True, timeout=20)
        ok = p.returncode == 0 and "ok" in p.stdout
        return ok, r, d, "" if ok else (p.stderr.strip().splitlines() or ["no output"])[-1][:120]
    finally:
        os.unlink(path)

def probe_json(c, model):
    r, d, txt = chat(c, model, "Return a JSON object with keys \"city\" and \"country\" for the capital of France. "
                     "Reply with only the JSON, no prose, no code fences.", 600)
    m = re.search(r"\{.*\}", txt, re.S)
    try:
        obj = json.loads(m.group(0)) if m else None
        ok = isinstance(obj, dict) and str(obj.get("city", "")).lower() == "paris"
        return ok, r, d, "" if ok else f"bad json: {txt[:80]!r}"
    except Exception as e:
        return False, r, d, (d.get("error") or {}).get("message") or f"{e}: {txt[:80]!r}"

PROBES = {"tool": probe_tool, "code": probe_code, "json": probe_json}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma list of model-name prefixes to include")
    ap.add_argument("--skip", default="", help="comma list of model-name prefixes to exclude")
    ap.add_argument("--base", default="http://localhost:4000")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    a = ap.parse_args()
    cfg = yaml.safe_load(open(CFG))
    models = []
    for m in cfg["model_list"]:
        n = m["model_name"]
        if (m.get("model_info") or {}).get("mode") == "embedding": continue   # chat probes only
        if n not in models: models.append(n)
    only = [p for p in a.only.split(",") if p]; skip = [p for p in a.skip.split(",") if p]
    if only: models = [m for m in models if any(m.startswith(p) for p in only)]
    if skip: models = [m for m in models if not any(m.startswith(p) for p in skip)]
    c = httpx.Client(base_url=a.base, timeout=150)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    results = {"timestamp": stamp, "base": a.base, "models": {}}
    for mi, model in enumerate(models, 1):
        probes = ["tool", "code"] if model.startswith("openrouter-") else ["tool", "code", "json"]
        res = {}
        for p in probes:
            t0 = time.time()
            try:
                ok, r, d, err = PROBES[p](c, model)
                lat = time.time() - t0
                usage = d.get("usage") or {}
                out_tok = usage.get("completion_tokens") or usage.get("output_tokens")
                fb = int(hdr(r, "x-litellm-attempted-fallbacks") or 0)
                dep = hdr(r, "x-litellm-model-name")
                if fb: ok, err = False, f"fell back to {dep} ({err or 'primary failed'})"
                res[p] = {"ok": ok, "latency_s": round(lat, 2), "out_tokens": out_tok, "deployment": dep,
                          "fallbacks": fb, "http": r.status_code, "error": err}
            except Exception as e:
                res[p] = {"ok": False, "latency_s": round(time.time() - t0, 2), "error": f"{type(e).__name__}: {e}"[:160]}
            print(f"[{mi}/{len(models)}] {model:28} {p:4} {'PASS' if res[p]['ok'] else 'FAIL'} {res[p]['latency_s']:6.1f}s {res[p].get('error','')}", flush=True)
            time.sleep(1)
        results["models"][model] = res
    os.makedirs(a.out, exist_ok=True)
    jpath = os.path.join(a.out, f"{stamp}.json"); json.dump(results, open(jpath, "w"), indent=1)
    lines = [f"# Proxy model benchmark {stamp}", "", f"Base: {a.base}. Probes: tool (Anthropic /v1/messages tool call), code (fizzbuzz, executed), json (structured reply).",
             "FAIL with 'fell back' means the primary deployment errored and the proxy answered from a fallback.", "",
             "| model | tool | code | json | avg latency s | code out tokens | note |", "|---|---|---|---|---|---|---|"]
    for model, res in results["models"].items():
        def cell(p):
            if p not in res: return "-"
            return ("PASS" if res[p]["ok"] else "FAIL") + f" {res[p]['latency_s']:.1f}s"
        lats = [r["latency_s"] for r in res.values()]
        note = "; ".join(f"{p}: {r['error']}" for p, r in res.items() if r.get("error"))[:140]
        lines.append(f"| {model} | {cell('tool')} | {cell('code')} | {cell('json')} | {sum(lats)/len(lats):.1f} | {res.get('code',{}).get('out_tokens','')} | {note} |")
    mpath = os.path.join(a.out, f"{stamp}.md"); open(mpath, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines)); print(f"\nsaved {jpath}\nsaved {mpath}")

if __name__ == "__main__":
    main()

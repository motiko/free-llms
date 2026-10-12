"""LiteLLM custom callback: append one JSON line per request to logs/requests.jsonl.

Records which alias was asked for, which deployment/provider served it, tokens, cost,
latency, fallback/retry counts, error details and the provider's remaining rate-limit
headers when it sends any. Wired in via litellm_settings.callbacks in config.yaml.

Query examples:
  jq -c 'select(.status=="failure") | {ts,model_group,model,error_code,error}' logs/requests.jsonl
  jq -r '[.provider,.model_group] | @tsv' logs/requests.jsonl | sort | uniq -c
"""
import datetime, json, os, threading

from litellm.integrations.custom_logger import CustomLogger

LOG_PATH = os.environ.get("LITELLM_REQUEST_LOG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "requests.jsonl"))
_lock = threading.Lock()


def _g(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return default if d is None else d


def _record(kwargs, status, start, end):
    slp = kwargs.get("standard_logging_object") or {}
    meta = slp.get("metadata") or {}
    lp = kwargs.get("litellm_params") or {}
    lp_meta = lp.get("metadata") or lp.get("litellm_metadata") or {}
    err = slp.get("error_information") or {}
    rec = {
        "ts": datetime.datetime.fromtimestamp(slp.get("startTime") or start.timestamp(), datetime.timezone.utc).isoformat(timespec="milliseconds"),
        "status": slp.get("status") or status,
        "call_id": slp.get("litellm_call_id") or kwargs.get("litellm_call_id"),
        "trace_id": slp.get("trace_id"),
        "call_type": slp.get("call_type") or kwargs.get("call_type"),
        "stream": slp.get("stream"),
        "model_group": slp.get("model_group") or lp_meta.get("model_group") or kwargs.get("model"),
        "model": slp.get("model") or kwargs.get("model"),
        "provider": slp.get("custom_llm_provider") or kwargs.get("custom_llm_provider"),
        "api_base": slp.get("api_base") or meta.get("api_base"),
        "model_id": slp.get("model_id") or meta.get("model_id"),
        "prompt_tokens": slp.get("prompt_tokens"),
        "completion_tokens": slp.get("completion_tokens"),
        "total_tokens": slp.get("total_tokens"),
        "cost_usd": slp.get("response_cost"),
        "latency_s": round(slp.get("response_time") or (end - start).total_seconds(), 3),
        "overhead_ms": meta.get("litellm_overhead_time_ms"),
        "fallbacks": lp_meta.get("attempted_fallbacks", lp_meta.get("fallback_depth")),
        "retries": lp_meta.get("attempted_retries"),
        "ratelimit_remaining_requests": meta.get("x_ratelimit_remaining_requests"),
        "ratelimit_remaining_tokens": meta.get("x_ratelimit_remaining_tokens"),
        "client_ip": slp.get("requester_ip_address") or meta.get("requester_ip_address"),
        "user_agent": slp.get("user_agent") or meta.get("user_agent"),
    }
    if status == "failure":
        rec["error_code"] = err.get("error_code")
        rec["error_class"] = err.get("error_class")
        rec["error"] = (slp.get("error_str") or str(kwargs.get("exception") or ""))[:500]
    return {k: v for k, v in rec.items() if v is not None and v != "" and v != {}}


def _append(rec):
    line = json.dumps(rec, ensure_ascii=False, default=str) + "\n"
    with _lock:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)


class RequestLogger(CustomLogger):
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        _append(_record(kwargs, "success", start_time, end_time))

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        _append(_record(kwargs, "failure", start_time, end_time))

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        _append(_record(kwargs, "success", start_time, end_time))

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        _append(_record(kwargs, "failure", start_time, end_time))


request_logger = RequestLogger()

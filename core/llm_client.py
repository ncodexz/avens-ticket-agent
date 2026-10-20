"""The only place where the code calls a language model.

Each pipeline step has its own model, set in core/models.json:
    {"routing": {"provider": "databricks", "model": "databricks-gpt-oss-120b"}}
Providers: 'databricks' (serving endpoints, token from a Databricks secret) and
'groq' (API key in .env). Both speak the OpenAI chat format over HTTPS.
Every call is logged with its tokens in runs/llm_calls.jsonl, which is the basis
for measuring cost.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from core.config import env, mode, runs_dir

MODELS_FILE = Path(__file__).with_name("models.json")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_databricks_token = None


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    seconds: float


def model_config(step):
    with open(MODELS_FILE, encoding="utf-8") as handle:
        return json.load(handle)[step]


def extract_text(content):
    """Some models return a string; others a list of blocks (reasoning + text)."""
    if isinstance(content, str):
        return content
    parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return "".join(parts)


def _endpoint_and_headers(provider, model, path="chat/completions"):
    global _databricks_token
    if provider == "databricks":
        if _databricks_token is None:
            from core.databricks_access import get_secret

            _databricks_token = get_secret(
                env("LLM_SECRET_SCOPE", required=True), env("LLM_SECRET_KEY", required=True)
            )
        host = env("DATABRICKS_HOST", required=True).rstrip("/")
        return f"{host}/serving-endpoints/{path}", {"Authorization": f"Bearer {_databricks_token}"}
    if provider == "groq":
        return GROQ_URL, {"Authorization": f"Bearer {env('GROQ_API_KEY', required=True)}"}
    raise ValueError(f"Unknown provider: {provider!r}")


def chat(step, messages, max_tokens=1500, run_id=None, ticket_id=None):
    config = model_config(step)
    url, headers = _endpoint_and_headers(config["provider"], config["model"])
    started = time.time()
    response = requests.post(
        url,
        headers=headers,
        json={"model": config["model"], "messages": messages, "max_tokens": max_tokens},
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    usage = data.get("usage", {})
    result = LLMResult(
        text=extract_text(data["choices"][0]["message"]["content"]),
        model=config["model"],
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        seconds=round(time.time() - started, 2),
    )
    _log(step, result, run_id, ticket_id)
    return result


def _log(step, result, run_id, ticket_id):
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "mode": mode(),
        "step": step,
        "ticket": ticket_id,
        "model": result.model,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "seconds": result.seconds,
    }
    with open(runs_dir() / "llm_calls.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


EMBED_BATCH = 16


def embed(texts, run_id=None):
    """Turn texts into vectors with the model of the 'embedding' step. Databricks only."""
    config = model_config("embedding")
    if config["provider"] != "databricks":
        raise ValueError("Embeddings are only configured for the databricks provider")
    url, headers = _endpoint_and_headers("databricks", config["model"], "embeddings")
    vectors = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start:start + EMBED_BATCH]
        started = time.time()
        response = requests.post(
            url, headers=headers, json={"model": config["model"], "input": batch}, timeout=120
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage", {})
        items = sorted(data["data"], key=lambda item: item["index"])
        vectors.extend(item["embedding"] for item in items)
        _log(
            "embedding",
            LLMResult(
                text="",
                model=config["model"],
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=0,
                total_tokens=usage.get("total_tokens", usage.get("prompt_tokens", 0)),
                seconds=round(time.time() - started, 2),
            ),
            run_id,
            None,
        )
    return vectors

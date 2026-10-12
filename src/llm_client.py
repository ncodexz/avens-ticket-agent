"""
Single place that knows which LLM provider we're talking to. Today: Groq.
Day of the hackathon: Alenia's Shared Model Serving endpoint (Databricks).
Only this file changes — nothing that calls `chat_json()` needs to know
which provider is behind it.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.environ.get("LLM_PROVIDER", "groq")  # "groq" | "databricks"
MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")


def _get_client():
    if PROVIDER == "groq":
        from groq import Groq
        return Groq()
    elif PROVIDER == "databricks":
        # Day-of-hackathon: point an OpenAI-compatible client at Alenia's
        # Shared Model Serving endpoint. Fill in base_url / api_key from
        # their docs/secrets once known.
        from openai import OpenAI
        return OpenAI(
            base_url=os.environ["DATABRICKS_SERVING_ENDPOINT_URL"],
            api_key=os.environ["DATABRICKS_TOKEN"],
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")


_client = None


def chat_json(prompt: str) -> dict:
    """Send a prompt, get back a parsed JSON dict. Used by every stage that
    asks the LLM to return structured data (extract_signals, generate_resolution)."""
    global _client
    if _client is None:
        _client = _get_client()

    response = _client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


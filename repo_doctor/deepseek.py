"""Minimal, fixed-endpoint DeepSeek JSON client."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


API_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekError(Exception):
    """A provider failure safe to show without exposing request credentials."""


@dataclass(frozen=True)
class DeepSeekResult:
    model: str
    payload: dict
    usage: dict[str, int | None] | None = None


def complete_json(
    system_prompt: str,
    user_prompt: str,
    *,
    api_key: str,
    model: str,
    timeout: float = 60.0,
) -> DeepSeekResult:
    """Send one non-streaming JSON request and parse the model response."""
    request_data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(request_data, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        exc.close()
        raise DeepSeekError(f"DeepSeek API returned HTTP {exc.code}") from None
    except TimeoutError:
        raise DeepSeekError("DeepSeek API request timed out") from None
    except urllib.error.URLError:
        raise DeepSeekError("Could not connect to DeepSeek API") from None
    except OSError:
        raise DeepSeekError("Could not read the DeepSeek API response") from None

    try:
        envelope = json.loads(response_body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise DeepSeekError("DeepSeek API returned invalid JSON") from None
    if not isinstance(envelope, dict):
        raise DeepSeekError("DeepSeek API response must be a JSON object")

    response_model = envelope.get("model")
    choices = envelope.get("choices")
    if not isinstance(response_model, str) or not response_model.strip():
        raise DeepSeekError("DeepSeek API response did not include a model name")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise DeepSeekError("DeepSeek API response did not include a completion")

    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise DeepSeekError("DeepSeek response was truncated by the output token limit")
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekError("DeepSeek returned empty response content")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        raise DeepSeekError("DeepSeek response content was not valid JSON") from None
    if not isinstance(payload, dict):
        raise DeepSeekError("DeepSeek response content must be a JSON object")

    usage_envelope = envelope.get("usage")
    usage = None
    if isinstance(usage_envelope, dict):
        usage = {}
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage_envelope.get(field)
            usage[field] = value if type(value) is int and value >= 0 else None

    return DeepSeekResult(response_model, payload, usage)

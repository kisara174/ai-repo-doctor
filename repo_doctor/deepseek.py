"""Minimal, fixed-endpoint DeepSeek JSON client."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


API_URL = "https://api.deepseek.com/chat/completions"
MAX_REQUEST_BYTES = 256 * 1024
DEEPSEEK_ERROR_CODES = frozenset({
    "timeout",
    "connection",
    "http",
    "request_too_large",
    "response_too_large",
    "invalid_response",
    "unknown",
})


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so credentials stay scoped to the fixed endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DeepSeekError(Exception):
    """A provider failure safe to show without exposing request credentials."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "unknown",
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code if isinstance(code, str) and code in DEEPSEEK_ERROR_CODES else "unknown"
        self.http_status = (
            http_status
            if self.code == "http" and type(http_status) is int and 100 <= http_status <= 599
            else None
        )


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
    request_body = json.dumps(request_data, ensure_ascii=False).encode("utf-8")
    if len(request_body) > MAX_REQUEST_BYTES:
        raise DeepSeekError(
            "DeepSeek API request exceeds 256 KiB limit", code="request_too_large"
        )
    request = urllib.request.Request(
        API_URL,
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        opener = urllib.request.build_opener(_NoRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        exc.close()
        raise DeepSeekError(
            f"DeepSeek API returned HTTP {exc.code}", code="http", http_status=exc.code
        ) from None
    except TimeoutError:
        raise DeepSeekError("DeepSeek API request timed out", code="timeout") from None
    except urllib.error.URLError:
        raise DeepSeekError("Could not connect to DeepSeek API", code="connection") from None
    except OSError:
        raise DeepSeekError(
            "Could not read the DeepSeek API response", code="connection"
        ) from None

    try:
        envelope = json.loads(response_body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise DeepSeekError("DeepSeek API returned invalid JSON", code="invalid_response") from None
    if not isinstance(envelope, dict):
        raise DeepSeekError(
            "DeepSeek API response must be a JSON object", code="invalid_response"
        )

    response_model = envelope.get("model")
    choices = envelope.get("choices")
    if not isinstance(response_model, str) or not response_model.strip():
        raise DeepSeekError(
            "DeepSeek API response did not include a model name", code="invalid_response"
        )
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise DeepSeekError(
            "DeepSeek API response did not include a completion", code="invalid_response"
        )

    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise DeepSeekError(
            "DeepSeek response was truncated by the output token limit", code="invalid_response"
        )
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekError("DeepSeek returned empty response content", code="invalid_response")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        raise DeepSeekError(
            "DeepSeek response content was not valid JSON", code="invalid_response"
        ) from None
    if not isinstance(payload, dict):
        raise DeepSeekError(
            "DeepSeek response content must be a JSON object", code="invalid_response"
        )

    usage_envelope = envelope.get("usage")
    usage = None
    if isinstance(usage_envelope, dict):
        usage = {}
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage_envelope.get(field)
            usage[field] = value if type(value) is int and value >= 0 else None

    return DeepSeekResult(response_model, payload, usage)

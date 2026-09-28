"""Minimal, fixed-endpoint DeepSeek JSON client."""

import json
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass


API_URL = "https://api.deepseek.com/chat/completions"
MODELS_URL = "https://api.deepseek.com/models"
MAX_REQUEST_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_THINKING_MODES = frozenset({"enabled", "disabled"})
DEEPSEEK_ERROR_CODES = frozenset({
    "timeout",
    "connection",
    "http",
    "request_too_large",
    "response_too_large",
    "invalid_response",
    "unknown",
})
DEEPSEEK_ERROR_DETAILS = frozenset({
    "invalid_envelope_json",
    "invalid_envelope_shape",
    "missing_model",
    "missing_choices",
    "truncated",
    "missing_content",
    "invalid_content_json",
    "invalid_content_shape",
})
_TRANSPORT_CATEGORIES = frozenset({"dns", "tls", "proxy", "timeout", "connection"})


def _safe_usage(value: object) -> dict[str, int | None] | None:
    if not isinstance(value, dict):
        return None
    usage = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        token_value = value.get(field)
        usage[field] = (
            token_value if type(token_value) is int and token_value >= 0 else None
        )
    return usage


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
        error_detail: str | None = None,
        usage: dict[str, int | None] | None = None,
        transport_category: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code if isinstance(code, str) and code in DEEPSEEK_ERROR_CODES else "unknown"
        self.http_status = (
            http_status
            if self.code == "http" and type(http_status) is int and 100 <= http_status <= 599
            else None
        )
        self.error_detail = (
            error_detail
            if self.code == "invalid_response"
            and isinstance(error_detail, str)
            and error_detail in DEEPSEEK_ERROR_DETAILS
            else None
        )
        self.usage = _safe_usage(usage)
        self.transport_category = (
            transport_category
            if self.code in {"connection", "timeout"} and transport_category in _TRANSPORT_CATEGORIES
            else None
        )

    @property
    def diagnostic_category(self) -> str:
        if self.code == "http":
            if self.http_status == 401:
                return "authentication"
            if self.http_status == 402:
                return "balance"
            if self.http_status == 407:
                return "proxy"
            if self.http_status == 429:
                return "rate_limit"
            if self.http_status is not None and self.http_status >= 500:
                return "server"
            return "http"
        return self.transport_category or self.code


def _connection_category(reason: object) -> str:
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(reason, socket.gaierror):
        return "dns"
    if isinstance(reason, ssl.SSLError):
        return "tls"
    if isinstance(reason, str) and reason.startswith("Tunnel connection failed:"):
        return "proxy"
    return "connection"


def _read_response(request: urllib.request.Request, timeout: float) -> bytes:
    try:
        opener = urllib.request.build_opener(_NoRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            response_body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(response_body) > MAX_RESPONSE_BYTES:
                raise DeepSeekError(
                    "DeepSeek API response exceeds 2 MiB limit", code="response_too_large"
                )
            return response_body
    except urllib.error.HTTPError as exc:
        exc.close()
        raise DeepSeekError(
            f"DeepSeek API returned HTTP {exc.code}", code="http", http_status=exc.code
        ) from None
    except TimeoutError:
        raise DeepSeekError(
            "DeepSeek API request timed out", code="timeout", transport_category="timeout"
        ) from None
    except urllib.error.URLError as exc:
        category = _connection_category(exc.reason)
        raise DeepSeekError(
            "Could not connect to DeepSeek API", code="connection", transport_category=category
        ) from None
    except OSError as exc:
        category = _connection_category(exc)
        raise DeepSeekError(
            "Could not read the DeepSeek API response", code="connection", transport_category=category
        ) from None


def list_models(*, api_key: str, timeout: float = 10.0) -> tuple[str, ...]:
    """Check the fixed models endpoint without sending repository source."""
    request = urllib.request.Request(
        MODELS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    response_body = _read_response(request, timeout)
    try:
        envelope = json.loads(response_body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise DeepSeekError(
            "DeepSeek API returned invalid JSON",
            code="invalid_response",
            error_detail="invalid_envelope_json",
        ) from None
    if (
        not isinstance(envelope, dict)
        or envelope.get("object") != "list"
        or not isinstance(envelope.get("data"), list)
        or any(
            not isinstance(item, dict)
            or item.get("object") != "model"
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
            for item in envelope["data"]
        )
    ):
        raise DeepSeekError(
            "DeepSeek API returned an invalid model list",
            code="invalid_response",
            error_detail="invalid_envelope_shape",
        )
    return tuple(item["id"] for item in envelope["data"])


def _thinking_parameter(thinking_mode: str | None) -> dict | None:
    if thinking_mode is None:
        return None
    if not isinstance(thinking_mode, str) or thinking_mode not in _THINKING_MODES:
        raise ValueError("thinking_mode must be enabled or disabled")
    return {"type": thinking_mode}


def _serialize_request_body(
    system_prompt: str,
    user_prompt: str,
    model: str,
    *,
    thinking_mode: str | None = None,
) -> bytes:
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
    thinking = _thinking_parameter(thinking_mode)
    if thinking is not None:
        request_data["thinking"] = thinking
    return json.dumps(request_data, ensure_ascii=False).encode("utf-8")


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
    thinking_mode: str | None = None,
) -> DeepSeekResult:
    """Send one non-streaming JSON request and parse the model response."""
    request_body = _serialize_request_body(
        system_prompt, user_prompt, model, thinking_mode=thinking_mode
    )
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

    response_body = _read_response(request, timeout)

    try:
        envelope = json.loads(response_body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise DeepSeekError(
            "DeepSeek API returned invalid JSON",
            code="invalid_response",
            error_detail="invalid_envelope_json",
        ) from None
    if not isinstance(envelope, dict):
        raise DeepSeekError(
            "DeepSeek API response must be a JSON object",
            code="invalid_response",
            error_detail="invalid_envelope_shape",
        )

    usage = _safe_usage(envelope.get("usage"))
    response_model = envelope.get("model")
    choices = envelope.get("choices")
    if not isinstance(response_model, str) or not response_model.strip():
        raise DeepSeekError(
            "DeepSeek API response did not include a model name",
            code="invalid_response",
            error_detail="missing_model",
            usage=usage,
        )
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise DeepSeekError(
            "DeepSeek API response did not include a completion",
            code="invalid_response",
            error_detail="missing_choices",
            usage=usage,
        )

    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise DeepSeekError(
            "DeepSeek response was truncated by the output token limit",
            code="invalid_response",
            error_detail="truncated",
            usage=usage,
        )
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekError(
            "DeepSeek returned empty response content",
            code="invalid_response",
            error_detail="missing_content",
            usage=usage,
        )
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        raise DeepSeekError(
            "DeepSeek response content was not valid JSON",
            code="invalid_response",
            error_detail="invalid_content_json",
            usage=usage,
        ) from None
    if not isinstance(payload, dict):
        raise DeepSeekError(
            "DeepSeek response content must be a JSON object",
            code="invalid_response",
            error_detail="invalid_content_shape",
            usage=usage,
        )

    return DeepSeekResult(response_model, payload, usage)

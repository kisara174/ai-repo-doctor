import io
import json
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

from repo_doctor.deepseek import (
    DeepSeekError,
    DeepSeekResult,
    _NoRedirectHandler,
    complete_json,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


class DeepSeekTests(unittest.TestCase):
    def call_client(self):
        return complete_json(
            "System prompt",
            "User prompt",
            api_key="test-secret",
            model="deepseek-flash",
        )

    def fake_api_response(self, content, finish_reason="stop", usage=None, include_usage=True):
        envelope = {
                "id": "completion-id",
                "object": "chat.completion",
                "created": 1710000000,
                "model": "deepseek-flash",
                "system_fingerprint": "fp_test",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": finish_reason,
                        "logprobs": None,
                        "message": {"role": "assistant", "content": content},
                    }
                ],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                    "prompt_tokens_details": {
                        "cached_tokens": 0,
                        "prompt_cache_hit_tokens": 0,
                        "prompt_cache_miss_tokens": 3,
                    },
                    "completion_tokens_details": {"reasoning_tokens": 0},
                },
            }
        if usage is not None:
            envelope["usage"] = usage
        elif not include_usage:
            envelope.pop("usage")
        return FakeResponse(envelope)

    def test_complete_json_sends_one_non_streaming_json_request(self):
        response = self.fake_api_response('{"findings": []}')

        with patch("urllib.request.OpenerDirector.open", return_value=response) as open_request:
            result = complete_json(
                "System prompt",
                "User prompt",
                api_key="test-secret",
                model="deepseek-flash",
            )

        self.assertEqual(result, DeepSeekResult(
            "deepseek-flash", {"findings": []},
            {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        ))
        open_request.assert_called_once()
        request = open_request.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(open_request.call_args.kwargs["timeout"], 60.0)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "deepseek-flash")
        self.assertEqual(body["messages"], [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User prompt"},
        ])
        self.assertIs(body["stream"], False)
        self.assertEqual(body["max_tokens"], 4096)
        self.assertEqual(body["response_format"], {"type": "json_object"})

    def test_missing_usage_remains_none(self):
        with patch("urllib.request.OpenerDirector.open", return_value=self.fake_api_response(
            '{"findings": []}', include_usage=False
        )):
            result = self.call_client()

        self.assertIsNone(result.usage)

    def test_invalid_usage_values_become_null_and_extra_fields_are_omitted(self):
        response = self.fake_api_response(
            '{"findings": []}',
            usage={
                "prompt_tokens": -1,
                "completion_tokens": True,
                "total_tokens": "5",
                "reasoning_tokens": 8,
            },
        )
        with patch("urllib.request.OpenerDirector.open", return_value=response):
            result = self.call_client()

        self.assertEqual(result.usage, {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        })

    def test_old_two_argument_result_construction_keeps_usage_optional(self):
        result = DeepSeekResult("deepseek-flash", {"findings": []})
        self.assertIsNone(result.usage)

    def test_legacy_error_construction_defaults_to_unknown_category(self):
        error = DeepSeekError("legacy message")
        self.assertEqual(getattr(error, "code", None), "unknown")
        self.assertIsNone(getattr(error, "http_status", None))

    def test_http_error_is_sanitized_and_not_retried(self):
        response_body = io.BytesIO(b"test-secret")
        failure = urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions",
            401,
            "Unauthorized",
            hdrs=None,
            fp=response_body,
        )
        with patch("urllib.request.OpenerDirector.open", side_effect=failure) as open_request:
            with self.assertRaisesRegex(DeepSeekError, "HTTP 401") as raised:
                self.call_client()

        open_request.assert_called_once()
        self.assertNotIn("test-secret", str(raised.exception))
        self.assertTrue(response_body.closed)
        self.assertEqual(getattr(raised.exception, "code", None), "http")
        self.assertEqual(getattr(raised.exception, "http_status", None), 401)

    def test_redirect_handler_refuses_redirects_and_client_installs_it(self):
        request = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=b"{}",
            headers={"Authorization": "Bearer test-secret"},
            method="POST",
        )
        with patch(
            "urllib.request.build_opener", wraps=urllib.request.build_opener
        ) as build_opener:
            with patch(
                "urllib.request.OpenerDirector.open",
                return_value=self.fake_api_response('{"findings": []}'),
            ) as open_request:
                self.call_client()

        build_opener.assert_called_once()
        open_request.assert_called_once()
        handler = build_opener.call_args.args[0]
        self.assertIsInstance(handler, _NoRedirectHandler)
        parent = Mock()
        handler.parent = parent
        self.assertIsNone(
            handler.http_error_302(
                request,
                io.BytesIO(),
                302,
                "Found",
                {"location": "https://attacker.example/collect"},
            )
        )
        parent.open.assert_not_called()

    def test_oversized_request_is_rejected_before_opening_transport(self):
        with patch("urllib.request.OpenerDirector.open") as open_request:
            open_request.return_value = self.fake_api_response('{"findings": []}')
            with self.assertRaisesRegex(DeepSeekError, "request exceeds") as raised:
                complete_json(
                    "System prompt",
                    "x" * (300 * 1024),
                    api_key="test-secret",
                    model="deepseek-flash",
                )

        open_request.assert_not_called()
        self.assertEqual(getattr(raised.exception, "code", None), "request_too_large")

    def test_url_error_does_not_leak_its_reason(self):
        with patch(
            "urllib.request.OpenerDirector.open",
            side_effect=urllib.error.URLError("test-secret"),
        ):
            with self.assertRaises(DeepSeekError) as raised:
                self.call_client()

        self.assertNotIn("test-secret", str(raised.exception))
        self.assertEqual(getattr(raised.exception, "code", None), "connection")

    def test_timeout_error_does_not_leak_its_message(self):
        with patch("urllib.request.OpenerDirector.open", side_effect=TimeoutError("test-secret")):
            with self.assertRaisesRegex(DeepSeekError, "timed out") as raised:
                self.call_client()

        self.assertNotIn("test-secret", str(raised.exception))
        self.assertEqual(getattr(raised.exception, "code", None), "timeout")

    def test_invalid_api_envelope_json_is_rejected(self):
        with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(b"not json")):
            with self.assertRaisesRegex(DeepSeekError, "invalid JSON") as raised:
                self.call_client()
        self.assertEqual(getattr(raised.exception, "code", None), "invalid_response")

    def test_missing_completion_is_rejected(self):
        with patch(
            "urllib.request.OpenerDirector.open",
            return_value=FakeResponse({"model": "deepseek-flash", "choices": []}),
        ):
            with self.assertRaisesRegex(DeepSeekError, "completion") as raised:
                self.call_client()
        self.assertEqual(getattr(raised.exception, "code", None), "invalid_response")

    def test_empty_message_content_is_rejected(self):
        with patch("urllib.request.OpenerDirector.open", return_value=self.fake_api_response("  ")):
            with self.assertRaisesRegex(DeepSeekError, "empty response") as raised:
                self.call_client()
        self.assertEqual(getattr(raised.exception, "code", None), "invalid_response")

    def test_malformed_model_json_is_rejected(self):
        with patch(
            "urllib.request.OpenerDirector.open",
            return_value=self.fake_api_response("{broken"),
        ):
            with self.assertRaisesRegex(DeepSeekError, "not valid JSON") as raised:
                self.call_client()
        self.assertEqual(getattr(raised.exception, "code", None), "invalid_response")

    def test_model_array_is_rejected(self):
        with patch("urllib.request.OpenerDirector.open", return_value=self.fake_api_response("[]")):
            with self.assertRaisesRegex(DeepSeekError, "must be a JSON object") as raised:
                self.call_client()
        self.assertEqual(getattr(raised.exception, "code", None), "invalid_response")

    def test_truncated_model_response_is_rejected(self):
        with patch(
            "urllib.request.OpenerDirector.open",
            return_value=self.fake_api_response("{}", "length"),
        ):
            with self.assertRaisesRegex(DeepSeekError, "truncated") as raised:
                self.call_client()
        self.assertEqual(getattr(raised.exception, "code", None), "invalid_response")

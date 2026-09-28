import io
import json
import socket
import ssl
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

import repo_doctor.deepseek as deepseek_module
from repo_doctor.deepseek import (
    DeepSeekError,
    DeepSeekResult,
    _NoRedirectHandler,
    complete_json,
    list_models,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )
        self.read_sizes = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.closed = True
        return False

    def read(self, size=-1):
        self.read_sizes.append(size)
        return self.payload if size < 0 else self.payload[:size]


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
        self.assertEqual(
            request.data,
            b'{"model": "deepseek-flash", "messages": [{"role": "system", "content": "System prompt"}, '
            b'{"role": "user", "content": "User prompt"}], "stream": false, "max_tokens": 4096, '
            b'"response_format": {"type": "json_object"}}',
        )
        self.assertEqual(body["model"], "deepseek-flash")
        self.assertEqual(body["messages"], [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User prompt"},
        ])
        self.assertIs(body["stream"], False)
        self.assertEqual(body["max_tokens"], 4096)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertNotIn("thinking", body)

    def test_complete_json_sends_explicit_thinking_mode(self):
        response = self.fake_api_response('{"findings": []}')

        with patch("urllib.request.OpenerDirector.open", return_value=response) as open_request:
            complete_json(
                "System prompt",
                "User prompt",
                api_key="test-secret",
                model="deepseek-flash",
                thinking_mode="disabled",
            )

        body = json.loads(open_request.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["thinking"], {"type": "disabled"})

    def test_complete_json_rejects_unsupported_thinking_mode_before_transport(self):
        with patch("urllib.request.OpenerDirector.open") as open_request:
            with self.assertRaises(ValueError):
                complete_json(
                    "System prompt",
                    "User prompt",
                    api_key="test-secret",
                    model="deepseek-flash",
                    thinking_mode="balanced",
                )

        open_request.assert_not_called()

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

    def test_request_wire_bytes_accept_exact_limit_and_reject_one_byte_over(self):
        limit = getattr(deepseek_module, "MAX_REQUEST_BYTES", None)
        serializer = getattr(deepseek_module, "_serialize_request_body", None)
        if not isinstance(limit, int) or not callable(serializer):
            self.fail("wire request serializer and byte limit are not available")

        base = serializer("system", "", "model")
        remaining = limit - len(base)
        user_prompt = "x" * (remaining - 2) + "é"
        expected_body = serializer("system", user_prompt, "model")
        self.assertEqual(len(expected_body), limit)

        response = self.fake_api_response('{"findings": []}')
        with patch("urllib.request.OpenerDirector.open", return_value=response) as open_request:
            complete_json("system", user_prompt, api_key="test-secret", model="model")
        self.assertEqual(open_request.call_args.args[0].data, expected_body)

        with patch("urllib.request.OpenerDirector.open") as open_request:
            with self.assertRaisesRegex(DeepSeekError, "request exceeds") as raised:
                complete_json(
                    "system", user_prompt + "x", api_key="test-secret", model="model"
                )
        open_request.assert_not_called()
        self.assertEqual(raised.exception.code, "request_too_large")

    def test_response_exact_limit_is_accepted_with_a_bounded_read(self):
        limit = getattr(deepseek_module, "MAX_RESPONSE_BYTES", None)
        if not isinstance(limit, int):
            self.fail("bounded response limit is not available")
        valid = b'{"model":"deepseek-flash","choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}'
        response = FakeResponse(valid + b" " * (limit - len(valid)))

        with patch("urllib.request.OpenerDirector.open", return_value=response):
            result = self.call_client()

        self.assertEqual(result.payload, {})
        self.assertEqual(response.read_sizes, [limit + 1])
        self.assertTrue(response.closed)

    def test_response_one_byte_over_limit_is_rejected_before_json_decode(self):
        limit = getattr(deepseek_module, "MAX_RESPONSE_BYTES", None)
        if not isinstance(limit, int):
            self.fail("bounded response limit is not available")
        valid = b'{"model":"deepseek-flash","choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}'
        response = FakeResponse(valid + b" " * (limit + 1 - len(valid)))

        with patch("urllib.request.OpenerDirector.open", return_value=response):
            with self.assertRaisesRegex(DeepSeekError, "response exceeds") as raised:
                self.call_client()

        self.assertEqual(raised.exception.code, "response_too_large")
        self.assertEqual(response.read_sizes, [limit + 1])
        self.assertTrue(response.closed)

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

    def test_invalid_content_json_preserves_safe_reason_and_token_usage(self):
        response = self.fake_api_response(
            "{broken",
            usage={"prompt_tokens": 31, "completion_tokens": 7, "total_tokens": 38,
                   "provider_private_field": "must not be retained"},
        )
        with patch("urllib.request.OpenerDirector.open", return_value=response):
            with self.assertRaises(DeepSeekError) as raised:
                self.call_client()

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertEqual(raised.exception.error_detail, "invalid_content_json")
        self.assertEqual(raised.exception.usage, {
            "prompt_tokens": 31, "completion_tokens": 7, "total_tokens": 38,
        })
        self.assertNotIn("provider_private_field", repr(raised.exception.usage))

    def test_invalid_outer_json_has_safe_reason_and_no_usage(self):
        with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(b"not json")):
            with self.assertRaises(DeepSeekError) as raised:
                self.call_client()

        self.assertEqual(raised.exception.error_detail, "invalid_envelope_json")
        self.assertIsNone(raised.exception.usage)

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

    def test_list_models_uses_bounded_get_without_source_or_redirects(self):
        response = FakeResponse({
            "object": "list",
            "data": [
                {"id": "deepseek-flash", "object": "model", "owned_by": "deepseek"},
                {"id": "deepseek-v4-pro", "object": "model", "owned_by": "deepseek"},
            ],
        })
        with patch("urllib.request.OpenerDirector.open", return_value=response) as open_request:
            models = list_models(api_key="test-secret", timeout=10.0)

        self.assertEqual(models, ("deepseek-flash", "deepseek-v4-pro"))
        request = open_request.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/models")
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertEqual(open_request.call_args.kwargs["timeout"], 10.0)
        self.assertEqual(response.read_sizes, [deepseek_module.MAX_RESPONSE_BYTES + 1])
        self.assertTrue(response.closed)

    def test_list_models_rejects_malformed_envelope(self):
        with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(
            {"object": "list", "data": [{"id": 5}]}
        )):
            with self.assertRaises(DeepSeekError) as raised:
                list_models(api_key="test-secret")

        self.assertEqual(raised.exception.code, "invalid_response")

    def test_transport_diagnosis_distinguishes_dns_tls_proxy_and_timeout(self):
        failures = [
            (urllib.error.URLError(socket.gaierror("test-secret")), "dns"),
            (urllib.error.URLError(ssl.SSLError("test-secret")), "tls"),
            (urllib.error.URLError("Tunnel connection failed: 407 test-secret"), "proxy"),
            (urllib.error.URLError(TimeoutError("test-secret")), "timeout"),
        ]
        for failure, expected in failures:
            with self.subTest(category=expected), patch(
                "urllib.request.OpenerDirector.open", side_effect=failure
            ):
                with self.assertRaises(DeepSeekError) as raised:
                    list_models(api_key="test-secret")
            self.assertEqual(raised.exception.diagnostic_category, expected)
            self.assertNotIn("test-secret", str(raised.exception))

    def test_http_diagnosis_distinguishes_account_and_provider_conditions(self):
        for status, expected in ((401, "authentication"), (402, "balance"), (429, "rate_limit"), (503, "server")):
            with self.subTest(status=status):
                failure = urllib.error.HTTPError(
                    "https://api.deepseek.com/models", status, "test-secret", None, io.BytesIO(b"test-secret")
                )
                with patch("urllib.request.OpenerDirector.open", side_effect=failure):
                    with self.assertRaises(DeepSeekError) as raised:
                        list_models(api_key="test-secret")
            self.assertEqual(raised.exception.diagnostic_category, expected)
            self.assertEqual(raised.exception.http_status, status)
            self.assertNotIn("test-secret", str(raised.exception))

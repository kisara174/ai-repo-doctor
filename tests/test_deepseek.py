import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from repo_doctor.deepseek import DeepSeekError, DeepSeekResult, complete_json


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")

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

    def fake_api_response(self, content, finish_reason="stop"):
        return FakeResponse(
            {
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
        )

    def test_complete_json_sends_one_non_streaming_json_request(self):
        response = self.fake_api_response('{"findings": []}')

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            result = complete_json(
                "System prompt",
                "User prompt",
                api_key="test-secret",
                model="deepseek-flash",
            )

        self.assertEqual(result, DeepSeekResult("deepseek-flash", {"findings": []}))
        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 60.0)
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

    def test_http_error_is_sanitized_and_not_retried(self):
        response_body = io.BytesIO(b"test-secret")
        failure = urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions",
            401,
            "Unauthorized",
            hdrs=None,
            fp=response_body,
        )
        with patch("urllib.request.urlopen", side_effect=failure) as urlopen:
            with self.assertRaisesRegex(DeepSeekError, "HTTP 401") as raised:
                self.call_client()

        urlopen.assert_called_once()
        self.assertNotIn("test-secret", str(raised.exception))
        self.assertTrue(response_body.closed)

    def test_url_error_does_not_leak_its_reason(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("test-secret")):
            with self.assertRaises(DeepSeekError) as raised:
                self.call_client()

        self.assertNotIn("test-secret", str(raised.exception))

    def test_timeout_error_does_not_leak_its_message(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("test-secret")):
            with self.assertRaisesRegex(DeepSeekError, "timed out") as raised:
                self.call_client()

        self.assertNotIn("test-secret", str(raised.exception))

    def test_invalid_api_envelope_json_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=FakeResponse(b"not json")):
            with self.assertRaisesRegex(DeepSeekError, "invalid JSON"):
                self.call_client()

    def test_missing_completion_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=FakeResponse({"model": "deepseek-flash", "choices": []})):
            with self.assertRaisesRegex(DeepSeekError, "completion"):
                self.call_client()

    def test_empty_message_content_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=self.fake_api_response("  ")):
            with self.assertRaisesRegex(DeepSeekError, "empty response"):
                self.call_client()

    def test_malformed_model_json_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=self.fake_api_response("{broken")):
            with self.assertRaisesRegex(DeepSeekError, "not valid JSON"):
                self.call_client()

    def test_model_array_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=self.fake_api_response("[]")):
            with self.assertRaisesRegex(DeepSeekError, "must be a JSON object"):
                self.call_client()

    def test_truncated_model_response_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=self.fake_api_response("{}", "length")):
            with self.assertRaisesRegex(DeepSeekError, "truncated"):
                self.call_client()

import io
import json
import unittest
from unittest.mock import patch

from repo_doctor.deepseek import DeepSeekError, DeepSeekResult, complete_json_schema
from repo_doctor.diagnosis import DIAGNOSIS_SCHEMA


class DeepSeekSchemaTests(unittest.TestCase):
    def response(self, text='{"findings": []}', status="completed"):
        return io.BytesIO(json.dumps({
            "id": "response-id",
            "object": "response",
            "created_at": 1710000000,
            "status": status,
            "error": None,
            "incomplete_details": None,
            "model": "deepseek-flash",
            "output": [{
                "type": "message",
                "id": "message-id",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": part, "annotations": []}
                    for part in (text if isinstance(text, list) else [text])
                ],
            }],
            "usage": {
                "input_tokens": 12,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 7,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 19,
            },
            "store": False,
        }).encode("utf-8"))

    def call_client(self):
        return complete_json_schema(
            "System prompt", "User prompt", api_key="test-secret", model="deepseek-flash"
        )

    def test_schema_request_is_explicit_and_parses_output_text(self):
        with patch("urllib.request.OpenerDirector.open", return_value=self.response()) as open_request:
            result = self.call_client()

        self.assertEqual(result, DeepSeekResult(
            "deepseek-flash", {"findings": []},
            {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
        ))
        open_request.assert_called_once()
        request = open_request.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/responses")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {
            "model": "deepseek-flash",
            "input": [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "User prompt"},
            ],
            "reasoning": {"effort": "none"},
            "max_output_tokens": 4096,
            "stream": False,
            "store": False,
            "text": {"format": {
                "type": "json_schema",
                "name": "repo_doctor_findings",
                "schema": DIAGNOSIS_SCHEMA,
            }},
        })

    def test_incomplete_response_is_rejected_without_parsing_content(self):
        with patch("urllib.request.OpenerDirector.open", return_value=self.response(status="incomplete")):
            with self.assertRaises(DeepSeekError) as raised:
                self.call_client()

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertEqual(raised.exception.error_detail, "truncated")

    def test_multiple_output_text_parts_form_one_json_document(self):
        with patch("urllib.request.OpenerDirector.open", return_value=self.response(
            text=['{"find', 'ings": []}']
        )):
            result = self.call_client()

        self.assertEqual(result.payload, {"findings": []})

    def test_invalid_output_text_json_is_sanitized(self):
        with patch("urllib.request.OpenerDirector.open", return_value=self.response(text="{secret")):
            with self.assertRaises(DeepSeekError) as raised:
                self.call_client()

        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertEqual(raised.exception.error_detail, "invalid_content_json")
        self.assertNotIn("secret", str(raised.exception))

    def test_invalid_key_is_rejected_before_transport(self):
        with patch("urllib.request.OpenerDirector.open") as open_request:
            with self.assertRaises(DeepSeekError) as raised:
                complete_json_schema("system", "user", api_key="SECRET\nEXTRA", model="deepseek-flash")

        self.assertEqual(raised.exception.code, "invalid_key")
        self.assertNotIn("SECRET", str(raised.exception))
        open_request.assert_not_called()

    def test_oversized_wire_request_is_rejected_before_transport(self):
        with patch("urllib.request.OpenerDirector.open") as open_request:
            with self.assertRaises(DeepSeekError) as raised:
                complete_json_schema(
                    "system", "x" * (300 * 1024),
                    api_key="test-secret", model="deepseek-flash",
                )

        self.assertEqual(raised.exception.code, "request_too_large")
        open_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()

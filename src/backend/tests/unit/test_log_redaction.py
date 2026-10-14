"""Unit tests for app.services.log_redaction.redact_raw_context()."""

from app.services.log_redaction import REDACTED, redact_raw_context


class TestRedactRawContext:
    def test_redacts_request_headers_that_carry_credentials(self) -> None:
        headers = {
            "Host": ["app.example.com"],
            "User-Agent": ["curl/8.11.1"],
            "Cookie": ["session=abc123"],
            "Authorization": ["Bearer eyJhbGciOi"],
            "X-Api-Key": ["key-123"],
            "X-CSRF-Token": ["csrf-456"],
            "X-Request-Id": ["tx-1"],
        }

        redacted = redact_raw_context({"transaction": {"request": {"headers": headers}}})

        result = redacted["transaction"]["request"]["headers"]
        assert result["Host"] == ["app.example.com"]
        assert result["User-Agent"] == ["curl/8.11.1"]
        assert result["X-Request-Id"] == ["tx-1"]
        assert result["Cookie"] == REDACTED
        assert result["Authorization"] == REDACTED
        assert result["X-Api-Key"] == REDACTED
        assert result["X-CSRF-Token"] == REDACTED

    def test_redacts_credential_fields_at_any_depth(self) -> None:
        event = {
            "transaction": {"request": {"args": {"password": "hunter2"}}},
            "messages": [{"data": {"api_key": "k", "msg": "SQL Injection"}}],
        }

        redacted = redact_raw_context(event)

        assert redacted["transaction"]["request"]["args"]["password"] == REDACTED
        assert redacted["messages"][0]["data"]["api_key"] == REDACTED
        assert redacted["messages"][0]["data"]["msg"] == "SQL Injection"

    def test_keeps_error_message_text_the_suggester_parses(self) -> None:
        """A sensitive word inside a value must not blank the whole message."""
        message = "[data \"Matched Data: token found within ARGS:token\"]"

        redacted = redact_raw_context({"messages": [{"error_message": message}]})

        assert redacted["messages"][0]["error_message"] == message

    def test_leaves_input_untouched(self) -> None:
        event = {"transaction": {"request": {"headers": {"Cookie": ["s=1"]}}}}

        redact_raw_context(event)

        assert event["transaction"]["request"]["headers"]["Cookie"] == ["s=1"]

    def test_handles_empty_and_scalar_values(self) -> None:
        assert redact_raw_context({}) == {}
        assert redact_raw_context([]) == []
        assert redact_raw_context(None) is None
        assert redact_raw_context("plain") == "plain"

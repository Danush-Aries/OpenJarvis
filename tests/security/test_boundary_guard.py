"""Tests for BoundaryGuard — scanning at device exit points."""

from __future__ import annotations

import pytest

from openjarvis.core.types import ToolCall


class TestBoundaryGuardScanOutbound:
    """scan_outbound should detect and redact secrets/PII."""

    def test_redacts_openai_key(self) -> None:
        from openjarvis.security.boundary import BoundaryGuard

        guard = BoundaryGuard(mode="redact")
        text = "Use this key: sk-proj-abc123def456ghi789jkl012mno345pqr678stu"
        result = guard.scan_outbound(text, destination="openai")
        assert "sk-proj-" not in result
        assert "[REDACTED" in result

    def test_redacts_aws_key(self) -> None:
        from openjarvis.security.boundary import BoundaryGuard

        guard = BoundaryGuard(mode="redact")
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        result = guard.scan_outbound(text, destination="openai")
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_warn_mode_does_not_alter_text(self) -> None:
        from openjarvis.security.boundary import BoundaryGuard

        guard = BoundaryGuard(mode="warn")
        text = "Use this key: sk-proj-abc123def456ghi789jkl012mno345pqr678stu"
        result = guard.scan_outbound(text, destination="openai")
        assert result == text

    def test_block_mode_raises(self) -> None:
        from openjarvis.security.boundary import BoundaryGuard, SecurityBlockError

        guard = BoundaryGuard(mode="block")
        text = "Use this key: sk-proj-abc123def456ghi789jkl012mno345pqr678stu"
        with pytest.raises(SecurityBlockError):
            guard.scan_outbound(text, destination="openai")

    def test_clean_text_passes_through(self) -> None:
        from openjarvis.security.boundary import BoundaryGuard

        guard = BoundaryGuard(mode="redact")
        text = "Hello, how are you?"
        result = guard.scan_outbound(text, destination="openai")
        assert result == text


class TestBoundaryGuardCheckOutbound:
    """check_outbound should redact secrets in tool call arguments."""

    def test_redacts_tool_call_arguments(self) -> None:
        from openjarvis.security.boundary import BoundaryGuard

        guard = BoundaryGuard(mode="redact")
        tc = ToolCall(
            id="test_1",
            name="web_search",
            arguments=(
                '{"query": "my key is sk-proj-abc123def456ghi789jkl012mno345pqr678stu"}'
            ),
        )
        result = guard.check_outbound(tc)
        assert "sk-proj-" not in result.arguments
        assert result.id == "test_1"
        assert result.name == "web_search"

    def test_clean_args_pass_through(self) -> None:
        from openjarvis.security.boundary import BoundaryGuard

        guard = BoundaryGuard(mode="redact")
        tc = ToolCall(id="test_2", name="web_search", arguments='{"query": "weather"}')
        result = guard.check_outbound(tc)
        assert result.arguments == tc.arguments

    def test_block_mode_raises_on_tool_call(self) -> None:
        from openjarvis.security.boundary import BoundaryGuard, SecurityBlockError

        guard = BoundaryGuard(mode="block")
        tc = ToolCall(
            id="test_3",
            name="web_search",
            arguments='{"query": "AKIAIOSFODNN7EXAMPLE"}',
        )
        with pytest.raises(SecurityBlockError):
            guard.check_outbound(tc)


class TestBoundaryGuardDisabled:
    """When disabled, BoundaryGuard should pass everything through."""

    def test_disabled_passes_secrets_through(self) -> None:
        from openjarvis.security.boundary import BoundaryGuard

        guard = BoundaryGuard(mode="redact", enabled=False)
        text = "sk-proj-abc123def456ghi789jkl012mno345pqr678stu"
        result = guard.scan_outbound(text, destination="openai")
        assert result == text

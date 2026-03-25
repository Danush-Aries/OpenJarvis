"""Tests for the gemma.cpp engine backend."""

from __future__ import annotations

import os

import pytest

from openjarvis.core.config import EngineConfig, GemmaCppEngineConfig


class TestGemmaCppEngineConfig:
    def test_default_values(self) -> None:
        cfg = GemmaCppEngineConfig()
        assert cfg.model_path == ""
        assert cfg.tokenizer_path == ""
        assert cfg.model_type == ""
        assert cfg.num_threads == 0

    def test_engine_config_has_gemma_cpp_field(self) -> None:
        ec = EngineConfig()
        assert hasattr(ec, "gemma_cpp")
        assert isinstance(ec.gemma_cpp, GemmaCppEngineConfig)


from openjarvis.core.types import Message, Role


class TestMessagesToPrompt:
    def _make_engine(self):
        """Create engine with no paths (won't load model, just test formatting)."""
        from openjarvis.engine.gemma_cpp import GemmaCppEngine
        return GemmaCppEngine()

    def test_single_user_message(self) -> None:
        engine = self._make_engine()
        msgs = [Message(role=Role.USER, content="Hello")]
        result = engine._messages_to_prompt(msgs)
        assert result == (
            "<start_of_turn>user\nHello<end_of_turn>\n"
            "<start_of_turn>model\n"
        )

    def test_system_folded_into_user(self) -> None:
        engine = self._make_engine()
        msgs = [
            Message(role=Role.SYSTEM, content="You are helpful."),
            Message(role=Role.USER, content="Hello"),
        ]
        result = engine._messages_to_prompt(msgs)
        assert result == (
            "<start_of_turn>user\n"
            "You are helpful.\n\nHello<end_of_turn>\n"
            "<start_of_turn>model\n"
        )

    def test_multi_turn_conversation(self) -> None:
        engine = self._make_engine()
        msgs = [
            Message(role=Role.USER, content="Hi"),
            Message(role=Role.ASSISTANT, content="Hello!"),
            Message(role=Role.USER, content="How are you?"),
        ]
        result = engine._messages_to_prompt(msgs)
        assert result == (
            "<start_of_turn>user\nHi<end_of_turn>\n"
            "<start_of_turn>model\nHello!<end_of_turn>\n"
            "<start_of_turn>user\nHow are you?<end_of_turn>\n"
            "<start_of_turn>model\n"
        )

    def test_trailing_system_message_discarded(self) -> None:
        engine = self._make_engine()
        msgs = [
            Message(role=Role.SYSTEM, content="Ignored system"),
        ]
        result = engine._messages_to_prompt(msgs)
        assert result == "<start_of_turn>model\n"

    def test_multiple_system_messages_concatenated(self) -> None:
        engine = self._make_engine()
        msgs = [
            Message(role=Role.SYSTEM, content="Rule 1"),
            Message(role=Role.SYSTEM, content="Rule 2"),
            Message(role=Role.USER, content="Go"),
        ]
        result = engine._messages_to_prompt(msgs)
        assert result == (
            "<start_of_turn>user\n"
            "Rule 1\n\nRule 2\n\nGo<end_of_turn>\n"
            "<start_of_turn>model\n"
        )

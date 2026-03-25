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

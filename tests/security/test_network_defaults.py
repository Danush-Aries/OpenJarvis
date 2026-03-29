"""Tests for secure network defaults (Section 1 of security hardening)."""

from __future__ import annotations


class TestServerConfigDefaults:
    """ServerConfig should bind to loopback by default."""

    def test_default_host_is_loopback(self) -> None:
        from openjarvis.core.config import ServerConfig

        cfg = ServerConfig()
        assert cfg.host == "127.0.0.1"

    def test_default_port_unchanged(self) -> None:
        from openjarvis.core.config import ServerConfig

        cfg = ServerConfig()
        assert cfg.port == 8000

    def test_cors_origins_default(self) -> None:
        from openjarvis.core.config import ServerConfig

        cfg = ServerConfig()
        assert isinstance(cfg.cors_origins, list)
        assert "http://localhost:3000" in cfg.cors_origins
        assert "http://localhost:5173" in cfg.cors_origins
        assert "tauri://localhost" in cfg.cors_origins
        assert "*" not in cfg.cors_origins


class TestSecurityConfigDefaults:
    """SecurityConfig should default to redact mode with rate limiting."""

    def test_default_mode_is_redact(self) -> None:
        from openjarvis.core.config import SecurityConfig

        cfg = SecurityConfig()
        assert cfg.mode == "redact"

    def test_rate_limiting_enabled_by_default(self) -> None:
        from openjarvis.core.config import SecurityConfig

        cfg = SecurityConfig()
        assert cfg.rate_limit_enabled is True

    def test_bypass_defaults_conservative(self) -> None:
        from openjarvis.core.config import SecurityConfig

        cfg = SecurityConfig()
        assert cfg.local_engine_bypass is False
        assert cfg.local_tool_bypass is False

    def test_profile_default_empty(self) -> None:
        from openjarvis.core.config import SecurityConfig

        cfg = SecurityConfig()
        assert cfg.profile == ""

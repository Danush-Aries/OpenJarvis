"""Tests for the app launcher tools."""

from __future__ import annotations

import sys
import unittest.mock as mock
import pytest

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools.app_launcher import AppLaunchTool, ListAppsTool


class TestAppLaunchTool:
    def test_registry(self):
        # Register explicitly since pytest conftest clears all registries for isolation
        ToolRegistry.register_value("launch_app", AppLaunchTool)
        assert ToolRegistry.contains("launch_app")
        tool = ToolRegistry.create("launch_app")
        assert isinstance(tool, AppLaunchTool)

    def test_spec(self):
        tool = AppLaunchTool()
        assert tool.spec.name == "launch_app"
        assert tool.spec.category == "system"
        assert "app" in tool.spec.parameters["properties"]
        assert "url" in tool.spec.parameters["properties"]

    @mock.patch("sys.platform", "linux")
    def test_execute_empty(self):
        tool = AppLaunchTool()
        result = tool.execute()
        assert result.success is False
        assert "Provide an app name or URL to open" in result.content

    @mock.patch("sys.platform", "linux")
    def test_execute_unknown_app(self):
        tool = AppLaunchTool()
        result = tool.execute(app="non_existent_app_12345")
        assert result.success is False
        assert "Unknown application" in result.content

    @mock.patch("sys.platform", "linux")
    @mock.patch("subprocess.Popen")
    def test_execute_known_app(self, mock_popen):
        tool = AppLaunchTool()
        # vscode is a known app in KNOWN_APPS
        result = tool.execute(app="vscode", args=["--version"])
        assert result.success is True
        assert "Launched Visual Studio Code" in result.content
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "code" in args
        assert "--version" in args

    @mock.patch("sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_execute_macos_alias_success(self, mock_run):
        mock_run.return_value.returncode = 0
        tool = AppLaunchTool()
        result = tool.execute(app="chrome", args=["--new-window"])
        assert result.success is True
        assert "Successfully launched 'Google Chrome' on macOS" in result.content
        mock_run.assert_called_once_with(
            ["open", "-a", "Google Chrome", "--new-window"],
            stdout=mock.ANY,
            stderr=mock.ANY,
            timeout=2.0
        )

    @mock.patch("sys.platform", "darwin")
    @mock.patch("subprocess.run")
    @mock.patch("subprocess.Popen")
    def test_execute_macos_fallback_to_linux(self, mock_popen, mock_run):
        mock_run.return_value.returncode = 1
        tool = AppLaunchTool()
        result = tool.execute(app="vscode")
        assert mock_run.called

    @mock.patch("webbrowser.open")
    def test_execute_open_url_webbrowser(self, mock_web_open):
        tool = AppLaunchTool()
        result = tool.execute(url="https://google.com")
        assert result.success is True
        assert "Opened https://google.com with default web browser" in result.content
        mock_web_open.assert_called_once_with("https://google.com")

    @mock.patch("webbrowser.open", side_error=Exception("webbrowser failed"))
    @mock.patch("subprocess.Popen")
    @mock.patch("os.startfile", create=True)
    def test_execute_open_url_fallback(self, mock_startfile, mock_popen, mock_web_open):
        # Force webbrowser.open to raise an exception to test fallback behavior
        mock_web_open.side_effect = Exception("webbrowser failed")
        tool = AppLaunchTool()
        
        # Test depending on platform
        result = tool.execute(url="https://google.com")
        assert result.success is True
        assert "Opened https://google.com" in result.content
        
        if sys.platform == "darwin":
            mock_popen.assert_called_once()
            assert mock_popen.call_args[0][0] == ["open", "https://google.com"]
        elif sys.platform.startswith("win"):
            mock_startfile.assert_called_once_with("https://google.com")
        else:
            mock_popen.assert_called_once()
            assert mock_popen.call_args[0][0] == ["xdg-open", "https://google.com"]


class TestListAppsTool:
    def test_registry(self):
        # Register explicitly since pytest conftest clears all registries for isolation
        ToolRegistry.register_value("list_apps", ListAppsTool)
        assert ToolRegistry.contains("list_apps")
        tool = ToolRegistry.create("list_apps")
        assert isinstance(tool, ListAppsTool)

    def test_spec(self):
        tool = ListAppsTool()
        assert tool.spec.name == "list_apps"
        assert tool.spec.category == "system"

    def test_execute_all(self):
        tool = ListAppsTool()
        result = tool.execute()
        assert result.success is True
        import json
        data = json.loads(result.content)
        assert "apps" in data
        assert data["count"] > 0
        assert data["category"] == "all"

    def test_execute_filter(self):
        tool = ListAppsTool()
        result = tool.execute(category="browser")
        assert result.success is True
        import json
        data = json.loads(result.content)
        assert data["category"] == "browser"
        for app in data["apps"]:
            assert app["category"] == "browser"

"""Desktop application launcher tool — open apps, list available apps, manage processes.

Gives Jarvis the ability to open desktop applications like a true AI companion.
Uses subprocess to launch apps in the background.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inline registry (kept for compatibility)
# ---------------------------------------------------------------------------
_TOOLS: Dict[str, Any] = {}

def register(cls: Any) -> Any:
    _TOOLS[cls.__name__] = cls
    return cls

def get_tools() -> List[Any]:
    return list(_TOOLS.values())

# ---------------------------------------------------------------------------
# Known applications — common Linux desktop apps
# ---------------------------------------------------------------------------

KNOWN_APPS: Dict[str, Dict[str, Any]] = {
    "firefox": {
        "name": "Firefox",
        "command": ["firefox"],
        "description": "Web browser",
        "category": "browser",
    },
    "chromium": {
        "name": "Chromium",
        "command": ["chromium-browser"],
        "description": "Web browser",
        "category": "browser",
    },
    "google-chrome": {
        "name": "Google Chrome",
        "command": ["google-chrome"],
        "description": "Web browser",
        "category": "browser",
    },
    "vscode": {
        "name": "Visual Studio Code",
        "command": ["code"],
        "description": "Code editor",
        "category": "development",
    },
    "code": {
        "name": "Visual Studio Code",
        "command": ["code"],
        "description": "Code editor",
        "category": "development",
    },
    "terminal": {
        "name": "Terminal",
        "command": ["gnome-terminal"],
        "description": "Terminal emulator",
        "category": "system",
    },
    "gnome-terminal": {
        "name": "GNOME Terminal",
        "command": ["gnome-terminal"],
        "description": "Terminal emulator",
        "category": "system",
    },
    "kitty": {
        "name": "Kitty Terminal",
        "command": ["kitty"],
        "description": "Terminal emulator",
        "category": "system",
    },
    "alacritty": {
        "name": "Alacritty",
        "command": ["alacritty"],
        "description": "Terminal emulator",
        "category": "system",
    },
    "nautilus": {
        "name": "Files",
        "command": ["nautilus"],
        "description": "File manager",
        "category": "system",
    },
    "slack": {
        "name": "Slack",
        "command": ["slack"],
        "description": "Team communication",
        "category": "communication",
    },
    "discord": {
        "name": "Discord",
        "command": ["discord"],
        "description": "Voice/text chat",
        "category": "communication",
    },
    "spotify": {
        "name": "Spotify",
        "command": ["spotify"],
        "description": "Music streaming",
        "category": "media",
    },
    "vlc": {
        "name": "VLC Media Player",
        "command": ["vlc"],
        "description": "Media player",
        "category": "media",
    },
    "calculator-gui": {
        "name": "Calculator",
        "command": ["gnome-calculator"],
        "description": "Desktop calculator",
        "category": "utilities",
    },
    "settings": {
        "name": "Settings",
        "command": ["gnome-control-center"],
        "description": "System settings",
        "category": "system",
    },
}


@register
@ToolRegistry.register("launch_app")
class AppLaunchTool(BaseTool):
    """Launch desktop applications by name.

    Opens the application in the background using the system's preferred
    method (xdg-open, desktop file, or direct binary). Supports common
    Linux desktop applications like browsers, terminals, editors, and more.
    """

    tool_id = "launch_app"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="launch_app",
            description=(
                "Open a desktop application. Supports browsers (firefox, chrome), "
                "terminals (gnome-terminal, kitty), editors (vscode, code), file managers, "
                "communication apps (slack, discord), media players, and more. "
                "Use 'open' to open files or URLs with the default application."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "Application name or path to open. Known apps: firefox, chrome, vscode, terminal, slack, discord, spotify, nautilus, settings",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional arguments to pass to the application (e.g., a URL for browser, a file path for editor)",
                        "default": [],
                    },
                    "url": {
                        "type": "string",
                        "description": "URL or file path to open with the default application (uses local Python webbrowser/launcher). Overrides 'app' if provided.",
                        "default": "",
                    },
                },
                "required": [],
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        app = params.get("app", "")
        args = params.get("args") or []
        url = params.get("url", "")

        if url:
            return self._open_url(url)
        if not app:
            return ToolResult(
                tool_name="launch_app",
                content="Provide an app name or URL to open",
                success=False,
            )

        app = app.lower().strip()
        args = args or []

        # ── macOS native launcher with smart alias resolution ──────────────
        import sys
        if sys.platform == "darwin":
            mac_aliases = {
                "chrome": "Google Chrome",
                "google-chrome": "Google Chrome",
                "google chrome": "Google Chrome",
                "vscode": "Visual Studio Code",
                "code": "Visual Studio Code",
                "visual studio code": "Visual Studio Code",
                "firefox": "Firefox",
                "safari": "Safari",
                "spotify": "Spotify",
                "terminal": "Terminal",
                "slack": "Slack",
                "discord": "Discord",
                "finder": "Finder",
                "settings": "System Settings",
                "system settings": "System Settings",
                "system-settings": "System Settings",
                "calculator": "Calculator",
                "calendar": "Calendar",
                "notes": "Notes",
                "mail": "Mail",
                "messages": "Messages",
                "facetime": "FaceTime",
                "maps": "Maps",
                "photos": "Photos",
                "reminders": "Reminders",
                "app-store": "App Store",
                "app store": "App Store",
                "safari browser": "Safari",
                "activity monitor": "Activity Monitor",
                "keychain": "Keychain Access",
                "keychain access": "Keychain Access",
                "pages": "Pages",
                "numbers": "Numbers",
                "keynote": "Keynote",
            }
            target_app = mac_aliases.get(app, app)
            try:
                res = subprocess.run(
                    ["open", "-a", target_app] + args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2.0
                )
                if res.returncode == 0:
                    return ToolResult(
                        tool_name="launch_app",
                        content=f"Successfully launched '{target_app}' on macOS",
                        success=True,
                        metadata={
                            "app": target_app,
                            "method": "open_a",
                            "args": args
                        }
                    )
            except Exception as e:
                logger.debug("macOS open -a failed: %s. Falling back to standard paths.", e)

        # Check if it's a known app
        known = KNOWN_APPS.get(app)
        if known:
            command = known["command"] + args
            display_name = known["name"]
        else:
            # Try to find the binary or use as-is
            binary = shutil.which(app)
            if binary:
                command = [binary] + args
                display_name = app
            else:
                return ToolResult(
                    tool_name="launch_app",
                    content=f"Unknown application '{app}'. Try one of: {', '.join(sorted(KNOWN_APPS.keys())[:15])}",
                    success=False,
                )

        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return ToolResult(
                tool_name="launch_app",
                content=f"Launched {display_name}",
                success=True,
                metadata={
                    "app": app,
                    "command": " ".join(command),
                }
            )
        except FileNotFoundError:
            return ToolResult(
                tool_name="launch_app",
                content=f"Could not find '{display_name}' on this system. The application may not be installed.",
                success=False,
            )
        except Exception as e:
            logger.error("Failed to launch %s: %s", app, e)
            return ToolResult(
                tool_name="launch_app",
                content=f"Failed to launch {display_name}: {str(e)}",
                success=False,
            )

    def _open_url(self, url: str) -> ToolResult:
        """Open a URL or file with the default system application using webbrowser."""
        try:
            import webbrowser
            # Using webbrowser.open is cross-platform, safe, local, and doesn't run external shell processes unless needed.
            webbrowser.open(url)
            return ToolResult(
                tool_name="launch_app",
                content=f"Opened {url} with default web browser",
                success=True,
                metadata={"url": url}
            )
        except Exception as e:
            # Fallback to os/platform-specific commands if webbrowser fails
            try:
                import sys
                import os
                if sys.platform == "darwin":
                    subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                elif sys.platform.startswith("win"):
                    os.startfile(url)
                else:
                    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return ToolResult(
                    tool_name="launch_app",
                    content=f"Opened {url} with fallback platform launcher",
                    success=True,
                    metadata={"url": url}
                )
            except Exception as fe:
                logger.error("Failed to open %s: %s", url, fe)
                return ToolResult(
                    tool_name="launch_app",
                    content=f"Failed to open {url}: {str(fe)}",
                    success=False,
                )


@register
@ToolRegistry.register("list_apps")
class ListAppsTool(BaseTool):
    """List available desktop applications that Jarvis can launch."""

    tool_id = "list_apps"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_apps",
            description="List all available desktop applications that can be launched, optionally filtered by category.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["browser", "development", "system", "communication", "media", "utilities"],
                        "description": "Filter by category (optional)",
                        "default": "",
                    },
                },
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        category = params.get("category", "")
        apps = []
        for key, info in KNOWN_APPS.items():
            if category and info.get("category") != category:
                continue
            apps.append({
                "key": key,
                "name": info["name"],
                "description": info["description"],
                "category": info.get("category", "other"),
                "available": shutil.which(info["command"][0]) is not None,
            })

        import json
        return ToolResult(
            tool_name="list_apps",
            content=json.dumps({
                "apps": apps,
                "count": len(apps),
                "category": category or "all",
            }),
            success=True,
            metadata={
                "category": category,
                "count": len(apps)
            }
        )

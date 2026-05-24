"""Local Ollama Engine tool — offline local query generation."""

from __future__ import annotations

import httpx
from typing import Any, List, Dict
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


@ToolRegistry.register("ollama_generate")
class OllamaGenerateTool(BaseTool):
    """Generates completions offline using a local Ollama server on port 11434."""

    tool_id = "ollama_generate"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="ollama_generate",
            description=(
                "Generate natural language responses offline using a local Ollama server."
                " Useful when internet is down or for high-speed, private local reasoning."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The main text prompt to send to the local model.",
                    },
                    "system": {
                        "type": "string",
                        "description": "Optional background instruction/system context for the local model.",
                    },
                    "model": {
                        "type": "string",
                        "description": "Local model name (e.g. 'qwen2.5-coder', 'llama3.2', 'mistral'). Default: 'qwen2.5-coder' or 'llama3.2'.",
                    },
                },
                "required": ["prompt"],
            },
            category="inference",
        )

    def execute(self, **params: Any) -> ToolResult:
        prompt = params.get("prompt", "").strip()
        if not prompt:
            return ToolResult(
                tool_name="ollama_generate",
                content="No prompt provided.",
                success=False,
            )

        system = params.get("system", "").strip()
        # Default to commonly installed local lightweight models on 8GB RAM systems
        model = params.get("model", "").strip() or "qwen2.5-coder:3b"

        url = "http://127.0.0.1:11434/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            # We connect locally with a short timeout to fail fast if Ollama is not active
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    response_text = data.get("response", "").strip()
                    return ToolResult(
                        tool_name="ollama_generate",
                        content=response_text,
                        success=True,
                        metadata={"model": model, "eval_duration": data.get("eval_duration")},
                    )
                else:
                    return ToolResult(
                        tool_name="ollama_generate",
                        content=f"Ollama returned HTTP error status: {resp.status_code}",
                        success=False,
                    )
        except httpx.ConnectError:
            # Fallback message suggesting model names if connection fails
            return ToolResult(
                tool_name="ollama_generate",
                content=(
                    "Could not connect to the local Ollama server. "
                    "Make sure Ollama is actively running on port 11434. "
                    "You can start it on macOS using the Ollama menu app or by running 'ollama serve' in your terminal."
                ),
                success=False,
            )
        except Exception as e:
            return ToolResult(
                tool_name="ollama_generate",
                content=f"Ollama generation exception: {str(e)}",
                success=False,
            )


__all__ = ["OllamaGenerateTool"]

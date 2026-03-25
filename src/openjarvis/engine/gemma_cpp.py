"""gemma.cpp inference engine backend via pygemma pybind11 bindings."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Sequence
from typing import Any, Dict, List

from openjarvis.core.registry import EngineRegistry
from openjarvis.core.types import Message, Role
from openjarvis.engine._base import InferenceEngine, estimate_prompt_tokens

logger = logging.getLogger(__name__)


@EngineRegistry.register("gemma_cpp")
class GemmaCppEngine(InferenceEngine):
    """gemma.cpp backend via pygemma pybind11 bindings (in-process, CPU)."""

    engine_id = "gemma_cpp"

    def __init__(
        self,
        model_path: str | None = None,
        tokenizer_path: str | None = None,
        model_type: str | None = None,
        num_threads: int = 0,
    ) -> None:
        self._model_path = (
            model_path
            or os.environ.get("GEMMA_CPP_MODEL_PATH", "")
        )
        self._tokenizer_path = (
            tokenizer_path
            or os.environ.get("GEMMA_CPP_TOKENIZER_PATH", "")
        )
        self._model_type = (
            model_type
            or os.environ.get("GEMMA_CPP_MODEL_TYPE", "")
        )
        self._num_threads = num_threads or int(
            os.environ.get("GEMMA_CPP_NUM_THREADS", "0")
        )
        self._gemma: Any = None  # lazy-loaded pygemma.Gemma instance

    def _messages_to_prompt(self, messages: Sequence[Message]) -> str:
        """Format messages into Gemma's chat template."""
        parts: list[str] = []
        system_prefix = ""
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_prefix += msg.content + "\n\n"
            elif msg.role == Role.USER:
                content = (
                    system_prefix + msg.content if system_prefix else msg.content
                )
                system_prefix = ""
                parts.append(f"<start_of_turn>user\n{content}<end_of_turn>\n")
            elif msg.role == Role.ASSISTANT:
                parts.append(
                    f"<start_of_turn>model\n{msg.content}<end_of_turn>\n"
                )
        parts.append("<start_of_turn>model\n")
        return "".join(parts)

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        raise NotImplementedError  # implemented in Task 4

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        raise NotImplementedError  # implemented in Task 4
        yield ""  # pragma: no cover

    def list_models(self) -> List[str]:
        raise NotImplementedError  # implemented in Task 5

    def health(self) -> bool:
        raise NotImplementedError  # implemented in Task 5

    def close(self) -> None:
        pass  # implemented in Task 4

    def prepare(self, model: str) -> None:
        pass  # implemented in Task 4


__all__ = ["GemmaCppEngine"]

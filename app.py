"""Jarvis API server — wires all routers into a single FastAPI app.

Usage:
    uvicorn app:app --reload --port 9099

Or:
    python app.py
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure src/ is on sys.path so internal modules can use `from openjarvis...` imports
_src = str(Path(__file__).parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("jarvis")


# ---------------------------------------------------------------------------
# Lifespan context manager — replaces deprecated @app.on_event decorators
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle application startup and shutdown."""
    # ---- STARTUP ----
    from openjarvis.core.credentials import get_credentials
    creds = get_credentials()

    # Warm up the default soul (creates one if it doesn't exist yet)
    _default_soul_status = ""
    try:
        from openjarvis.soul import Soul
        default = Soul.load_or_create("default")
        mem_stats = default.memory.stats()
        _default_soul_status = (
            f"{mem_stats['total']} memories "
            f"(E:{mem_stats['episodic']} S:{mem_stats['semantic']} P:{mem_stats['procedural']}), "
            f"evolved {default.persona.evolution_count}x"
        )
        logger.info("    Soul:  %s default [%s]",
                     chr(10003), _default_soul_status)
    except Exception as e:
        logger.info("    Soul:  O (%s)", e)

    logger.info("")
    logger.info("Jarvis API Server v0.2.0")
    logger.info("  Endpoints:")
    logger.info("    POST /v1/chat        - Conversational AI")
    logger.info("    POST /v1/chat/stream  - Streaming AI")
    logger.info("    POST /v1/voice/speak  - Text-to-Speech")
    logger.info("    GET  /v1/soul/*       - Persistent Identity & Memory")
    logger.info("    GET  /v1/projects/*   - Project Management")
    logger.info("    GET  /v1/graph/*      - Knowledge Graph")
    logger.info("  Services:")
    logger.info("    LLM:   %s %s",
                chr(10003) if creds.llm_available else "O",
                creds.llm_model)
    logger.info("    TTS:   %s Cartesia",
                chr(10003) if creds.tts_available else "O")
    logger.info("    Web:   %s Tavily Search",
                chr(10003) if creds.web_search_available else "O")
    logger.info("    STT:   %s Deepgram",
                chr(10003) if creds.stt_available else "O")
    logger.info("  Tools loaded: %d", _tool_count)
    logger.info("")

    yield

    # ---- SHUTDOWN ----
    try:
        from openjarvis.soul import Soul
        before = len(Soul.list_souls())
        Soul.close_all()
        if before:
            logger.info("Closed all %d cached souls gracefully", before)
    except Exception:
        pass
    logger.info("Jarvis API Server shutting down")


app = FastAPI(title="Jarvis API", version="0.2.0", lifespan=lifespan)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:9099",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Register all routers at module level (not inside startup event)
# ---------------------------------------------------------------------------

# Chat & Conversation
from openjarvis.server.router_chat import router as chat_router
app.include_router(chat_router)

# Soul — persistent identity, memory, and evolving personality
from openjarvis.server.router_soul import router as soul_router
app.include_router(soul_router)

# Voice / TTS
from openjarvis.server.router_voice import router as voice_router
app.include_router(voice_router)

# Projects & Tasks
from openjarvis.server.router_projects import projects_router
app.include_router(projects_router)

# Knowledge Graph
from openjarvis.server.router_graph import graph_router
app.include_router(graph_router)

# Warm up tool registries
from openjarvis.tools import neural_graph_tools, project_tools, learning_tools
from openjarvis.tools.web_search import get_tools as get_web_tools
from openjarvis.tools.file_read import get_tools as get_file_read_tools
from openjarvis.tools.file_write import get_tools as get_file_write_tools
from openjarvis.tools.shell_exec import get_tools as get_shell_tools
from openjarvis.tools.git_tool import get_tools as get_git_tools
from openjarvis.tools.code_interpreter import get_tools as get_code_interp_tools
from openjarvis.tools.apply_patch import get_tools as get_patch_tools
from openjarvis.tools.http_request import get_tools as get_http_tools
from openjarvis.tools.calculator import get_tools as get_calc_tools
from openjarvis.tools.browser import get_tools as get_browser_tools
from openjarvis.tools.repl import get_tools as get_repl_tools
from openjarvis.tools.agent_tools import get_tools as get_agent_tools
from openjarvis.tools.app_launcher import get_tools as get_app_tools
from openjarvis.tools.finance_tool import get_tools as get_finance_tools

_tool_count = (
    len(neural_graph_tools.get_tools())
    + len(project_tools.get_tools())
    + len(learning_tools.get_tools())
    + len(get_web_tools())
    + len(get_file_read_tools())
    + len(get_file_write_tools())
    + len(get_shell_tools())
    + len(get_git_tools())
    + len(get_code_interp_tools())
    + len(get_patch_tools())
    + len(get_http_tools())
    + len(get_calc_tools())
    + len(get_browser_tools())
    + len(get_repl_tools())
    + len(get_agent_tools())
    + len(get_app_tools())
    + len(get_finance_tools())
)


# ---------------------------------------------------------------------------
# Health & status
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    return {"service": "Jarvis", "status": "online", "version": "0.2.0"}


@app.get("/health")
async def health():
    from openjarvis.core.credentials import get_credentials
    creds = get_credentials()

    # Gather soul status
    try:
        from openjarvis.soul import Soul
        soul_names = Soul.list_souls()
        soul_info = {
            "count": len(soul_names),
            "names": soul_names[:10],  # cap to avoid huge responses
        }
        # Stats for the default soul
        if "default" in soul_names:
            try:
                default_soul = Soul.load_or_create("default")
                soul_info["default_memory_stats"] = default_soul.memory.stats()
                soul_info["default_persona_evolutions"] = default_soul.persona.evolution_count
            except Exception:
                pass
    except Exception:
        soul_info = {"count": 0, "names": []}

    return {
        "status": "ok",
        "version": "0.2.0",
        "services": {
            "llm": creds.llm_available,
            "web_search": creds.web_search_available,
            "tts": creds.tts_available,
            "stt": creds.stt_available,
        },
        "soul": soul_info,
        "tools_loaded": _tool_count,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=9099, reload=True)

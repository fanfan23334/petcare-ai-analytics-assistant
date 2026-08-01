"""PetCare AI Analytics Assistant - application entry.

Assembles the dependency graph:
    PetCareConfig -> MySQLRunner -> SafeRunSqlTool -> ToolRegistry
    PetCareSystemPromptBuilder + create_llm_service(config) -> Agent
    Agent + SafeChatHandler -> FastAPI app (register_chat_routes)

Run:
    python -m petcare.main            # uvicorn on 0.0.0.0:8000
"""

from __future__ import annotations

import logging
import os
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from vanna import Agent
from vanna.core.agent.config import AgentConfig, UiFeature, UiFeatures
from vanna.core.registry import ToolRegistry
from vanna.integrations.mysql import MySQLRunner
from vanna.servers.base import ChatHandler, ChatRequest, ChatStreamChunk
from vanna.servers.base.templates import get_index_html
from vanna.servers.fastapi.routes import register_chat_routes

from .config import load_config
from .llm_factory import create_llm_service
from .prompts import PetCareSystemPromptBuilder
from .safety import SafeRunSqlTool

logger = logging.getLogger("petcare")

PAGE_TITLE = "PetCare AI Analytics Assistant"
H1_MARKUP = (
    '<h1 class="text-4xl font-bold text-vanna-navy mb-2 font-serif">'
    "Vanna Agents</h1>"
)
H1_MARKUP_PETCARE = (
    '<h1 class="text-4xl font-bold text-vanna-navy mb-2 font-serif">'
    f"{PAGE_TITLE}</h1>"
)

# map common provider errors to user-safe messages (no secrets, no stack traces)
SAFE_ERROR_MESSAGES: tuple[tuple[str, str], ...] = (
    ("authenticationerror", "模型服务认证失败：请检查 LLM_API_KEY 是否有效"),
    ("invalid_api_key", "模型服务认证失败：API Key 无效或已过期"),
    ("ratelimiterror", "请求过于频繁（限流），请稍后重试"),
    ("apitimeouterror", "模型服务响应超时，请稍后重试"),
    ("apiconnectionerror", "无法连接模型服务，请检查网络或 LLM_BASE_URL"),
    ("apierror", "模型服务返回错误，请稍后重试"),
)


def _safe_error_message(exc: Exception) -> str:
    text = f"{type(exc).__name__} {exc}".lower()
    for needle, message in SAFE_ERROR_MESSAGES:
        if needle in text:
            return message
    return "服务内部错误，请稍后重试"


class SafeChatHandler(ChatHandler):
    """ChatHandler that sanitizes errors before they reach the SSE stream.

    The framework's routes yield str(exc) into the stream; we replace it with
    a safe message and log the full details server-side.
    """

    async def handle_stream(
        self, request: ChatRequest
    ) -> AsyncGenerator[ChatStreamChunk, None]:
        try:
            async for chunk in super().handle_stream(request):
                yield chunk
        except Exception as exc:  # noqa: BLE001
            logger.error("chat stream error", exc_info=True)
            raise RuntimeError(_safe_error_message(exc)) from exc


def create_agent():
    """Build the PetCare Agent (LLM provider from config)."""
    config = load_config()

    runner = MySQLRunner(
        host=config.mysql_host,
        database=config.mysql_database,
        user=config.mysql_user,
        password=config.mysql_password,
        port=config.mysql_port,
    )
    tool = SafeRunSqlTool(sql_runner=runner)
    registry = ToolRegistry()
    registry.register(tool)

    prompt_builder = PetCareSystemPromptBuilder(as_of_date=config.as_of_date)
    llm_service = create_llm_service(config)

    # business decision: operators can see the generated SQL in the UI
    # (transparency / verifiability); empty group list = visible to everyone
    ui_features = UiFeatures(
        feature_group_access={
            UiFeature.UI_FEATURE_SHOW_TOOL_NAMES: [],
            UiFeature.UI_FEATURE_SHOW_TOOL_ARGUMENTS: [],
            UiFeature.UI_FEATURE_SHOW_TOOL_ERROR: [],
        }
    )

    return Agent(
        llm_service=llm_service,
        tool_registry=registry,
        system_prompt_builder=prompt_builder,
        config=AgentConfig(
            ui_features=ui_features,
            # protection boundary, NOT the fix: CTE data passing is fixed in
            # SafeRunSqlTool; cap iterations so pathological loops fail fast
            max_tool_iterations=4,
        ),
    )


def create_app() -> FastAPI:
    """Build the FastAPI application (used by tests and uvicorn)."""
    config = load_config()
    agent = create_agent()
    chat_handler = SafeChatHandler(agent)

    app = FastAPI(title=PAGE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        html = get_index_html(dev_mode=False, api_base_url="")
        return (
            html.replace("<title>Vanna Agents Chat</title>", f"<title>{PAGE_TITLE}</title>")
            .replace(H1_MARKUP, H1_MARKUP_PETCARE)
        )

    register_chat_routes(app, chat_handler)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {
            "status": "healthy",
            "service": "petcare",
            "provider": config.llm_provider,
            "model": config.llm_model or "",
        }

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled error on %s", request.url.path, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误，请稍后重试"},
        )

    return app


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()

"""PetCare AI Analytics Assistant - application entry.

Assembles the dependency graph:
    PetCareConfig -> MySQLRunner -> SafeRunSqlTool -> ToolRegistry
    PetCareSystemPromptBuilder + PetCareMockLlmService -> Agent
    Agent + ChatHandler -> FastAPI app (register_chat_routes)

Run:
    python -m petcare.main            # uvicorn on 0.0.0.0:8000
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from vanna import Agent
from vanna.core.registry import ToolRegistry
from vanna.integrations.mysql import MySQLRunner
from vanna.servers.base import ChatHandler
from vanna.servers.base.templates import get_index_html
from vanna.servers.fastapi.routes import register_chat_routes

from .config import load_config
from .mock_llm import PetCareMockLlmService
from .prompts import PetCareSystemPromptBuilder
from .safety import SafeRunSqlTool

PAGE_TITLE = "PetCare AI Analytics Assistant"
H1_MARKUP = (
    '<h1 class="text-4xl font-bold text-vanna-navy mb-2 font-serif">'
    "Vanna Agents</h1>"
)
H1_MARKUP_PETCARE = (
    '<h1 class="text-4xl font-bold text-vanna-navy mb-2 font-serif">'
    f"{PAGE_TITLE}</h1>"
)


def create_agent():
    """Build the PetCare Agent with mock LLM + safe read-only SQL tool."""
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
    llm_service = PetCareMockLlmService(as_of_date=config.as_of_date)

    return Agent(
        llm_service=llm_service,
        tool_registry=registry,
        system_prompt_builder=prompt_builder,
    )


def create_app() -> FastAPI:
    """Build the FastAPI application (used by tests and uvicorn)."""
    agent = create_agent()
    chat_handler = ChatHandler(agent)

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
        return {"status": "healthy", "service": "petcare"}

    return app


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()

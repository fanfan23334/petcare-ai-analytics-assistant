"""CTE (WITH ... SELECT) result-passing tests.

Verifies the fix in SafeRunSqlTool: WITH queries must produce a
DataFrameComponent with real data for the LLM and the frontend, instead of
being treated as DML ("N row(s) affected"). Also verifies the WITH-write
protection and that a model summarizing after a successful CTE result does
not re-invoke tools.
"""

import json

import pytest

from vanna.capabilities.sql_runner import RunSqlToolArgs
from vanna.components import DataFrameComponent
from vanna.core.tool import ToolContext
from vanna.core.user import User
from vanna.integrations.local.memory import InMemoryAgentMemory
from vanna.integrations.mysql import MySQLRunner

from petcare.config import load_config
from petcare.safety import SafeRunSqlTool, validate_read_only_sql

SELECT_SQL = "SELECT COUNT(*) AS cnt FROM owners"
WITH_SQL = "WITH t AS (SELECT COUNT(*) AS cnt FROM owners) SELECT cnt FROM t"


def _tool():
    config = load_config()
    runner = MySQLRunner(
        host=config.mysql_host,
        database=config.mysql_database,
        user=config.mysql_user,
        password=config.mysql_password,
        port=config.mysql_port,
    )
    return SafeRunSqlTool(sql_runner=runner)


def _context() -> ToolContext:
    return ToolContext(
        user=User(id="cte", username="cte"),
        conversation_id="cte",
        request_id="cte-1",
        agent_memory=InMemoryAgentMemory(),
    )


async def _run(sql: str):
    return await _tool().execute(_context(), RunSqlToolArgs(sql=sql))


@pytest.mark.asyncio
async def test_select_returns_dataframe():
    result = await _run(SELECT_SQL)
    assert result.success
    assert isinstance(result.ui_component.rich_component, DataFrameComponent)
    assert result.metadata["row_count"] == 1


@pytest.mark.asyncio
async def test_with_cte_returns_dataframe():
    """WITH ... SELECT must produce a dataframe, not a notification."""
    result = await _run(WITH_SQL)
    assert result.success
    assert isinstance(result.ui_component.rich_component, DataFrameComponent)
    assert result.metadata["row_count"] == 1


@pytest.mark.asyncio
async def test_with_result_for_llm_contains_real_data():
    result = await _run(WITH_SQL)
    assert "cnt" in result.result_for_llm
    assert "30" in result.result_for_llm  # owners count
    assert "Results saved to file" in result.result_for_llm


@pytest.mark.asyncio
async def test_with_not_rows_affected():
    result = await _run(WITH_SQL)
    assert "row(s) affected" not in result.result_for_llm
    assert "No rows returned" not in result.result_for_llm


@pytest.mark.parametrize(
    "sql",
    [
        "WITH cte AS (SELECT 1) DELETE FROM bills",
        "WITH cte AS (SELECT 1) UPDATE doctors SET salary = 0",
        "WITH cte AS (SELECT 1) INSERT INTO owners (name) VALUES ('x')",
        "WITH cte AS (SELECT 1) DROP TABLE pets",
    ],
)
def test_with_hidden_write_rejected(sql):
    ok, reason = validate_read_only_sql(sql)
    assert not ok, f"WITH-embedded write must be rejected: {sql}"
    assert reason


@pytest.mark.asyncio
async def test_model_summarizes_after_cte_success_without_extra_calls():
    """Complex question answered by ONE CTE call -> model summarizes, no retry."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from vanna import Agent
    from vanna.core.agent.config import AgentConfig, UiFeature, UiFeatures
    from vanna.core.llm import LlmResponse
    from vanna.core.registry import ToolRegistry
    from vanna.core.tool import ToolCall
    from vanna.servers.base import ChatHandler
    from vanna.servers.fastapi.routes import register_chat_routes

    from petcare.mock_llm import PetCareMockLlmService
    from petcare.prompts import PetCareSystemPromptBuilder

    class FakeCteLlm(PetCareMockLlmService):
        """Round 1 -> single WITH CTE query; round 2 -> summary (no tool)."""

        async def send_request(self, request):
            msgs = request.messages
            tool_msgs = [m for m in msgs if getattr(m, "role", None) == "tool"]
            if not tool_msgs:
                return LlmResponse(
                    content="查一下",
                    tool_calls=[
                        ToolCall(
                            id="c1",
                            name="run_sql",
                            arguments={
                                "sql": (
                                    "WITH t AS (SELECT species, COUNT(*) AS cnt "
                                    "FROM pets GROUP BY species) "
                                    "SELECT species, cnt FROM t WHERE species IN ('cat','dog')"
                                )
                            },
                        )
                    ],
                    finish_reason="tool_calls",
                )
            last = tool_msgs[-1].content or ""
            if "cat" in last and "dog" in last:
                return LlmResponse(content="查询完成：猫 20 只，狗 18 只。", finish_reason="stop")
            return LlmResponse(content="工具未返回数据", finish_reason="stop")

    config = load_config()
    registry = ToolRegistry()
    registry.register(_tool())
    agent = Agent(
        llm_service=FakeCteLlm(),
        tool_registry=registry,
        system_prompt_builder=PetCareSystemPromptBuilder(as_of_date=config.as_of_date),
        config=AgentConfig(
            ui_features=UiFeatures(
                feature_group_access={
                    UiFeature.UI_FEATURE_SHOW_TOOL_NAMES: [],
                    UiFeature.UI_FEATURE_SHOW_TOOL_ARGUMENTS: [],
                    UiFeature.UI_FEATURE_SHOW_TOOL_ERROR: [],
                }
            ),
            max_tool_iterations=4,
        ),
    )
    app = FastAPI()
    register_chat_routes(app, ChatHandler(agent))

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/vanna/v2/chat_sse",
            json={"message": "猫和狗各有多少只？", "conversation_id": "cte-e2e"},
        ) as resp:
            events = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    payload = line[6:]
                    events.append(None if payload == "[DONE]" else json.loads(payload))

    # exactly one tool call (status_card pair), dataframe present, summary produced
    types = [None if e is None else e["rich"]["type"] for e in events]
    cards = [t for t in types if t == "status_card"]
    assert len(cards) == 2, f"expected exactly one tool call, got {len(cards)//2}"
    assert "dataframe" in types
    texts = [
        e["rich"]["data"]["content"]
        for e in events
        if e is not None and e["rich"]["type"] == "text"
        and e["rich"]["data"].get("content")
    ]
    assert any("猫 20 只" in t for t in texts), f"summary missing data: {texts}"

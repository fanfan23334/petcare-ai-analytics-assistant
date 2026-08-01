"""Real DeepSeek integration tests.

Marked `integration`: run explicitly with:
    pytest -m integration -v
and requires LLM_API_KEY + LLM_PROVIDER=deepseek in the environment.
Skipped by default (no external API calls in normal pytest runs).

These tests exercise the real chain: Agent -> DeepSeek tool call ->
SafeRunSqlTool -> MySQLRunner -> petcare_db (read-only account).
"""

import asyncio
import os
from datetime import date

import pytest

def _has_deepseek_key() -> bool:
    """Read from config (env or .env), never from hardcoded values."""
    try:
        from petcare.config import load_config

        cfg = load_config()
        return cfg.llm_provider == "deepseek" and bool(cfg.llm_api_key)
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _has_deepseek_key(),
        reason="LLM_PROVIDER=deepseek + LLM_API_KEY not configured; integration tests skipped",
    ),
]

from vanna.core.llm import LlmMessage, LlmRequest
from vanna.core.user import User

from petcare.config import load_config
from petcare.llm_factory import create_llm_service

QUESTIONS = [
    ("最近三个月收入最高的医生是谁？", "张伟"),
    ("消费最高的客户是谁？", "冯浩建"),
    ("本月预约取消率是多少？", "31.9"),
    ("猫和狗各有多少只？", "猫"),
    ("哪位医生完成预约最多？", "46"),
    ("上个月手术收入占总收入的比例是多少？", None),
    ("哪个城市的客户实收消费最高？", None),
    ("哪位医生的收入与月薪比最高？", None),
    ("最近三个月各收费类型的收入分别是多少？", None),
    ("养多只宠物的客户是否比单宠物客户消费更高？", None),
]


async def _run_question(agent, question: str, cid: str):
    """Run through the agent, collecting components and the final summary."""
    from vanna.core.user.request_context import RequestContext

    components = []
    async for comp in agent.send_message(
        request_context=RequestContext(),
        message=question,
        conversation_id=cid,
    ):
        components.append(comp)
    return components


def _summary(components):
    """Extract final summary: RichTextComponent (DeepSeek) or SimpleTextComponent (mock)."""
    parts = []
    for comp in components:
        rich = getattr(comp, "rich_component", None)
        name = type(rich).__name__
        if name == "SimpleTextComponent" and getattr(rich, "text", ""):
            parts.append(rich.text)
        elif name == "RichTextComponent" and getattr(rich, "content", ""):
            parts.append(rich.content)
    return "".join(parts)


def _has_dataframe(components):
    return any(
        type(getattr(c, "rich_component", None)).__name__ == "DataFrameComponent"
        for c in components
    )


@pytest.mark.parametrize(
    "question,expect", QUESTIONS, ids=[q[:8] for q, _ in QUESTIONS]
)
def test_question_tool_call_roundtrip(question, expect):
    config = load_config()
    assert config.llm_provider == "deepseek", "integration requires LLM_PROVIDER=deepseek"

    from petcare.main import create_agent

    agent = create_agent()
    cid = f"int-{abs(hash(question)) % 10**8}"
    components = asyncio.run(_run_question(agent, question, cid))

    assert _has_dataframe(components), f"{question}: no dataframe streamed (tool call failed?)"
    summary = _summary(components)
    assert summary, f"{question}: no summary produced"
    if expect:
        assert expect in summary, f"{question}: summary mismatch: {summary}"


def test_llm_service_tool_call_direct():
    """Direct LLM service check: model must emit a run_sql tool call (usage sampled)."""
    config = load_config()
    service = create_llm_service(config)

    request = LlmRequest(
        messages=[LlmMessage(role="user", content="猫和狗各有多少只？")],
        tools=[
            {
                "name": "run_sql",
                "description": "Execute a read-only SQL query",
                "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}},
            }
        ],
        user=User(id="int", username="int"),
        system_prompt="你是宠物医院数据分析助手。",
    )

    resp = asyncio.run(service.send_request(request))
    assert resp.is_tool_call(), f"expected tool call, got content={resp.content!r}"
    assert resp.tool_calls[0].name == "run_sql"
    assert "sql" in resp.tool_calls[0].arguments
    print(f"USAGE_SAMPLE: {resp.usage}")

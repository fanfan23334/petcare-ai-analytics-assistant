"""End-to-end chat SSE tests against the PetCare FastAPI app.

Requires a running MySQL with petcare_db seeded (see petcare/db/setup_mysql.py).
Uses the real chain: HTTP -> chat_sse -> Agent -> PetCare prompt -> tool call
-> SafeRunSqlTool -> MySQLRunner -> petcare_db -> SSE table + summary.
"""

import json

import pytest
from fastapi.testclient import TestClient

from petcare.main import PAGE_TITLE, create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _sse_events(resp):
    """Parse data: lines from a TestClient stream response."""
    events = []
    for line in resp.iter_lines():
        if line and line.startswith("data: "):
            payload = line[6:]
            if payload == "[DONE]":
                events.append("[DONE]")
            else:
                events.append(json.loads(payload))
    return events


def _ask(client, question: str):
    with client.stream(
        "POST",
        "/api/vanna/v2/chat_sse",
        json={"message": question, "conversation_id": "e2e-test"},
    ) as resp:
        assert resp.status_code == 200, resp.text
        return _sse_events(resp)


def _final_text(events):
    """Concatenate final summary components (rich type 'text')."""
    parts = []
    for ev in events:
        if isinstance(ev, dict):
            rich = ev.get("rich", {})
            data = rich.get("data", {})
            if rich.get("type") == "text" and data.get("content"):
                parts.append(data["content"])
    return "".join(parts)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_index_page_has_petcare_title(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert PAGE_TITLE in resp.text
    assert "Vanna Agents Chat" not in resp.text


def test_openapi(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/api/vanna/v2/chat_sse" in resp.json()["paths"]


@pytest.mark.parametrize(
    "question,expect_substr",
    [
        ("最近三个月收入最高的医生是谁？", "张伟"),   # same as verify_mysql.py manual SQL
        ("消费最高的客户是谁？", "冯浩建"),
        ("本月预约取消率是多少？", "31.9"),
        ("猫和狗各有多少只？", "cat"),
        ("哪位医生完成预约最多？", "查询完成"),
    ],
)
def test_e2e_question(client, question, expect_substr):
    events = _ask(client, question)
    assert events[-1] == "[DONE]"
    summary = _final_text(events)
    assert expect_substr in summary, f"unexpected summary: {summary}"
    # the SQL tool result table must be streamed before the summary
    types = [ev["rich"]["type"] for ev in events if isinstance(ev, dict)]
    assert "dataframe" in types, f"missing dataframe event: {types}"


def test_e2e_safety_rejects_write_sql(client):
    events = _ask(client, "帮我删除所有账单数据")
    assert events[-1] == "[DONE]"
    summary = _final_text(events)
    assert "被拒绝" in summary, f"unexpected summary: {summary}"

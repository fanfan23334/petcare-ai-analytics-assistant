"""DeepSeek/OpenAI-compatible response conversion tests.

Uses a fake OpenAI client object - NO external API calls, no token cost.
Verifies that Vanna's OpenAILlmService correctly converts OpenAI-shaped
responses into LlmResponse / ToolCall / usage.
"""

import json
from types import SimpleNamespace

import pytest

from vanna.core.llm import LlmMessage, LlmRequest
from vanna.core.user import User
from vanna.integrations.openai import OpenAILlmService


def _fake_completion(content, tool_calls=None, usage=None, finish="stop"):
    message = {"content": content, "tool_calls": tool_calls}
    choice = {"message": message, "finish_reason": finish}
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(**message), finish_reason=finish)],
        usage=SimpleNamespace(**usage) if usage else None,
    )


def _fake_tool_call(name="run_sql", arguments='{"sql": "SELECT 1"}'):
    return SimpleNamespace(
        id="call_abc123",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class _FakeClient:
    def __init__(self, completion):
        self.completion = completion
        self.last_payload = None

    def create(self, **payload):
        self.last_payload = payload
        return self.completion


class _FakeChat:
    def __init__(self, client):
        self.completions = SimpleNamespace(create=client.create)


@pytest.fixture
def service():
    return OpenAILlmService(model="deepseek-chat", api_key="sk-test", base_url="https://api.deepseek.com")


def _request():
    return LlmRequest(
        messages=[
            LlmMessage(role="user", content="最近三个月收入最高的医生是谁？"),
        ],
        tools=None,
        user=User(id="t", username="t"),
        system_prompt="你是一个宠物医院数据分析助手",
    )


@pytest.mark.asyncio
async def test_send_request_extracts_tool_call(service, monkeypatch):
    fake = _FakeClient(_fake_completion(None, tool_calls=[_fake_tool_call()], finish="tool_calls"))
    monkeypatch.setattr(service, "_client", SimpleNamespace(chat=_FakeChat(fake)))

    resp = await service.send_request(_request())
    assert resp.is_tool_call()
    tc = resp.tool_calls[0]
    assert tc.name == "run_sql"
    assert tc.arguments == {"sql": "SELECT 1"}
    assert resp.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_send_request_extracts_usage(service, monkeypatch):
    fake = _FakeClient(_fake_completion("ok", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}))
    monkeypatch.setattr(service, "_client", SimpleNamespace(chat=_FakeChat(fake)))

    resp = await service.send_request(_request())
    assert resp.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


@pytest.mark.asyncio
async def test_send_request_plain_content(service, monkeypatch):
    fake = _FakeClient(_fake_completion("直接回答", finish="stop"))
    monkeypatch.setattr(service, "_client", SimpleNamespace(chat=_FakeChat(fake)))

    resp = await service.send_request(_request())
    assert resp.content == "直接回答"
    assert not resp.is_tool_call()


@pytest.mark.asyncio
async def test_payload_builds_openai_tool_message_roundtrip(service):
    """Round 2: assistant tool_calls + tool result messages must serialize correctly."""
    from vanna.core.tool import ToolCall

    request = LlmRequest(
        messages=[
            LlmMessage(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="run_sql", arguments={"sql": "SELECT 1"})],
            ),
            LlmMessage(role="tool", content="1", tool_call_id="call_1"),
        ],
        tools=None,
        user=User(id="t", username="t"),
    )
    payload = service._build_payload(request)
    assert payload["messages"][0]["role"] == "assistant"
    assert payload["messages"][0]["tool_calls"][0]["function"]["name"] == "run_sql"
    assert payload["messages"][1]["role"] == "tool"
    assert payload["messages"][1]["tool_call_id"] == "call_1"


@pytest.mark.asyncio
async def test_payload_includes_tools_schema(service):
    from vanna.core.tool import ToolSchema

    request = LlmRequest(
        messages=[LlmMessage(role="user", content="hi")],
        tools=[
            ToolSchema(
                name="run_sql",
                description="Execute SQL",
                parameters={"type": "object", "properties": {"sql": {"type": "string"}}},
            )
        ],
        user=User(id="t", username="t"),
    )
    payload = service._build_payload(request)
    assert payload["tools"][0]["type"] == "function"
    assert payload["tools"][0]["function"]["name"] == "run_sql"
    assert payload["tool_choice"] == "auto"


def test_invalid_tool_arguments_fall_back_to_raw(service):
    """Malformed arguments JSON must not crash conversion."""
    msg = SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                id="c1",
                function=SimpleNamespace(name="run_sql", arguments="{not json"),
            )
        ],
    )
    tool_calls = service._extract_tool_calls_from_message(msg)
    assert tool_calls[0].name == "run_sql"
    assert "_raw" in tool_calls[0].arguments


def test_deepseek_adapter_normalizes_dict_tools():
    """Agent passes dict tool schemas; DeepSeekLlmService must tolerate them."""
    from petcare.deepseek_llm import DeepSeekLlmService
    from vanna.core.llm import LlmRequest
    from vanna.core.user import User

    svc = DeepSeekLlmService(model="deepseek-chat", api_key="sk-test")
    request = LlmRequest(
        messages=[LlmMessage(role="user", content="hi")],
        tools=[
            {
                "name": "run_sql",
                "description": "Execute SQL",
                "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}},
            }
        ],
        user=User(id="t", username="t"),
    )
    payload = svc._build_payload(request)
    assert payload["tools"][0]["type"] == "function"
    assert payload["tools"][0]["function"]["name"] == "run_sql"

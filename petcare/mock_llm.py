"""PetCare deterministic Mock LLM for end-to-end testing.

Emits REAL run_sql tool calls (never bypasses the Agent/tool chain) for a
fixed set of pet-hospital questions, then summarizes the tool result in a
second round. Deterministic: same question -> same SQL -> same summary.

Supported questions:
1. 最近三个月收入最高的医生是谁？
2. 消费最高的客户是谁？
3. 本月预约取消率是多少？
4. 猫和狗各有多少只？
5. 哪位医生完成预约最多？
6. (safety demo) 删除类问题 -> emits DELETE SQL, rejected by SafeRunSqlTool
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import date
from typing import Any, AsyncGenerator, List, Optional

from vanna.core.llm import LlmRequest, LlmResponse, LlmStreamChunk, LlmService
from vanna.core.tool import ToolCall, ToolSchema

from .prompts import time_windows


def _summarize_table(text: str, max_rows: int = 3) -> str:
    """Extract the first data rows of a table dump, skipping noise lines."""
    noise_prefixes = ("results saved", "**important", "---")
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    data_lines = [
        ln for ln in lines[1:] if not ln.lower().startswith(noise_prefixes)
    ] if len(lines) >= 2 else lines
    return "；".join(data_lines[:max_rows]) if data_lines else "(empty)"


class PetCareMockLlmService(LlmService):
    """Deterministic question->SQL->summary mock for PetCare e2e tests."""

    def __init__(self, as_of_date: date | None = None):
        self.as_of_date = as_of_date or date(2026, 4, 30)
        windows = time_windows(self.as_of_date)
        self._recent = windows["recent_3_months"]
        self._this_month = windows["this_month"]
        self.call_count = 0

        # question patterns -> SQL (all read-only, MySQL 8.0)
        self._question_sqls: List[tuple[str, str]] = [
            (
                "delete",
                "DELETE FROM bills WHERE billed_date >= '2026-04-01'",
            ),
            (
                "income",
                (
                    f"SELECT d.name AS doctor, d.specialty, "
                    f"ROUND(SUM(b.amount), 2) AS revenue "
                    f"FROM bills b JOIN doctors d ON b.doctor_id = d.doctor_id "
                    f"WHERE b.pay_status = 'paid' "
                    f"AND b.billed_date BETWEEN '{self._recent[0]}' AND '{self._recent[1]}' "
                    f"GROUP BY d.doctor_id ORDER BY revenue DESC LIMIT 1"
                ),
            ),
            (
                "spend",
                (
                    "SELECT o.name AS owner, o.city, "
                    "ROUND(SUM(b.amount), 2) AS total_spend "
                    "FROM bills b JOIN pets p ON b.pet_id = p.pet_id "
                    "JOIN owners o ON p.owner_id = o.owner_id "
                    "WHERE b.pay_status = 'paid' "
                    "GROUP BY o.owner_id ORDER BY total_spend DESC LIMIT 1"
                ),
            ),
            (
                "cancel",
                (
                    f"SELECT COUNT(*) AS total, "
                    f"SUM(status = 'cancelled') AS cancelled, "
                    f"ROUND(100 * SUM(status = 'cancelled') / NULLIF(COUNT(*), 0), 1) AS cancel_rate "
                    f"FROM appointments "
                    f"WHERE appointment_date BETWEEN '{self._this_month[0]}' AND '{self._this_month[1]}'"
                ),
            ),
            (
                "species",
                (
                    "SELECT species, COUNT(*) AS cnt "
                    "FROM pets GROUP BY species ORDER BY cnt DESC"
                ),
            ),
            (
                "workload",
                (
                    "SELECT d.name AS doctor, d.specialty, "
                    "COUNT(a.appointment_id) AS completed_cnt "
                    "FROM appointments a JOIN doctors d ON a.doctor_id = d.doctor_id "
                    "WHERE a.status = 'completed' "
                    "GROUP BY d.doctor_id ORDER BY completed_cnt DESC LIMIT 1"
                ),
            ),
        ]

    # ------------------------------------------------------------- detection
    def detect(self, question: str) -> Optional[tuple[str, str]]:
        """Return (key, sql) for a supported question, else None."""
        q = question.lower()
        if "删除" in q or "delete" in q:
            key = "delete"
        elif "收入最高" in q and "医生" in q:
            key = "income"
        elif "消费最高" in q:
            key = "spend"
        elif "取消率" in q:
            key = "cancel"
        elif "猫" in q and "狗" in q:
            key = "species"
        elif "完成预约最多" in q or ("预约最多" in q and "医生" in q):
            key = "workload"
        else:
            return None
        for pattern, sql in self._question_sqls:
            if pattern == key:
                return key, sql
        return None

    # -------------------------------------------------------------- round 1
    def _first_round(self, question: str) -> LlmResponse:
        detected = self.detect(question)
        if detected is None:
            return LlmResponse(
                content="暂不支持该问题，请换一种问法（例如：最近三个月收入最高的医生是谁？）。",
                finish_reason="stop",
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            )
        key, sql = detected
        return LlmResponse(
            content=f"好的，我来查询{'删除' if key == 'delete' else '分析'}数据…",
            tool_calls=[
                ToolCall(
                    id=f"call_{uuid.uuid4().hex[:8]}",
                    name="run_sql",
                    arguments={"sql": sql},
                )
            ],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
        )

    # -------------------------------------------------------------- round 2
    def _second_round(self, tool_msg: Any) -> LlmResponse:
        raw = tool_msg.content or ""
        if "被安全层拒绝" in raw or "rejected" in raw.lower():
            summary = f"查询被拒绝：{raw.strip()}"
        else:
            row = _summarize_table(raw)
            summary = f"查询完成，结果为：{row}。如需进一步分析，可以继续提问。"
        return LlmResponse(
            content=summary,
            finish_reason="stop",
            usage={"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60},
        )

    # ------------------------------------------------------------- LlmService
    def _latest_user_message(self, messages: List[Any]) -> Optional[Any]:
        for m in reversed(messages):
            if getattr(m, "role", None) == "user":
                return m
        return None

    def _latest_tool_message(self, messages: List[Any]) -> Optional[Any]:
        for m in reversed(messages):
            if getattr(m, "role", None) == "tool":
                return m
        return None

    async def send_request(self, request: LlmRequest) -> LlmResponse:
        self.call_count += 1
        user_msg = self._latest_user_message(request.messages)
        tool_msg = self._latest_tool_message(request.messages)
        # summary round: a tool message exists after the latest user question
        if tool_msg is not None and user_msg is not None:
            messages = request.messages
            user_idx = max(
                i for i, m in enumerate(messages) if getattr(m, "role", None) == "user"
            )
            tool_after_user = any(
                getattr(m, "role", None) == "tool" for m in messages[user_idx + 1 :]
            )
            if tool_after_user:
                return self._second_round(tool_msg)
        return self._first_round((user_msg.content if user_msg else "") or "")

    async def stream_request(
        self, request: LlmRequest
    ) -> AsyncGenerator[LlmStreamChunk, None]:
        response = await self.send_request(request)
        if response.tool_calls:
            yield LlmStreamChunk(
                content=response.content,
                tool_calls=response.tool_calls,
                finish_reason="tool_calls",
            )
            return
        words = (response.content or "").split()
        for i, word in enumerate(words):
            await asyncio.sleep(0.01)
            yield LlmStreamChunk(
                content=word + (" " if i < len(words) - 1 else ""),
                finish_reason="stop" if i == len(words) - 1 else None,
            )

    async def validate_tools(self, tools: List[ToolSchema]) -> List[str]:
        return []

"""PetCare read-only SQL safety layer.

Low-intrusion wrapper around Vanna's RunSqlTool: validates SQL before
execution and rejects anything that is not a single read-only query.
Vanna core is NOT modified.
"""

from __future__ import annotations

import re
from typing import Any, Type

from vanna.core.tool import ToolContext, ToolResult
from vanna.tools import RunSqlTool
from vanna.capabilities.sql_runner import RunSqlToolArgs

# Dangerous keywords: any occurrence (word boundary) rejects the query
FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "replace",
    "grant",
    "revoke",
    "call",
    "execute",
    "commit",
    "rollback",
    "lock",
    "rename",
    "load",
    "kill",
)

ALLOWED_STARTS = ("SELECT", "WITH")

_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)


def validate_read_only_sql(sql: str) -> tuple[bool, str]:
    """Validate that sql is a single read-only query.

    Returns (True, "") if safe, or (False, reason) with a clear message.
    """
    if not sql or not sql.strip():
        return False, "SQL 为空，拒绝执行"

    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        return False, "禁止多语句执行：SQL 中包含分号"

    head = cleaned.split(None, 1)[0].upper() if cleaned.split(None, 1) else ""
    if head not in ALLOWED_STARTS:
        return False, f"只允许只读查询（以 SELECT 或 WITH 开头），当前以 '{head or '(空)'}' 开头"

    match = _FORBIDDEN_RE.search(cleaned)
    if match:
        return False, f"禁止写操作关键字 {match.group(1).upper()}：只允许只读查询"

    return True, ""


class SafeRunSqlTool(RunSqlTool):
    """RunSqlTool with read-only enforcement at the PetCare layer."""

    async def execute(self, context: ToolContext, args: RunSqlToolArgs) -> ToolResult:
        ok, reason = validate_read_only_sql(args.sql)
        if not ok:
            return ToolResult(
                success=False,
                result_for_llm=f"SQL 被安全层拒绝：{reason}",
                error=f"SQL rejected by safety layer: {reason}",
                metadata={"rejected": True, "reason": reason},
            )
        return await super().execute(context, args)

    def get_args_schema(self) -> Type[RunSqlToolArgs]:
        return RunSqlToolArgs

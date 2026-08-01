"""PetCare read-only SQL safety layer.

Low-intrusion wrapper around Vanna's RunSqlTool: validates SQL before
execution and rejects anything that is not a single read-only query.
Vanna core is NOT modified.

IMPORTANT: this string-based check is only the FIRST defense layer.
The final permission boundary is the MySQL read-only account
(petcare_reader) - see petcare/db/create_readonly_user.sql and
docs/database-security.md.
"""

from __future__ import annotations

import re
from typing import Any, Type

from vanna.core.tool import ToolContext, ToolResult
from vanna.tools import RunSqlTool
from vanna.capabilities.sql_runner import RunSqlToolArgs

MAX_SQL_LENGTH = 2000

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

# extra patterns: statement-level threats, system schemas, comment bypass
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)

_EXTRA_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("INTO OUTFILE 文件导出", re.compile(r"\binto\s+outfile\b", re.IGNORECASE)),
    ("INTO DUMPFILE 文件导出", re.compile(r"\binto\s+dumpfile\b", re.IGNORECASE)),
    ("LOAD_FILE 读取服务器文件", re.compile(r"\bload_file\s*\(", re.IGNORECASE)),
    ("SLEEP 延时函数", re.compile(r"\bsleep\s*\(", re.IGNORECASE)),
    ("BENCHMARK 耗时函数", re.compile(r"\bbenchmark\s*\(", re.IGNORECASE)),
    ("FOR UPDATE 行锁", re.compile(r"\bfor\s+update\b", re.IGNORECASE)),
    ("LOCK IN SHARE MODE 共享锁", re.compile(r"\block\s+in\s+share\s+mode\b", re.IGNORECASE)),
    ("information_schema 系统库", re.compile(r"\binformation_schema\b", re.IGNORECASE)),
    ("performance_schema 系统库", re.compile(r"\bperformance_schema\b", re.IGNORECASE)),
    ("mysql 系统库", re.compile(r"\bmysql\s*\.\s*\w+", re.IGNORECASE)),
    ("sys 系统库", re.compile(r"\bsys\s*\.\s*\w+", re.IGNORECASE)),
    ("SQL 注释（--）", re.compile(r"--")),
    ("SQL 注释（#）", re.compile(r"#")),
    ("SQL 注释（/* */）", re.compile(r"/\*")),
)


def validate_read_only_sql(sql: str) -> tuple[bool, str]:
    """Validate that sql is a single read-only query.

    Returns (True, "") if safe, or (False, reason) with a clear message.
    """
    if not sql or not sql.strip():
        return False, "SQL 为空，拒绝执行"

    if len(sql) > MAX_SQL_LENGTH:
        return False, f"SQL 过长（超过 {MAX_SQL_LENGTH} 字符），拒绝执行"

    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        return False, "禁止多语句执行：SQL 中包含分号"

    head = cleaned.split(None, 1)[0].upper() if cleaned.split(None, 1) else ""
    if head not in ALLOWED_STARTS:
        return False, f"只允许只读查询（以 SELECT 或 WITH 开头），当前以 '{head or '(空)'}' 开头"

    match = _FORBIDDEN_RE.search(cleaned)
    if match:
        return False, f"禁止写操作关键字 {match.group(1).upper()}：只允许只读查询"

    for label, pattern in _EXTRA_PATTERNS:
        if pattern.search(cleaned):
            return False, f"检测到危险内容：{label}，拒绝执行"

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

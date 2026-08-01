"""PetCare read-only SQL safety layer + WITH-CTE result handling.

Low-intrusion wrapper around Vanna's RunSqlTool:
1. validates SQL before execution (read-only enforcement, first defense layer)
2. FIXES a Vanna core defect: core RunSqlTool only treats `SELECT` as a result
   query (`sql.split()[0] == "SELECT"`); `WITH ... SELECT` CTE queries fall
   into the "DML" branch and return only "N row(s) affected" - the LLM never
   receives the actual data. Here both SELECT and WITH queries produce a
   DataFrameComponent + full data in result_for_llm.

Vanna core is NOT modified.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Type, cast

from vanna.capabilities.sql_runner import RunSqlToolArgs
from vanna.components import (
    ComponentType,
    DataFrameComponent,
    NotificationComponent,
    SimpleTextComponent,
    UiComponent,
)
from vanna.core.tool import ToolContext, ToolResult
from vanna.tools import RunSqlTool

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
    The MySQL read-only account (petcare_reader) is the final permission
    boundary - this is only the first application-layer defense.
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
    """RunSqlTool with read-only enforcement + WITH-CTE result handling."""

    async def execute(self, context: ToolContext, args: RunSqlToolArgs) -> ToolResult:
        ok, reason = validate_read_only_sql(args.sql)
        if not ok:
            return ToolResult(
                success=False,
                result_for_llm=f"SQL 被安全层拒绝：{reason}",
                error=f"SQL rejected by safety layer: {reason}",
                metadata={"rejected": True, "reason": reason},
            )
        # safety guarantees the query is SELECT / WITH read-only, so always
        # route through the result-set path (fixes core WITH-as-DML defect)
        return await self._execute_result_query(context, args)

    async def _execute_result_query(
        self, context: ToolContext, args: RunSqlToolArgs
    ) -> ToolResult:
        """Result-set handling for SELECT and WITH ... SELECT queries.

        Mirrors Vanna core's SELECT branch but accepts both SELECT and WITH
        as result-producing queries. WITH CTEs must not be treated as DML.
        """
        try:
            df = await self.sql_runner.run_sql(args, context)
            query_type = args.sql.strip().upper().split()[0]  # SELECT or WITH

            if df.empty:
                result = "Query executed successfully. No rows returned."
                ui_component = UiComponent(
                    rich_component=DataFrameComponent(
                        rows=[],
                        columns=[],
                        title="Query Results",
                        description="No rows returned",
                    ),
                    simple_component=SimpleTextComponent(text=result),
                )
                metadata: Dict[str, Any] = {
                    "row_count": 0,
                    "columns": [],
                    "query_type": query_type,
                    "results": [],
                }
            else:
                results_data = df.to_dict("records")
                columns = df.columns.tolist()
                row_count = len(df)

                file_id = str(uuid.uuid4())[:8]
                filename = f"query_results_{file_id}.csv"
                csv_content = df.to_csv(index=False)
                await self.file_system.write_file(
                    filename, csv_content, context, overwrite=True
                )

                results_preview = csv_content
                if len(results_preview) > 1000:
                    results_preview = (
                        results_preview[:1000]
                        + "\n(Results truncated to 1000 characters. FOR LARGE RESULTS YOU DO NOT NEED TO SUMMARIZE THESE RESULTS OR PROVIDE OBSERVATIONS. THE NEXT STEP SHOULD BE A VISUALIZE_DATA CALL)"
                    )

                result = (
                    f"{results_preview}\n\nResults saved to file: {filename}\n\n"
                    f"**IMPORTANT: FOR VISUALIZE_DATA USE FILENAME: {filename}**"
                )

                dataframe_component = DataFrameComponent.from_records(
                    records=cast(List[Dict[str, Any]], results_data),
                    title="Query Results",
                    description=f"SQL query returned {row_count} rows with {len(columns)} columns",
                )
                ui_component = UiComponent(
                    rich_component=dataframe_component,
                    simple_component=SimpleTextComponent(text=result),
                )
                metadata = {
                    "row_count": row_count,
                    "columns": columns,
                    "query_type": query_type,
                    "results": results_data,
                    "output_file": filename,
                }

            return ToolResult(
                success=True,
                result_for_llm=result,
                ui_component=ui_component,
                metadata=metadata,
            )
        except Exception as exc:  # noqa: BLE001
            error_message = f"Error executing query: {str(exc)}"
            return ToolResult(
                success=False,
                result_for_llm=error_message,
                ui_component=UiComponent(
                    rich_component=NotificationComponent(
                        type=ComponentType.NOTIFICATION,
                        level="error",
                        message=error_message,
                    ),
                    simple_component=SimpleTextComponent(text=error_message),
                ),
                error=str(exc),
                metadata={"error_type": "sql_error"},
            )

    def get_args_schema(self) -> Type[RunSqlToolArgs]:
        return RunSqlToolArgs

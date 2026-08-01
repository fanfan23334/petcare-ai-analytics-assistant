"""Read-only SQL safety layer tests."""

import pytest

from vanna.capabilities.sql_runner import RunSqlToolArgs
from vanna.core.tool import ToolContext
from vanna.core.user import User
from vanna.integrations.local.memory import InMemoryAgentMemory
from vanna.integrations.sqlite import SqliteRunner

from petcare.safety import SafeRunSqlTool, validate_read_only_sql

ALLOWED = [
    ("simple select", "SELECT COUNT(*) FROM owners"),
    ("select lower case", "select name from doctors"),
    ("with cte", "WITH t AS (SELECT 1 AS x) SELECT * FROM t"),
    ("select with strings", "SELECT name FROM pets WHERE species = 'cat'"),
    ("trailing semicolon", "SELECT 1;"),
    ("parenthesized", "SELECT (SELECT COUNT(*) FROM bills) AS total"),
]

REJECTED = [
    ("delete", "DELETE FROM bills"),
    ("insert", "INSERT INTO owners (name) VALUES ('x')"),
    ("update", "UPDATE doctors SET salary = 0"),
    ("drop", "DROP TABLE pets"),
    ("alter", "ALTER TABLE owners ADD COLUMN x INT"),
    ("truncate", "TRUNCATE TABLE bills"),
    ("create", "CREATE TABLE hack (id INT)"),
    ("replace", "REPLACE INTO owners (name) VALUES ('x')"),
    ("multi statement", "SELECT 1; DELETE FROM bills"),
    ("not select start", "EXPLAIN SELECT * FROM owners"),
    ("empty", "   "),
    ("into outfile", "SELECT * FROM bills INTO OUTFILE '/tmp/x.csv'"),
    ("into dumpfile", "SELECT * FROM bills INTO DUMPFILE '/tmp/x.bin'"),
    ("load_file", "SELECT LOAD_FILE('/etc/passwd')"),
    ("sleep", "SELECT SLEEP(10)"),
    ("benchmark", "SELECT BENCHMARK(1000000, MD5('x'))"),
    ("for update", "SELECT * FROM bills FOR UPDATE"),
    ("lock in share mode", "SELECT * FROM bills LOCK IN SHARE MODE"),
    ("information_schema", "SELECT * FROM information_schema.tables"),
    ("performance_schema", "SELECT * FROM performance_schema.events"),
    ("mysql system db", "SELECT * FROM mysql.user"),
    ("sys system db", "SELECT * FROM sys.schema_tables"),
    ("comment dash", "SELECT 1 -- comment"),
    ("comment hash", "SELECT 1 # comment"),
    ("comment block", "SELECT 1 /* comment */"),
    ("too long", "SELECT " + "1, " * 2500),
    ("substring delete trick", "SELECT * FROM owners WHERE name LIKE 'x' AND (SELECT 1) IS NOT NULL; DELETE FROM bills"),
]


@pytest.mark.parametrize("name,sql", ALLOWED)
def test_allowed(name, sql):
    ok, reason = validate_read_only_sql(sql)
    assert ok, f"{name} should pass: {reason}"


@pytest.mark.parametrize("name,sql", REJECTED)
def test_rejected(name, sql):
    ok, reason = validate_read_only_sql(sql)
    assert not ok, f"{name} should be rejected"
    assert reason, "rejection must carry a clear message"


def _context() -> ToolContext:
    return ToolContext(
        user=User(id="test", username="test"),
        conversation_id="test",
        request_id="test-1",
        agent_memory=InMemoryAgentMemory(),
    )


async def _run_tool(sql: str):
    tool = SafeRunSqlTool(sql_runner=SqliteRunner(":memory:"))
    return await tool.execute(_context(), RunSqlToolArgs(sql=sql))


@pytest.mark.asyncio
async def test_tool_rejects_delete():
    result = await _run_tool("DELETE FROM bills")
    assert result.success is False
    assert result.error and "只读" in result.error
    assert "安全层拒绝" in (result.result_for_llm or "")


@pytest.mark.asyncio
async def test_tool_rejects_multi_statement():
    result = await _run_tool("SELECT 1; DROP TABLE bills")
    assert result.success is False


@pytest.mark.asyncio
async def test_tool_allows_select():
    result = await _run_tool("SELECT 1 AS x")
    assert result.success is True

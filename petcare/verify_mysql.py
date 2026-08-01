"""Verify the PetCare MySQL connection through Vanna's MySQLRunner chain.

Exercises the full Vanna tool chain (not raw pymysql business queries):
    RunSqlTool -> MySQLRunner -> MySQL -> DataFrame -> ToolResult

Usage:
    python petcare/verify_mysql.py [--report reports/petcare-mysql-verification.md]
"""

import argparse
import asyncio
from datetime import date, timedelta
from pathlib import Path
from typing import List, Tuple

from vanna.core.tool import ToolContext
from vanna.core.user import User
from vanna.integrations.local.memory import InMemoryAgentMemory
from vanna.integrations.mysql import MySQLRunner
from vanna.tools import RunSqlTool
from vanna.capabilities.sql_runner import RunSqlToolArgs

from petcare.config import load_config


def add_months(d: date, months: int) -> date:
    month_index = d.year * 12 + (d.month - 1) + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    if month == 2:
        last = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
    elif month in (4, 6, 9, 11):
        last = 30
    else:
        last = 31
    return date(year, month, min(d.day, last))


def build_cases(base_date: date) -> List[Tuple[str, str]]:
    """(case_name, sql) — all time windows derived from BASE_DATE."""
    recent_start = add_months(base_date, -6).isoformat()      # 2026-02-01
    recent_end = (add_months(base_date, -3) - timedelta(days=1)).isoformat()  # 2026-04-30
    month_start = add_months(base_date, -4).isoformat()       # 2026-04-01
    month_end = (add_months(base_date, -3) - timedelta(days=1)).isoformat()

    return [
        ("owners 总数", "SELECT COUNT(*) AS cnt FROM owners"),
        ("bills 总数", "SELECT COUNT(*) AS cnt FROM bills"),
        (
            f"最近三个月({recent_start}~{recent_end})收入最高医生",
            f"""SELECT d.name AS doctor, d.specialty, ROUND(SUM(b.amount), 2) AS revenue
                FROM bills b JOIN doctors d ON b.doctor_id = d.doctor_id
                WHERE b.pay_status = 'paid'
                  AND b.billed_date BETWEEN '{recent_start}' AND '{recent_end}'
                GROUP BY d.doctor_id
                ORDER BY revenue DESC
                LIMIT 1""",
        ),
        (
            "消费最高客户",
            """SELECT o.name AS owner, o.city, ROUND(SUM(b.amount), 2) AS total_spend
                FROM bills b
                JOIN pets p ON b.pet_id = p.pet_id
                JOIN owners o ON p.owner_id = o.owner_id
                WHERE b.pay_status = 'paid'
                GROUP BY o.owner_id
                ORDER BY total_spend DESC
                LIMIT 1""",
        ),
        (
            f"本月({month_start}~{month_end})预约取消率",
            f"""SELECT COUNT(*) AS total,
                        SUM(status = 'cancelled') AS cancelled,
                        ROUND(100 * SUM(status = 'cancelled') / COUNT(*), 1) AS cancel_rate
                FROM appointments
                WHERE appointment_date BETWEEN '{month_start}' AND '{month_end}'""",
        ),
    ]


def first_data_line(out: str, max_len: int = 120) -> str:
    """Return the first non-empty data row (after the header) of a table dump."""
    lines = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
    if len(lines) >= 2:
        return lines[1][:max_len]
    return lines[0][:max_len] if lines else "(empty)"


async def run_case(tool: RunSqlTool, context: ToolContext, sql: str) -> Tuple[bool, str]:
    result = await tool.execute(context, RunSqlToolArgs(sql=sql))
    if result.success:
        return True, result.result_for_llm
    return False, result.error or "unknown error"


async def main() -> int:
    parser = argparse.ArgumentParser(description="PetCare MySQLRunner verification")
    parser.add_argument(
        "--report",
        default="reports/petcare-mysql-verification.md",
        help="output markdown report path",
    )
    args = parser.parse_args()

    config = load_config()

    # config summary (password masked)
    print("== 配置加载 ==")
    print(f"  MYSQL_HOST={config.mysql_host}  MYSQL_PORT={config.mysql_port}")
    print(f"  MYSQL_USER={config.mysql_user}  MYSQL_DATABASE={config.mysql_database}")
    print(f"  MYSQL_PASSWORD={'*' * len(config.mysql_password)}")
    print(f"  LLM_PROVIDER={config.llm_provider}  LLM_MODEL={config.llm_model or '-'}")
    print(f"  PETCARE_BASE_DATE={config.base_date}")

    # Vanna chain: RunSqlTool -> MySQLRunner
    runner = MySQLRunner(
        host=config.mysql_host,
        database=config.mysql_database,
        user=config.mysql_user,
        password=config.mysql_password,
        port=config.mysql_port,
    )
    tool = RunSqlTool(sql_runner=runner)
    context = ToolContext(
        user=User(id="verify", username="verify"),
        conversation_id="verify",
        request_id="verify-0001",
        agent_memory=InMemoryAgentMemory(),
    )

    # connection smoke: simple query
    try:
        ok, out = await run_case(tool, context, "SELECT 1 AS ping")
        connected = ok
        print(f"== 数据库连接 ==")
        print(f"  ping SELECT 1: {'PASS' if ok else 'FAIL'} ({out.strip()[:40]})")
    except Exception as exc:  # noqa: BLE001
        connected = False
        print(f"== 数据库连接 ==")
        print(f"  ping SELECT 1: FAIL ({exc})")

    cases = build_cases(config.base_date)
    results = []
    print("== 业务验证 ==")
    for name, sql in cases:
        try:
            ok, out = await run_case(tool, context, sql)
        except Exception as exc:  # noqa: BLE001
            ok, out = False, str(exc)
        results.append((name, sql, ok, out))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if ok:
            print(f"        -> {first_data_line(out)}")
        else:
            print(f"        -> {out[:200]}")

    # ---- write report ----
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PetCare MySQLRunner 验证报告",
        "",
        f"- 日期：{date.today().isoformat()}",
        f"- 链路：`RunSqlTool -> MySQLRunner -> MySQL 8.0`（未直接使用 pymysql 执行业务查询）",
        f"- BASE_DATE：`{config.base_date}`（数据窗口至 {add_months(config.base_date, -3) - timedelta(days=1)}）",
        "",
        "## 配置加载（密码已隐藏）",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| MYSQL_HOST | `{config.mysql_host}` |",
        f"| MYSQL_PORT | `{config.mysql_port}` |",
        f"| MYSQL_USER | `{config.mysql_user}` |",
        f"| MYSQL_PASSWORD | `{'*' * len(config.mysql_password)}` |",
        f"| MYSQL_DATABASE | `{config.mysql_database}` |",
        f"| LLM_PROVIDER | `{config.llm_provider}` |",
        f"| PETCARE_BASE_DATE | `{config.base_date}` |",
        "",
        "## 数据库连接",
        "",
        f"- ping `SELECT 1`: **{'PASS' if connected else 'FAIL'}**",
        "",
        "## 测试用例",
        "",
        "| # | 用例 | SQL | 结果 | 状态 |",
        "|---|---|---|---|---|",
    ]
    for i, (name, sql, ok, out) in enumerate(results, 1):
        out_one = first_data_line(out)
        lines.append(
            f"| {i} | {name} | `{' '.join(sql.split())}` | {out_one} | **{'PASS' if ok else 'FAIL'}** |"
        )
    failed = [r for r in results if not r[0]]
    lines += [
        "",
        f"## 结论",
        "",
        f"- 用例通过：{len(results) - len(failed)}/{len(results)}",
        f"- 整体：**{'PASS' if connected and not failed else 'FAIL'}**",
        "",
        "## 遇到的问题及修复",
        "",
        "- 无（若后续失败见下方记录）",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"== 报告已生成：{report}")
    return 0 if connected and not failed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

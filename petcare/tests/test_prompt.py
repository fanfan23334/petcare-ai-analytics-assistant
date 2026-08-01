"""PetCare system prompt builder tests."""

from datetime import date

import pytest

from petcare.prompts import (
    DEFAULT_AS_OF_DATE,
    PetCareSystemPromptBuilder,
    time_windows,
)

AS_OF = date(2026, 4, 30)


def test_time_windows_relative_to_as_of_date():
    w = time_windows(AS_OF)
    assert w["this_month"] == ("2026-04-01", "2026-04-30")
    assert w["last_month"] == ("2026-03-01", "2026-03-31")
    assert w["recent_3_months"] == ("2026-02-01", "2026-04-30")


async def _build() -> str:
    builder = PetCareSystemPromptBuilder(as_of_date=AS_OF)
    return await builder.build_system_prompt(user=None, tools=[])


@pytest.mark.asyncio
async def test_prompt_contains_identity_and_tables():
    prompt = await _build()
    assert "宠物医院业务数据分析助手" in prompt
    assert "医院管理者和运营人员" in prompt
    for table in ("owners", "pets", "doctors", "appointments", "medical_records", "bills"):
        assert table in prompt


@pytest.mark.asyncio
async def test_prompt_contains_business_semantics():
    prompt = await _build()
    assert "pay_status='paid'" in prompt or "pay_status = 'paid'" in prompt
    assert "refunded 不计入收入" in prompt
    assert "cat=猫" in prompt and "dog=狗" in prompt
    assert "booked=已预约" in prompt and "cancelled=已取消" in prompt and "no_show=爽约" in prompt
    assert "consultation=诊查费" in prompt and "surgery=手术费" in prompt


@pytest.mark.asyncio
async def test_prompt_time_semantics_use_as_of_date_not_system_date():
    prompt = await _build()
    assert "AS_OF_DATE = 2026-04-30" in prompt
    assert "2026-02-01" in prompt  # recent 3 months start
    assert "禁止使用服务器真实系统日期" in prompt
    assert date.today().isoformat() not in prompt


@pytest.mark.asyncio
async def test_prompt_contains_sql_rules():
    prompt = await _build()
    assert "MySQL 8.0" in prompt
    assert "ROUND(SUM(amount), 2)" in prompt
    assert "NULLIF(COUNT(*), 0)" in prompt
    assert "不虚构数据库" in prompt
    assert "SELECT / WITH 开头" in prompt


@pytest.mark.asyncio
async def test_default_as_of_date():
    builder = PetCareSystemPromptBuilder()
    assert builder.as_of_date == DEFAULT_AS_OF_DATE

# PetCare AI Analytics Assistant

> 宠物医院智能数据分析助手 —— 自然语言问数，直接得到答案。

**本项目基于 [vanna-ai/vanna](https://github.com/vanna-ai/vanna) 2.0.2（MIT License）进行二次开发。** 上游提供 Agent 工具调用框架、FastAPI 服务基础与 Web 组件；本项目在其上新增宠物医院业务层、领域提示词、DeepSeek 接入、SQL 安全控制与数据库只读账户，并修复了上游 CTE 查询结果传递缺陷。

---

## 1. 项目简介

运营人员用自然语言提问（如"最近三个月收入最高的医生是谁？"），系统通过 LLM 生成只读 SQL、查询 MySQL 业务库，并以流式表格 + 中文摘要的形式返回结果。面向宠物医院管理者与运营人员，用于收入分析、医生工作量、宠物类型统计、预约情况与客户消费分析。

## 2. 项目定位与适用场景

- **定位**：企业级 AI 应用实战项目（AI Application Engineer / FDE 方向求职展示），非生产系统。
- **适用场景**：宠物医院运营数据分析、Text-to-SQL 应用开发学习、LLM Agent + 只读数据库的工程实践。
- **覆盖分析类型**：收入分析 / 医生工作量 / 宠物类型统计 / 预约情况 / 客户消费。

## 3. 上游项目与许可证

| 项 | 值 |
|---|---|
| 上游项目 | [vanna-ai/vanna](https://github.com/vanna-ai/vanna)（Vanna Agents 2.x） |
| 版本 | **2.0.2**（上游 tag `v2.0.2`） |
| 许可证 | **MIT License**（`LICENSE` 保留上游 `Copyright (c) 2024 Vanna.AI`） |
| 本项目协议 | MIT（衍生作品，保留上游版权声明） |

## 4. 本项目新增内容（与上游的边界）

**上游提供（未修改或仅配置使用）：**
- Agent 工具调用框架（`vanna.core.agent`）
- FastAPI 服务基础与 SSE 路由（`vanna.servers.fastapi`）
- `RunSqlTool` 工具协议、`MySQLRunner`（PyMySQL）
- `<vanna-chat>` Web 组件

**本项目新增或改造（`petcare/` 目录为主）：**
- 宠物医院六表业务模型（owners / pets / doctors / appointments / medical_records / bills）与确定性合成数据（`petcare/db/`）
- 领域 Prompt（`PetCareSystemPromptBuilder`：收入口径、枚举映射、AS_OF_DATE 时间语义、工具调用收敛规则）
- DeepSeek Provider（`deepseek_llm.py` + `llm_factory.py`，OpenAI 兼容 Tool Call）
- SQL 安全层（`safety.py`：只读校验 + 危险内容规则 + 纵深防御）
- MySQL 只读账户 `petcare_reader`（最终权限边界）
- FastAPI 组装与错误脱敏（`main.py`）
- Mock / DeepSeek 双模式（`mock_llm.py` 零成本测试）
- **CTE 结果传递兼容修复**（上游 `run_sql.py` 仅识别 `SELECT`，`WITH` 查询被当作 DML 导致数据不返回；已在 PetCare 层修复）
- 测试与评估体系（90+ 单测 + 真实 LLM integration）

## 5. 架构图

```
┌─────────────────────────────────────────────────────────┐
│  Web UI  <vanna-chat>（SSE 流式表格 + 摘要）             │
└──────────────────────┬──────────────────────────────────┘
                       │ POST /api/vanna/v2/chat_sse
┌──────────────────────▼──────────────────────────────────┐
│  FastAPI（petcare/main.py，错误脱敏 + /health）          │
└──────────────────────┬──────────────────────────────────┘
┌──────────────────────▼──────────────────────────────────┐
│  Agent（Vanna core，max_tool_iterations=4）              │
│   ├─ PetCareSystemPromptBuilder（领域提示词）            │
│   ├─ LLM：PetCareMockLlmService 或 DeepSeekLlmService   │
│   └─ ToolRegistry → SafeRunSqlTool（只读校验 + CTE 修复）│
└──────────────────────┬──────────────────────────────────┘
┌──────────────────────▼──────────────────────────────────┐
│  MySQLRunner → petcare_db（petcare_reader 只读账户）     │
└─────────────────────────────────────────────────────────┘
```

## 6. 目录结构

```
├── src/vanna/            # 上游框架（含兼容 shim，见 docs）
├── petcare/              # ★ 本项目业务代码
│   ├── main.py           # 依赖组装 + FastAPI
│   ├── prompts.py        # 领域提示词
│   ├── safety.py         # SQL 安全层 + CTE 修复
│   ├── deepseek_llm.py   # DeepSeek Adapter
│   ├── llm_factory.py    # Mock/DeepSeek 双 Provider
│   ├── mock_llm.py       # 确定性 Mock LLM
│   ├── config.py         # .env 配置
│   ├── db/               # schema.sql / seed 生成 / setup / 只读账户
│   ├── docs/             # 安全设计 / 上游兼容性说明
│   └── tests/            # 90+ 测试
└── pyproject.toml        # 上游构建配置（editable 安装）
```

## 7. 环境要求

- Python **3.10+**（开发使用 3.12）
- MySQL **8.0+**（本地或 Docker）
- 可选：DeepSeek API Key（`LLM_PROVIDER=deepseek` 时）
- Windows / Linux / macOS 均可（Windows 需设置 `PYTHONIOENCODING=utf-8`）

## 8. 安装步骤

```bash
# 1. 克隆仓库后进入根目录
cd petcare-ai-analytics-assistant

# 2. 创建虚拟环境
python -m venv .venv
# Linux/macOS: source .venv/bin/activate   Windows: .venv\Scripts\activate

# 3. 安装（editable，含 servers/mysql/openai 依赖）
pip install -e ".[servers,mysql,openai]"
```

## 9. MySQL 数据库初始化

```bash
# 需本地 MySQL 8.0 正在运行
cd petcare/db
python setup_mysql.py --host 127.0.0.1 --user root --password YOUR_MYSQL_PASSWORD
# 输出行数校验：owners=30 pets=50 doctors=8 appointments=342 records=248 bills=500
```

数据库 `petcare_db` 与全部种子数据（确定性生成，`seed=42`，可复现）。

## 10. 创建只读账户

```bash
# 编辑 petcare/db/create_readonly_user.sql，替换密码占位符后执行：
mysql -u root -p < petcare/db/create_readonly_user.sql
# 验证：SHOW GRANTS FOR 'petcare_reader'@'localhost';  # 仅 SELECT on petcare_db.*
```

应用连接**必须**使用 `petcare_reader`，禁止 root（见 §16 安全设计）。

## 11. .env 配置

```bash
cp petcare/.env.example petcare/.env
# 编辑 petcare/.env：
#   MYSQL_USER=petcare_reader
#   MYSQL_PASSWORD=<只读账户密码>
#   LLM_PROVIDER=mock            # mock 或 deepseek
#   LLM_API_KEY=<你的 DeepSeek Key>   # deepseek 模式必需
#   PETCARE_AS_OF_DATE=2026-04-30     # 业务分析基准日
```

`.env` 已被 `.gitignore` 排除，**不要提交**。

## 12. Mock 模式启动（无需 API Key）

```bash
LLM_PROVIDER=mock python -m petcare.main    # Windows: $env:LLM_PROVIDER="mock"; python -m petcare.main
```

Mock 模式内置 5 个确定性问答（收入最高医生 / 消费最高客户 / 取消率 / 物种统计 / 工作量），用于链路验证与测试。

## 13. DeepSeek 模式启动

```bash
# petcare/.env 中设置 LLM_PROVIDER=deepseek 与 LLM_API_KEY
python -m petcare.main
```

模型默认 `deepseek-chat`（可通过 `LLM_MODEL` 修改），Tool Call 自动触发、流式返回。

## 14. 访问 Web UI

启动后浏览器打开：**http://127.0.0.1:8000**

- `/` Web 聊天界面（提问 → 表格 + 摘要）
- `/api/vanna/v2/chat_sse` SSE 流式接口
- `/health` 健康检查（含 provider/model）

## 15. 测试

```bash
# 默认测试（不消耗 API，使用 Mock LLM）
python -m pytest petcare/tests -q          # 期望 90 passed

# 真实 DeepSeek 集成测试（需要 LLM_API_KEY）
python -m pytest petcare/tests -m integration -q   # 期望 11 passed
```

## 16. 安全设计

- **纵深防御**：应用层 `SafeRunSqlTool` 只读校验（SELECT/WITH 白名单、禁写关键字、禁多语句、危险内容规则、超长限制）+ 数据库层 `petcare_reader` 只读账户（仅 SELECT，最终边界）
- **密钥管理**：全部走环境变量 / `.env`，不硬编码；错误响应脱敏（不泄露 Key、密码、连接串、堆栈）
- 详见 [`petcare/docs/database-security.md`](petcare/docs/database-security.md)

## 17. 上游兼容性说明

上游存在 7 项已知兼容问题（缺失模块、API 签名、CTE 分类缺陷等），修复方式与升级回归清单见 [`petcare/docs/upstream-compatibility.md`](petcare/docs/upstream-compatibility.md)。

## 18. 合成数据声明

**本项目数据库中的姓名、手机号、地址、账单与诊疗数据均为程序生成的合成数据**（`random.seed(42)` 确定性生成，手机号为不可拨打的占位符）。如有与真实人物/号码雷同，纯属巧合。

## 19. 当前限制

- **非生产系统**：面向学习与求职展示，未做多租户、鉴权体系与生产级监控
- **真实 LLM 输出存在随机性**：DeepSeek 生成的 SQL 偶发遗漏时间窗口等语义，建议关键查询人工复核
- **评估集规模有限**：当前 10 个基准问题的评估为采样性质，非统计完备基准
- 工具迭代上限 `max_tool_iterations=4`（保护边界）

## 20. 作者与联系方式

- 作者：Yuxi Wen（联系邮箱 17666534357wyx@gmail.com）
- 项目定位：AI Application Engineer / FDE 求职展示项目
- 欢迎 Issues / PR 交流

---

### License

MIT License（详见 [LICENSE](LICENSE)，保留上游 `Copyright (c) 2024 Vanna.AI`）。

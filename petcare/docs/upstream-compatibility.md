# PetCare 上游兼容性与版本策略

> 本文件记录 PetCare 项目依赖的 Vanna 上游缺陷、兼容修复原因、固定版本，
> 以及将来升级 Vanna 时必须运行的 CTE 回归测试。

## 1. 固定版本

| 项 | 值 |
|---|---|
| 包名 | `vanna`（Vanna Agents，2.x 重构线） |
| 固定版本 | **2.0.2** |
| 上游基线 | tag `v2.0.2`（原始 commit `365d061`；2026-08 历史清理后为 `2c97c0f`，内容 tree 完全等同） |
| 上游 tag | `v2.0.2` |
| 安装方式 | `pip install -e ".[servers,mysql,openai]"`（editable，在仓库根目录执行） |
| PetCare 发布节点 | tag `petcare-v0.1-deepseek`（基于本 fork 的 `aee8c69`） |

⚠️ 注意：`src/vanna/__init__.py` 的 `__version__ = "0.1.0"` 与 `pyproject.toml` 的
`version = "2.0.2"` 不一致（上游自身问题），版本判定以 `pyproject.toml` 为准。

## 2. 上游缺陷与兼容修复清单

### 2.1 已修改 Vanna 源码的修复（位于 vanna repo 内，升级时需评估取舍）

| # | 上游缺陷位置 | 现象 | 修复方式（commit `548b8c0`） | 升级时 |
|---|---|---|---|---|
| 1 | `src/vanna/core/` 缺少 `interfaces.py` / `models.py` / `rich_components.py` / `simple_components.py` 模块 | 2.0 重构把接口移到 `core/llm`、`core/agent` 等，但 5 个 example 仍 `from vanna.core.interfaces import ...`，import 直接失败 | 新增 4 个 shim 模块，从现有实现重导出（Agent/LlmService/SystemPromptBuilder/组件/模型） | 若上游已补齐可删除 shim，删除后重跑测试 |
| 2 | `src/vanna/core/registry.py`：只有 `register_local_tool(tool, access_groups)`，无 `register()` | README 与 examples 均调用 `tools.register(...)`，AttributeError | 新增 `register(tool, access_groups=None)` 别名 | 若上游已加 register 则删除本地别名 |
| 3 | `src/vanna/core/agent/agent.py:82`：`Agent.__init__` 新增**必填**参数 `user_resolver`、`agent_memory`，README/examples 未更新 | 按 README 构造 Agent 报 `missing 2 required positional arguments` | 参数改为可选；新增 `src/vanna/integrations/local/memory.py`（`InMemoryAgentMemory` + `AnonymousUserResolver` 默认实现） | 上游文档更新后可移除默认值，保留默认实现即可 |

### 2.2 在 PetCare 层修复（不修改 Vanna 源码）

| # | 上游缺陷位置 | 现象 | 修复方式（PetCare 层） |
|---|---|---|---|
| 4 | `src/vanna/tools/run_sql.py:63`：`query_type = args.sql.strip().upper().split()[0]`，仅 `== "SELECT"` 走结果集分支 | **WITH ... SELECT CTE 查询被当作 DML**：只返回 `"Query executed successfully. N row(s) affected."`，无 dataframe、数据不传给 LLM → LLM 反复查询直到工具迭代上限（Q10 根因） | `petcare/safety.py` 的 `SafeRunSqlTool` 重写 `execute`：安全校验后 SELECT / WITH 统一走结果集路径（DataFrameComponent + `result_for_llm` 完整数据 + row_count + CSV 落盘） |
| 5 | Agent 传给 LLM 的 tool schema 是 dict，`OpenAILlmService._build_payload` 期望 `ToolSchema` 对象 | AttributeError: 'dict' object has no attribute 'name' | `petcare/deepseek_llm.py`：`DeepSeekLlmService` 继承 `OpenAILlmService`，`_build_payload` 中归一化 dict 工具 |
| 6 | 框架 SSE 路由把 `str(exc)` 直接透传给前端 | 内部错误细节（可能含连接信息/堆栈）泄露 | `petcare/main.py`：`SafeChatHandler` 包装 `ChatHandler`，异常脱敏为安全消息并服务端记录完整日志 |
| 7 | 上游 UI 功能默认仅 admin 可见工具参数 | SSE 中不出现 status_card（无法审计生成 SQL） | `petcare/main.py`：Agent 配置 `ui_features` 允许展示工具名/参数（业务决策：运营可验证 SQL） |

### 2.3 环境性适配（非代码缺陷）

- Windows 控制台/日志默认 GBK 编码，服务打印 UTF-8 字符（如 🚀、✓）会崩溃：运行前设置 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1`。

## 3. 升级 Vanna 检查步骤

1. 记录基线：升级前运行
   ```bash
   python -m pytest petcare/tests -q          # 当前基线 90 passed
   python -m pytest petcare/tests -m integration -q   # 真实 DeepSeek 11 passed（需 LLM_API_KEY）
   ```
2. 升级 Vanna（重新 `pip install -e` 或替换版本）后，**先验证 2.1 中的 shim 是否与上游冲突**：
   - 若上游已修复对应缺陷：删除本地 shim / 别名 / 参数默认化，改回上游用法；
   - 若上游未修复：保留并确认仍可导入。
3. 运行 §4 的 CTE 回归测试（核心）。
4. 运行完整测试套件与安全回归（`test_sql_safety.py` 的全部攻击用例）。
5. 真实链路冒烟：`python -m petcare.main` 后跑 Q10 三次（§4.3）。

## 4. CTE 回归测试清单（升级 Vanna 后必须执行）

### 4.1 自动化（零 API 消耗）

```bash
python -m pytest petcare/tests/test_cte_query.py -v
```

覆盖（9 项）：
1. 普通 `SELECT` 返回 `DataFrameComponent`；
2. `WITH ... SELECT` 返回 `DataFrameComponent`（不是 NotificationComponent）；
3. CTE 的 `ToolResult.result_for_llm` 包含**实际列名与数据值**；
4. CTE 不能只返回 `"row(s) affected"`；
5. CTE 返回正确的 `row_count` 与 `metadata.results`；
6. `WITH ... INSERT/UPDATE/DELETE/DROP` 隐藏写操作仍被安全层拒绝（4 种）；
7. 复杂问题首次 CTE 成功返回完整结果后，模型直接生成摘要且**不再调用工具**（端到端 mock）。

### 4.2 连带回归

```bash
python -m pytest petcare/tests/test_sql_safety.py -v   # 安全规则（含 SELECT/WITH 白名单）
python -m pytest petcare/tests/test_chat_sse.py -v     # mock 端到端 SSE 链路
python -m pytest petcare/tests -m integration -v       # 真实 DeepSeek 10 题
```

### 4.3 手动冒烟（真实 LLM，验收标准）

对问题"养多只宠物的客户是否比单宠物客户消费更高？"连续运行 3 次：

- 每次 `tool_call_count <= 2`（期望 1-2 次）；
- 不触达工具迭代上限（摘要不得为 "Tool Execution Limit Reached"）；
- 每次生成最终业务摘要；
- 最终数据与手工基准一致（多宠物 15 位/¥9841.56、单宠物 6 位/¥3346.31）；
- SSE 中每次工具调用后出现 `dataframe` 事件（CTE 数据确实传给前端与 LLM）。

验收：3/3 生成摘要、无迭代上限、结果与基准一致。

## 5. 相关链接

- 数据库只读账户与安全边界：`petcare/docs/database-security.md`
- 发布节点：`git tag petcare-v0.1-deepseek`

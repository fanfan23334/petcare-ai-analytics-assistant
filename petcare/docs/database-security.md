# PetCare 数据库安全设计

> 纵深防御：应用层 SQL 校验（第一层）+ MySQL 只读账户（最终权限边界）

## 1. 为什么需要只读账户

`SafeRunSqlTool` 的字符串校验只是**应用层防护**，存在被绕过的理论风险（编码变体、解析差异、未来规则遗漏）。真正的安全边界必须放在数据库层：即使 LLM 或攻击者生成了恶意 SQL，数据库也会**直接拒绝**写操作。

生产/联调环境禁止使用 root 或具有写权限的账户连接数据库。

## 2. 账户设计

| 项 | 值 |
|---|---|
| 用户名 | `petcare_reader` |
| 主机 | `localhost`（本机应用） |
| 权限 | 仅 `SELECT` on `petcare_db.*` |
| 拒绝的权限 | INSERT / UPDATE / DELETE / CREATE / DROP / ALTER / FILE / SUPER / GRANT 等（未授予即不可用） |

创建脚本：`petcare/db/create_readonly_user.sql`（密码为占位符 `__READONLY_PASSWORD__`，执行前替换）。

## 3. 权限矩阵

| 操作 | 应用层校验 | petcare_reader |
|---|---|---|
| SELECT / WITH 只读查询 | ✅ 放行 | ✅ 允许 |
| INSERT / UPDATE / DELETE | ❌ 拒绝 | ❌ 拒绝（无权限） |
| DROP / ALTER / TRUNCATE / CREATE | ❌ 拒绝 | ❌ 拒绝（无权限） |
| INTO OUTFILE / LOAD_FILE / SLEEP 等 | ❌ 拒绝 | ❌ 拒绝（无 FILE 等权限） |
| 访问 information_schema / mysql / performance_schema / sys | ❌ 拒绝 | ❌ 拒绝（无权限/非目标库） |
| 多语句（分号） | ❌ 拒绝 | ❌ 拒绝（只授权单库 SELECT） |

两层独立配置，任何一层放行都无法执行写操作。

## 4. 配置方式（.env）

```ini
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=petcare_reader
MYSQL_PASSWORD=<只读账户的真实密码>
MYSQL_DATABASE=petcare_db
```

DeepSeek 真实模式必须使用 `petcare_reader` 连接，**禁止 root**。

## 5. 验证命令

```sql
-- 确认只读账户权限
SHOW GRANTS FOR 'petcare_reader'@'localhost';
-- 期望输出仅包含: GRANT SELECT ON `petcare_db`.* TO 'petcare_reader'@'localhost'

-- 写操作应失败
-- 使用只读账户连接后执行：
--   DELETE FROM petcare_db.bills;      -> ERROR 1142 (42000): DELETE command denied
--   DROP TABLE petcare_db.bills;       -> ERROR 1142 (42000): DROP command denied
```

## 6. 风险与限制

- 只读账户限制了**数据库层**风险；应用层仍有鉴权缺失风险（目前无用户系统，属阶段范围外）。
- `SELECT ... FROM` 只能访问 petcare_db，`LOAD_FILE` 需要 FILE 权限（未授予）。
- 密码存储于 `.env`（gitignore 排除），禁止写入代码、日志或提交到仓库。
- 若未来需要写入能力（如保存对话），应新增独立的受限写账户，而不是给 `petcare_reader` 加权限。

## 7. 检查清单（上线前）

- [ ] `create_readonly_user.sql` 已执行且占位符已替换
- [ ] `.env` 使用 `petcare_reader`，不是 root
- [ ] `SHOW GRANTS` 仅含 SELECT
- [ ] 应用层安全测试（pytest `test_sql_safety.py`）全部通过

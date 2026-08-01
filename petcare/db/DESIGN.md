# PetCare 数据库设计说明

> PetCare AI Analytics Assistant —— 宠物医院智能数据分析助手
> 数据库：MySQL 8.0（`petcare_db`），字符集 utf8mb4

## 1. 设计目标

为 Text-to-SQL 智能问答提供**贴近真实宠物医院业务**的数据底座。设计时以"自然语言问题 → 可执行 SQL"为第一约束，兼顾业务真实性与面试可讲性。

覆盖 5 类典型分析问题：

| 分析类别 | 核心数据表 | 示例问题 |
|---|---|---|
| 收入分析 | `bills` + `doctors` + `pets` | 最近三个月收入最高的医生是谁？ |
| 医生工作量 | `appointments` + `medical_records` + `doctors` | 哪位医生完成预约最多？ |
| 宠物类型统计 | `pets` | 猫和狗各有多少只？ |
| 预约情况 | `appointments` | 上周取消率是多少？ |
| 客户消费 | `bills` + `pets` + `owners` | 消费最高的客户是谁？ |

## 2. 实体关系（ER）

```mermaid
erDiagram
    owners ||--o{ pets : "拥有(1:N)"
    doctors ||--o{ appointments : "接诊(1:N)"
    pets ||--o{ appointments : "预约(1:N)"
    pets ||--o{ medical_records : "就诊(1:N)"
    doctors ||--o{ medical_records : "记录(1:N)"
    appointments |o--o| medical_records : "关联(0..1:1)"
    pets ||--o{ bills : "收费(1:N)"
    doctors ||--o{ bills : "负责(1:N)"
    medical_records |o--o{ bills : "关联(0..1:N)"

    owners { int owner_id PK; varchar name; varchar phone }
    doctors { int doctor_id PK; varchar name; varchar specialty; decimal salary }
    pets { int pet_id PK; int owner_id FK; varchar name; enum species }
    appointments { int appointment_id PK; int pet_id FK; int doctor_id FK; date appointment_date; enum status }
    medical_records { int record_id PK; int pet_id FK; int doctor_id FK; int appointment_id FK; date record_date; varchar diagnosis }
    bills { int bill_id PK; int pet_id FK; int doctor_id FK; int record_id FK; enum item_type; decimal amount; date billed_date; enum pay_status }
```

## 3. 每张表的作用与设计理由

### 3.1 `owners` 客户表（30 条）
- **作用**：宠物主人信息，客户消费分析的聚合主体。
- **设计理由**：`phone` 唯一（业务上电话是主要联系渠道）；`city` 单独字段支持"哪个城市的客户多"这类地域分析；`created_at` 支持"新客户 vs 老客户"分层。

### 3.2 `doctors` 医生表（8 条）
- **作用**：兽医花名册，收入、工作量分析的主体。
- **设计理由**：`specialty` 覆盖内科/外科/皮肤科/牙科/眼科/心脏科/骨科/营养科 8 个专科——专科是医院核心业务维度，可支撑"哪个科室收入最高"；`salary` 与 `bills` 收入可对比出"医生的创收能力 vs 人力成本"（简历亮点）；`hire_date` 支撑资历分析；`status` 支持在职/休假过滤。

### 3.3 `pets` 宠物表（50 条）
- **作用**：患者档案，连接 owner 与所有业务单据。
- **设计理由**：`species` 用英文枚举（cat/dog/bird/rabbit/hamster/reptile），避免中文枚举在 SQL 拼接/LLM 生成中的编码与匹配风险，语义映射写在系统提示词中；`breed`、`birth_date`、`weight`、`neutered` 支撑品种分布、年龄结构、体重管理、绝育率等统计问题——这些是宠物医院区别于普通诊所的特色分析点。

### 3.4 `appointments` 预约表（462 条）
- **作用**：排期数据，工作量与预约情况分析的核心。
- **设计理由**：`appointment_date` + `appointment_time` 分离，便于按天/月/时段聚合（"周末预约最多吗？"）；`status` 四态（booked/completed/cancelled/no_show）支撑**履约率/爽约率/取消率**分析——这是运营面试题高频点；`reason` 记录预约目的（疫苗/绝育/复诊），支撑预约结构分析。

### 3.5 `medical_records` 诊疗记录表（300 条）
- **作用**：就诊过程，疾病分布分析的来源。
- **设计理由**：`diagnosis` 与医生专科强相关（内科→肠胃炎/猫瘟，皮肤科→真菌感染…），保证"内科看什么病最多"这类问题有真实语义；`appointment_id` 可空（急诊/复诊直录），体现真实业务中的两种来源；`medicine`/`treatment`/`notes` 丰富文本便于演示。

### 3.6 `bills` 账单表（500 条）
- **作用**：收费明细，**收入分析的核心**。
- **设计理由**：
  - `item_type` 七类（consultation/examination/surgery/medicine/vaccine/hospitalization/grooming）——支撑"手术收入占比""药品收入趋势"等结构化收入分析；
  - `amount DECIMAL(10,2)` 精确金额，SUM 聚合语义清晰；
  - `pay_status` 三态（paid/unpaid/refunded）——**收入统计口径**的基石（见 §6）；
  - `billed_date` 单独日期字段（与就诊日期解耦），支撑按收费日期的时间窗口分析（"最近三个月"）；
  - `record_id` 可空（疫苗、美容等独立收费项），保证 bills 覆盖完整业务。

## 4. 数据规模与生成策略

| 表 | 数量 | 说明 |
|---|---|---|
| owners | 30 | 中文姓名、7 个城市 |
| doctors | 8 | 固定花名册（可预测，便于面试准备） |
| pets | 50 | 猫 20 / 狗 18 / 鸟 4 / 兔 4 / 仓鼠 2 / 爬宠 2 |
| appointments | 343 | 2025-08-01 ~ 2026-04-30，最近 3 个月（2026-02~04）密度更高；completed 255 / cancelled 70 / no_show 18 |
| medical_records | 247 | 完成预约的 95% + 急诊直录，诊断与专科强相关 |
| bills | 500 | 每条诊疗 1-3 项收费 + 独立疫苗/美容；最近 3 个月 286 条；paid 461 / unpaid 14 / refunded 25 |

- 时间截止：**所有业务数据（预约/诊疗/账单）截止到 2026-04-30**，时间窗口统一为 2025-08 ~ 2026-04，共 9 个月。
- 生成方式：`gen_seed.py`（Python，`random.seed(42)`）**确定性生成**，每次运行产出完全一致的 `seed.sql`——可复现性是面试加分点（"数据可复现，评估可对比"）。
- 医生收入差异化：靠项目类型与专科加权（心脏科检查贵、外科手术贵），形成可分析的分布。

## 5. Text-to-SQL 友好性设计要点

1. **枚举用英文小写 + COMMENT 中文语义**（`species='cat'` 表示猫）——LLM 生成 SQL 时枚举匹配稳定，提示词中给出映射表。
2. **时间字段统一 DATE 类型**——`billed_date`/`record_date`/`appointment_date` 都支持 `DATE_SUB`/`DATE_FORMAT`，中文时间表达（"最近三个月"）映射到 `INTERVAL 3 MONTH`；数据窗口为 2025-08 ~ 2026-04，"最近三个月"即 2026-02-01 ~ 2026-04-30。
3. **金额统一 DECIMAL(10,2)**——SUM/ROUND 聚合无精度歧义。
4. **收入口径显式化**：统计"收入"需 `pay_status='paid'`；提示词中固定口径（见 §6）。
5. **外键语义自解释**：`pet_id`/`doctor_id` 命名一致，JOIN 路径直观（bills→doctors→owners 均可一跳到根）。
6. **表注释（COMMENT）即业务文档**：schema.sql 中每张表、每个字段的中文注释，可作为提示词 / RAG 语料的直接来源。

## 6. 收入统计口径（面试必讲）

| 口径 | SQL 条件 | 适用场景 |
|---|---|---|
| 实收收入 | `pay_status='paid'` | 默认口径，推荐给 LLM |
| 应收收入 | 所有非 refunded 账单 | 含未支付 |
| 流水金额 | 全部账单 | 不含退款扣减，不推荐 |

> 面试话术：**"收入类问题统一用 `pay_status='paid'` 口径，未支付与已退款单独分析，避免口径不一致导致的歧义——这是业务系统与 Demo 的关键区别。"**

## 7. 支持的 NL 查询案例

### 收入分析
- "最近三个月收入最高的医生是谁？" → `bills JOIN doctors WHERE paid AND DATE_SUB(...3 MONTH) GROUP BY doctor ORDER BY SUM DESC`
- "哪个科室收入最高？" → 按 `doctors.specialty` 分组
- "上个月手术收入占比多少？" → `item_type='surgery'` / 总实收
- "每月收入趋势？" → `DATE_FORMAT(billed_date,'%Y-%m') GROUP BY`

### 医生工作量分析
- "哪位医生完成预约最多？" → `appointments GROUP BY doctor WHERE status='completed'`
- "哪位医生爽约率最高？" → `SUM(status='no_show')/COUNT(*)`
- "各专科的月均接诊量？" → 时间 + specialty 分组
- "哪个医生创收能力最强（收入/月薪比）？" → `SUM(bills)/salary`

### 宠物类型统计
- "猫和狗各有多少只？" → `pets GROUP BY species`
- "哪种品种的宠物最多？" → `breed GROUP BY`
- "绝育率是多少？" → `SUM(neutered)/COUNT(*)`
- "平均体重最重的物种？" → `AVG(weight) GROUP BY species`

### 预约情况分析
- "本月的预约量/取消率？" → `status` 聚合 + 时间窗口
- "周几预约最多？" → `DAYOFWEEK(appointment_date)`
- "哪些宠物经常爽约？" → `pet_id GROUP BY no_show`
- "预约最多的前 5 个预约原因？" → `reason GROUP BY`

### 客户消费分析
- "消费最高的客户是谁？" → `bills JOIN pets JOIN owners GROUP BY owner`
- "人均消费多少？" → `SUM/COUNT(DISTINCT owner)`
- "养多只宠物的客户消费更高吗？" → `COUNT(pets) vs SUM(bills)` 对比
- "哪个城市的客户消费最多？" → `owners.city GROUP BY`

## 8. 文件说明

| 文件 | 作用 |
|---|---|
| `schema.sql` | 建库建表 DDL（8 条语句） |
| `gen_seed.py` | 确定性 seed 生成器（seed=42） |
| `seed.sql` | 生成的种子数据（执行后 462 预约 / 300 诊疗 / 500 账单） |
| `setup_mysql.py` | 一键建库：执行 schema + seed + 校验行数 |

```bash
# 重建数据库（幂等：TRUNCATE 后重新导入）
python petcare/db/setup_mysql.py
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

团队工时分析系统：从 Notion 工时数据库拉取数据，生成包含人员分析、项目分析、图表、下周安排、AI 深度分析的完整周报。已部署到 Streamlit Community Cloud。

## Commands

```bash
# 启动 Streamlit Web 应用
streamlit run app.py

# CLI 生成报告
python main.py --input data/timesheet.csv --output output/ --date 2026-02-18

# 自动化周报（从 Notion 拉取 + 生成报告）
# ⚠️ 默认输出到 ~/Documents/MIH_Reports；本地重生供前端/仓库用必须加 --output-dir ./reports
# ⚠️ 邮件仅当显式传 --email 才发（不带地址=默认收件人），手动重生默认静默
python auto_weekly_report.py --output-dir ./reports           # 本地重生(不发邮件)
python auto_weekly_report.py --output-dir ./reports --email    # 同时发邮件
python auto_weekly_report.py --week-offset -1 --output-dir ./reports

# 钉钉推送本地手测（需先 export DINGTALK_WEBHOOK / DINGTALK_SECRET）
python dingtalk_reminder.py
python dingtalk_report_push.py

# 测试
python test_spring_festival_weeks.py          # 节假日逻辑测试
NOTION_API_TOKEN=xxx python test_notion_connection.py  # Notion 连接测试

# 语法检查（无 lint 工具配置）
python -c "import py_compile; py_compile.compile('app.py', doraise=True)"
```

## Architecture

数据流水线：**数据源 → 加载 → 预处理 → 分析 → 输出**

### 入口脚本

- `app.py` — Streamlit Web 前端（6 个 tab），支持三种数据源：预生成报告 / Notion 直连 / CSV 上传
- `main.py` — 命令行入口，读 CSV 输出报告+图表
- `auto_weekly_report.py` — 定时任务入口，从 Notion 拉数据 → 分析 → 可选邮件通知。邮件 **opt-in**（`CONFIG.email.enabled` 默认 False，仅 `--email` 时发；CI `weekly_report.yml` 已显式传 `--email`）。默认输出目录是 `~/Documents/MIH_Reports`，CI/本地重生靠 `--output-dir ./reports`。GitHub Actions 每周五北京时间 13:00 自动运行
- `dingtalk_reminder.py` — 周五 9:00 钉钉群提醒填工时，无数据依赖。Workflow: `.github/workflows/dingtalk_reminder.yml`
- `dingtalk_report_push.py` — 周五 14:00 钉钉群推送本周工时分析周报，读 `reports/report_YYYYMMDD.json` sidecar 的 `weekStats` + `gammaUrl`。sidecar 缺失/字段不全 → 走兜底分支并 @胡若玫。Workflow: `.github/workflows/dingtalk_report_push.yml`

### 核心模块 (`src/`)

- **data_loader.py** — `load_timesheet()` 加载 CSV，`validate_data()` 校验必需列（成员、日期、工时 h）
- **preprocessor.py** — `preprocess_data(df, reference_date)` 标准化姓名、清理项目名、按 ISO 周划分周期类型（本周/下周/往期/未来），挂载员工配置。`filter_by_period(df, "本周")` 按周期过滤
- **analyzer.py** — `TimesheetAnalyzer(df)` 核心分析引擎。返回 `MemberAnalysis` 和 `ProjectAnalysis` dataclass。状态判定阈值：超负荷 >1.2x 标准工时，偏低 <0.7x。标准工时会根据节假日和请假自动调整
- **ai_analyzer.py** — Claude API 深度分析（4 维度 10 指标）。`generate_quick_scan()` 是纯本地规则计算，不调 API。`analyze()` 调用 Claude API 返回 `AIInsightResult`
- **notion_connector.py** — `NotionConnector` 封装 Notion API（2025-09-03 版本，使用 data_sources 端点）。`fetch_timesheet(start, end)` 返回与 CSV 格式一致的 DataFrame
- **visualizer.py** — matplotlib 图表生成，`create_visualizations()` 生成组合图，`create_single_chart()` 生成单图
- **report_generator.py** — `generate_markdown_report()` 生成 Markdown 报告，支持 next_week 和 ai_insights 可选参数

### 主题与样式

- `.streamlit/config.toml` — Streamlit 主题配置（indigo 主色、浅色背景、slate 文字色）
- `app.py` 内嵌 CSS — 自定义 metric 卡片、tab 栏、按钮、侧边栏等组件样式
- `src/visualizer.py` 中 `COLORS` dict 和 `PALETTE` list — 图表统一调色板，所有图表颜色从此处引用

### 配置 (`config/`)

- `employees.yaml` — 员工列表（中英文名、类型、标准工时、入职日期 onboard_date、离职日期 offboard_date、请假记录）+ 全局默认值（阈值、AI 模型配置）+ 项目分类关键词
- `holidays.yaml` — 中国法定节假日，type: `holiday`（放假）或 `workday`（调休上班）
- `__init__.py` — `get_employees_config()` / `get_holidays_config()` 加载 YAML

### 周期判定逻辑

基于 `reference_date` 的 ISO 周数：同 ISO 周 = 本周，ISO 周 +1 = 下周，更早 = 往期，更远 = 未来。周一是每周第一天。Notion 直连模式拉取 reference_date 所在周一到下周日共 14 天数据。

## Key Conventions

- 所有中文字段名与 Notion 数据库一致：`成员`、`日期`、`工时 h`、`MIH Projects 项目库`、`工作阶段`、`优先级`、`项目属性`
- 员工中英文名映射在 `preprocessor.py` 的 `_standardize_member_names()` 中处理
- 员工离职：在 `config/employees.yaml` 给该员工加 `offboard_date: "YYYY-MM-DD"`（离职生效日，含；与 `onboard_date` 对称）。`preprocessor.py:_filter_departed_members` 按 **ISO 报告周** 粒度整周剔除其工时（含离职前几天），离职生效周及之后全链路（分析/图表/AI/sidecar/钉钉）不出现，离职前历史周不受影响。⚠️ 分析是**数据驱动**的（按 DataFrame 里实际有数据的成员，非 yaml 名单）——仅从 Notion 删人但工时记录仍在时，本周报告仍会拉到他并可能误标「📉 偏低」，必须靠 offboard_date 剔除。测试：`python test_offboard_filter.py`
- ⚠️ offboard 是**按名字匹配**剔除的，但离职后**删除 Notion 账号**会抹掉工时行的成员名（person `name=null`→「未知」，或 people 空数组→`""`/CSV 往返后 NaN→「未知」），此时名字匹配漏剔，会冒出幻影「未知/按需」成员。兜底在 `preprocessor.py:_filter_unidentified_members`（step 2.5，姓名标准化后）：丢弃 `成员_中文` 为 未知/空/NaN 的行并打印告警。语义安全——未映射的真实人名会原样透传，绝不会变「未知」。测试：`python test_unidentified_filter.py`
- Streamlit「预生成报告」模式是**实时从 CSV 重算**（`app.py:803-806` `preprocess_data`+`TimesheetAnalyzer`），不读 md/json。改预处理/分析逻辑后**前端重启即生效**；但 md/sidecar/PDF/Gamma 是静态产物，需 `auto_weekly_report.py` 重生才更新。前端表里若仍有旧数据，先分清看的是实时重算（重启 app）还是静态产物（重生）
- 侧边栏「员工配置预览」(`app.py:670`)：`offboard_date <= 今天` 的员工类型显示为「离职」、整行置灰、稳定排序到表末（在职原顺序不变）。判定独立于报告周，用 `date.today()`
- API Token 通过 Streamlit secrets (`st.secrets`) 或环境变量 (`os.getenv`) 读取，优先 secrets
- `@st.cache_data` 用于缓存数据加载，Notion 直连 TTL=300 秒
- GitHub Actions 生成的报告提交到 `reports/` 目录，文件名格式 `timesheet_YYYYMMDD.csv` / `report_YYYYMMDD.md`
- `reference_date` in `app.py` is independent of the "预生成报告" CSV picker. When matching dated artifacts (e.g., `reports/report_YYYYMMDD.json` sidecar), match by ISO week not exact date — derive Monday-of-week from both sides.
- AI 深度分析默认从 sidecar 复用,不调 Claude API。仅当用户在 Tab 6 勾选「🔁 强制重跑 AI 深度分析」时才重跑。新增/删除 `ai_insights` session_state 时同步处理 `ai_insights_source` 标签
- PPT/PDF 下载文件名固定为 `工时分析周报_数据平台部_YYYYMMDD.pdf`(Streamlit Tab 6 下载按钮 + 邮件附件),日期取 `reference_date` / `ref_date`
- `send_email(attachments=...)` 支持 `str` 或 `(path, display_name)` 元组;中文文件名走 RFC 2231 `filename*=utf-8''…` 头(已在 `auto_weekly_report.py:send_email` 内部封装)
- 未立项 / 临时指派 工时口径统一在 `src/report_pipeline.py:UNALIGNED_KEYWORDS = ("未立项", "临时指派")`，改这里会同步影响 sidecar `weekStats.unalignedHours` 和钉钉推送内容
- Sidecar `reports/report_YYYYMMDD.json` 的 `weekStats` 字段（weekNum / totalHours / projectCount / top3Projects / categories / unalignedHours / unalignedPct / nextWeek）由 `src/report_pipeline.py:_compute_week_stats` 生成，是 `dingtalk_report_push.py` 的稳定契约，删字段会触发兜底分支
- `weekStats.categories` 是按 `项目属性` 的四分类（顺序固定 `战略项目 / 付费项目 / 售前项目 / 支持/运营项目`，见 `report_pipeline.py:CATEGORY_ORDER`），每类含 `hours` + `top1{name,hours}`；不属于这 4 类的项目计入 totalHours 但不进 categories（四类之和可能 < 总工时）。`weekStats.nextWeek` = 下周 `{totalHours, projectCount}`，来自 `next_week_summary`，缺失时为 null。`未立项/临时指派`(unalignedHours) 与 categories **不去重**——它当前归在「支持/运营项目」属性下，会被同时计入。钉钉推送 `categories`/`nextWeek` 缺失时回退到 Top3 段落、省略下周段（不触发 @胡若玫 兜底）

## Environment Variables

All read via `os.getenv()` (Streamlit also accepts `st.secrets`):

- `NOTION_API_TOKEN` — required for Notion API
- `ANTHROPIC_API_KEY` — Claude AI deep analysis; missing → graceful skip
- `MAIL_SENDER` — 126 邮箱授权码 (not login password); missing → email skipped
- `GAMMA_API_KEY` — Gamma Pro+ key for online PPT; missing → skip with warning
- `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` — 钉钉群机器人 webhook URL + 加签密钥；任一缺失 → `dingtalk_reminder.py` / `dingtalk_report_push.py` 抛 ValueError

All of the above must also live in GitHub Actions secrets for the Friday CI workflows to use them.

## When Making Changes

- Always read existing code before modifying — understand the context first
- Show me a brief plan before writing code, wait for confirmation
- Use `git diff` to show me what you changed after each file modification
- Run a quick smoke test if applicable (e.g., `streamlit run app.py` to verify UI loads)
- For new external API integrations: verify in this order — (1) env-var-missing path returns None gracefully, (2) minimal isolated call (e.g. `python -c "from src.X import fn; fn(minimal_input)"`), (3) full pipeline e2e
- Make small, focused commits — one logical change per commit
- Use Conventional Commits prefixes: feat: / fix: / chore: / docs: / refactor:

## Important: Never Commit
- `.env` file (contains API keys)
- Any hardcoded API keys, tokens, or passwords in code
- Files matching patterns in `.gitignore`

## Branch Workflow
- Never commit directly to main
- Create feature branch: `git checkout -b feat/xxx` or `fix/xxx`
- Make changes, commit, push, create PR on GitHub
- Self-review the PR before merging

## Known Issues / Tech Debt

- [ ] Webhook notifications are coded but disabled (planned activation in Phase 3). Email is active via 126 SMTP (smtp.126.com:465 SSL) using `MAIL_SENDER` env var
- [ ] CI `git add reports/` commits the Gamma PDF every Friday (~4 MB/week, ~200 MB/year). Consider git LFS or `.gitignore reports/*.pdf` (would break Streamlit Cloud's PDF download button)

## Gamma Integration

`auto_weekly_report.py` calls Gamma Generate API (via `src/gamma_client.py`) to turn the Markdown report into an online presentation. Sidecar `reports/report_YYYYMMDD.json` stores `gammaUrl` / `exportUrl` (so `app.py` Tab 6 can embed the deck via iframe) plus `aiInsights` / `aiInsightsGeneratedAt` (serialized `AIInsightResult` — Streamlit loads it on data load to skip the Claude API call). Requires `GAMMA_API_KEY` env var (Gamma Pro+); falls back to skip with a warning if missing.

`AIInsightResult` (de)serialization helpers live in `src/ai_analyzer.py`: `serialize_ai_insights()` / `deserialize_ai_insights()`. Pipeline-side wiring: `src/report_pipeline.py:render_report_artifacts` writes the field; `app.py` (data-load block) and the Tab 6 regen path read it.

Gamma API quirks: `folderIds` is a JSON array (plural), `themeId` lowercase `d`, generation is async with polling at `GET /v1.0/generations/{id}`, embed URL = `gammaUrl.replace("/docs/", "/embed/")`.

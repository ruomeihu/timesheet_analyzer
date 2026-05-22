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
python auto_weekly_report.py
python auto_weekly_report.py --week-offset -1 --output-dir ./reports

# 测试
python test_spring_festival_weeks.py          # 节假日逻辑测试
NOTION_API_TOKEN=xxx python test_notion_connection.py  # Notion 连接测试

# 语法检查（无 lint 工具配置）
python -c "import py_compile; py_compile.compile('app.py', doraise=True)"
```

## Architecture

数据流水线：**数据源 → 加载 → 预处理 → 分析 → 输出**

### 三个入口

- `app.py` — Streamlit Web 前端（6 个 tab），支持三种数据源：预生成报告 / Notion 直连 / CSV 上传
- `main.py` — 命令行入口，读 CSV 输出报告+图表
- `auto_weekly_report.py` — 定时任务入口，从 Notion 拉数据 → 分析 → 可选邮件/webhook 通知。GitHub Actions 每周五北京时间 13:00 自动运行

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

- `employees.yaml` — 员工列表（中英文名、类型、标准工时、入职日期、请假记录）+ 全局默认值（阈值、AI 模型配置）+ 项目分类关键词
- `holidays.yaml` — 中国法定节假日，type: `holiday`（放假）或 `workday`（调休上班）
- `__init__.py` — `get_employees_config()` / `get_holidays_config()` 加载 YAML

### 周期判定逻辑

基于 `reference_date` 的 ISO 周数：同 ISO 周 = 本周，ISO 周 +1 = 下周，更早 = 往期，更远 = 未来。周一是每周第一天。Notion 直连模式拉取 reference_date 所在周一到下周日共 14 天数据。

## Key Conventions

- 所有中文字段名与 Notion 数据库一致：`成员`、`日期`、`工时 h`、`MIH Projects 项目库`、`工作阶段`、`优先级`、`项目属性`
- 员工中英文名映射在 `preprocessor.py` 的 `_standardize_member_names()` 中处理
- API Token 通过 Streamlit secrets (`st.secrets`) 或环境变量 (`os.getenv`) 读取，优先 secrets
- `@st.cache_data` 用于缓存数据加载，Notion 直连 TTL=300 秒
- GitHub Actions 生成的报告提交到 `reports/` 目录，文件名格式 `timesheet_YYYYMMDD.csv` / `report_YYYYMMDD.md`
- `reference_date` in `app.py` is independent of the "预生成报告" CSV picker. When matching dated artifacts (e.g., `reports/report_YYYYMMDD.json` sidecar), match by ISO week not exact date — derive Monday-of-week from both sides.
- AI 深度分析默认从 sidecar 复用,不调 Claude API。仅当用户在 Tab 6 勾选「🔁 强制重跑 AI 深度分析」时才重跑。新增/删除 `ai_insights` session_state 时同步处理 `ai_insights_source` 标签
- PPT/PDF 下载文件名固定为 `工时分析周报_数据平台部_YYYYMMDD.pdf`(Streamlit Tab 6 下载按钮 + 邮件附件),日期取 `reference_date` / `ref_date`
- `send_email(attachments=...)` 支持 `str` 或 `(path, display_name)` 元组;中文文件名走 RFC 2231 `filename*=utf-8''…` 头(已在 `auto_weekly_report.py:send_email` 内部封装)

## Environment Variables

All read via `os.getenv()` (Streamlit also accepts `st.secrets`):

- `NOTION_API_TOKEN` — required for Notion API
- `ANTHROPIC_API_KEY` — Claude AI deep analysis; missing → graceful skip
- `MAIL_SENDER` — 126 邮箱授权码 (not login password); missing → email skipped
- `GAMMA_API_KEY` — Gamma Pro+ key for online PPT; missing → skip with warning

All four must also live in GitHub Actions secrets for the Friday CI workflow to use them.

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

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

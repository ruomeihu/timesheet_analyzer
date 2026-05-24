# 📊 团队工时分析系统 (Timesheet Analyzer)

从 Notion 工时数据库自动生成周报，支持云端部署、手机随时查看。

## 功能概览

- **6 个分析维度**：人员分析、项目分析、可视化图表、下周安排、AI 深度分析、报告下载
- **3 种数据源**：预生成报告（秒开）、Notion 直连（实时）、CSV 上传（手动）
- **自动化周报**：GitHub Actions 每周五 13:00（北京时间）自动生成
- **AI 深度分析**：Claude API 驱动的四维度十指标分析
- **移动端友好**：手机浏览器打开即用

## 在线访问

打开 Streamlit Cloud 应用：[timesheetanalyzer.streamlit.app](https://timesheetanalyzer-n6jtxnowfsfvtfvv6pzkaw.streamlit.app/)

## 项目结构

```
timesheet_analyzer/
├── config/                          # 配置层
│   ├── employees.yaml               # 员工配置（姓名、标准工时、请假）
│   └── holidays.yaml                # 中国法定节假日配置
├── src/                             # 业务逻辑层
│   ├── data_loader.py               # 数据加载：读取 CSV
│   ├── preprocessor.py              # 数据预处理：清洗、分周
│   ├── analyzer.py                  # 分析引擎：计算各种指标
│   ├── visualizer.py                # 可视化：生成图表
│   ├── report_generator.py          # 报告生成：输出 Markdown
│   ├── ai_analyzer.py               # AI 分析：Claude API 深度洞察
│   ├── notion_connector.py          # Notion API 连接器
│   └── holiday_helper.py            # 节假日助手：处理调休
├── reports/                         # GitHub Actions 自动生成的周报
├── .github/workflows/
│   └── weekly_report.yml            # 定时任务：每周五自动生成报告
├── .streamlit/
│   └── secrets.toml.example         # Streamlit Cloud secrets 模板
├── app.py                           # Streamlit Web 前端
├── main.py                          # 命令行入口
├── auto_weekly_report.py            # 自动化周报脚本
└── requirements.txt                 # Python 依赖
```

## 快速开始

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 NOTION_API_TOKEN 和 ANTHROPIC_API_KEY

# 3. 启动 Streamlit
streamlit run app.py
```

### 命令行生成报告

```bash
# 分析本周
python auto_weekly_report.py

# 分析上周
python auto_weekly_report.py --week-offset -1

# 指定输出目录
python auto_weekly_report.py --output-dir ./reports
```

## 云端部署

### Streamlit Cloud

1. Fork 或连接此仓库到 [share.streamlit.io](https://share.streamlit.io)
2. Main file 设为 `app.py`
3. 在 Advanced settings → Secrets 中配置：
   ```toml
   NOTION_API_TOKEN = "ntn_your_token"
   ANTHROPIC_API_KEY = "sk-ant-your_key"  # 可选
   ```

### GitHub Actions 定时任务

每周五北京时间 13:00 自动从 Notion 拉取数据、生成报告、提交到 `reports/` 目录。

需要在仓库 Settings → Secrets → Actions 中配置：

| Secret | 说明 |
|--------|------|
| `NOTION_API_TOKEN` | Notion API Token |
| `ANTHROPIC_API_KEY` | Claude AI 深度分析（可选） |
| `MAIL_SENDER` | 126 邮箱授权码，用于发送周报（可选） |
| `GAMMA_API_KEY` | Gamma Pro+ key，生成在线 PPT（可选） |
| `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` | 钉钉机器人，用于周五提醒 + 周报推送 |

也可以随时手动触发：Actions → Weekly Timesheet Report → Run workflow。

## 配置说明

### 员工配置 (`config/employees.yaml`)

```yaml
employees:
  - name_cn: "张三"
    name_en: "Zhang San"
    type: "全职"            # 全职/兼职/按需
    standard_hours: 40      # 周标准工时
    department: "研发"
    leaves:                 # 请假记录
      - start: "2026-02-16"
        end: "2026-02-17"
        type: "年假"
```

### 节假日配置 (`config/holidays.yaml`)

```yaml
holidays:
  2026:
    - date: "2026-01-01"
      name: "元旦"
      type: "holiday"
    - date: "2026-01-04"
      name: "元旦调休"
      type: "workday"       # 调休上班
```

## 数据源说明

| 数据源 | 适用场景 | 加载速度 |
|--------|----------|----------|
| 预生成报告 | 查看定时快照，无需等待 | 秒开 |
| Notion 直连 | 需要最新实时数据 | ~15 秒 |
| CSV 上传 | 离线使用或调试 | 即时 |

## 技术栈

- **前端**：Streamlit
- **数据处理**：pandas, numpy
- **可视化**：matplotlib, seaborn
- **AI 分析**：Anthropic Claude API
- **数据源**：Notion API
- **自动化**：GitHub Actions
- **部署**：Streamlit Community Cloud

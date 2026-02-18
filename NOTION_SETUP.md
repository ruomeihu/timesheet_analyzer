# 🔗 Notion 数据连接器使用指南

本指南将帮助你在 VS Code 中设置并运行 Notion 数据连接器，实现自动从 Notion 获取工时数据。

---

## 📋 前置准备

### 1. 确保你已经安装了

- [x] VS Code
- [x] Python 3.8+
- [x] 本项目的依赖包

### 2. 获取 Notion API Token

1. 访问 https://www.notion.so/my-integrations
2. 点击 **"+ New integration"**
3. 填写名称（如 "MIH Timesheet"）
4. 选择你的 Workspace
5. 点击 **Submit**
6. 复制 **Internal Integration Secret**（以 `ntn_` 开头）

### 3. 授权 Integration 访问数据库

⚠️ **这一步很重要！**

1. 打开你的 Notion 工时数据库页面
2. 点击右上角的 `•••` 菜单
3. 点击 **"Add connections"**
4. 搜索并选择你刚创建的 Integration
5. 点击 **Confirm**

---

## 🖥️ VS Code 设置步骤

### 步骤 1：打开项目文件夹

```
文件 → 打开文件夹 → 选择 timesheet_analyzer 文件夹
```

### 步骤 2：打开终端

```
终端 → 新建终端
或者快捷键：Ctrl + ` (反引号)
```

### 步骤 3：安装依赖

在终端中运行：

```bash
pip install pandas requests pyyaml matplotlib seaborn streamlit
```

### 步骤 4：设置环境变量

**Windows (PowerShell):**
```powershell
$env:NOTION_API_TOKEN = "你的token"
```

**Windows (CMD):**
```cmd
set NOTION_API_TOKEN=你的token
```

**Mac/Linux:**
```bash
export NOTION_API_TOKEN="你的token"
```

> 💡 **提示**：环境变量只在当前终端窗口有效。如果关闭终端需要重新设置。

---

## 🚀 使用方法

### 方法 1：命令行导出数据

```bash
# 导出指定日期范围的数据
python src/notion_connector.py --start 2025-09-22 --end 2025-09-30 --output data/sept_w39.csv

# 查看帮助
python src/notion_connector.py --help
```

### 方法 2：在 Python 中使用

创建一个新文件 `test_notion.py`：

```python
import os
from src.notion_connector import fetch_timesheet, save_to_csv

# 设置 Token（如果没有通过环境变量设置）
# os.environ["NOTION_API_TOKEN"] = "你的token"

# 获取数据
print("📥 正在从 Notion 获取数据...")
df = fetch_timesheet("2025-09-22", "2025-09-30")

print(f"✅ 获取到 {len(df)} 条记录")
print(df.head())

# 保存为 CSV
save_to_csv(df, "data/timesheet_export.csv")
print("💾 已保存到 data/timesheet_export.csv")
```

然后运行：
```bash
python test_notion.py
```

### 方法 3：完整分析流程

```bash
# 第一步：从 Notion 导出数据
python src/notion_connector.py --start 2025-09-22 --end 2025-09-30 --output data/week39.csv

# 第二步：运行分析
python main.py --input data/week39.csv --date 2025-09-28 --output output/

# 第三步：查看报告
# 报告在 output/ 文件夹中
```

---

## 🎯 常用命令速查

| 场景 | 命令 |
|------|------|
| 导出本周数据 | `python src/notion_connector.py -s 2026-01-20 -e 2026-01-24 -o data/this_week.csv` |
| 导出上月数据 | `python src/notion_connector.py -s 2025-12-01 -e 2025-12-31 -o data/dec.csv` |
| 分析并生成报告 | `python main.py -i data/this_week.csv -d 2026-01-24` |
| 启动 Web 界面 | `streamlit run app.py` |

---

## 🔧 永久保存 Token（可选）

如果不想每次都设置环境变量，可以创建配置文件：

### 方法 A：创建 .env 文件

1. 在项目根目录创建 `.env` 文件：
```
NOTION_API_TOKEN=你的token
```

2. 安装 python-dotenv：
```bash
pip install python-dotenv
```

3. 在代码开头添加：
```python
from dotenv import load_dotenv
load_dotenv()
```

### 方法 B：使用 config.yaml

1. 创建 `config/secrets.yaml`：
```yaml
notion:
  api_token: "你的token"
  database_id: "27860a7d47d280ab9529e599217f6730"
```

2. 在 `.gitignore` 中添加这个文件（防止泄露）

---

## ❓ 常见问题

### Q1: 提示 "需要 Notion API Token"
**A:** 检查环境变量是否设置正确。在终端运行：
```bash
# Windows PowerShell
echo $env:NOTION_API_TOKEN

# Mac/Linux
echo $NOTION_API_TOKEN
```

### Q2: 提示 "Notion API 错误: 401"
**A:** Token 无效或已过期。请重新生成 Token。

### Q3: 提示 "Notion API 错误: 403"
**A:** Integration 没有权限访问数据库。请按照"授权 Integration"步骤操作。

### Q4: 项目名称显示为 ID 而不是名称
**A:** 这是正常的，因为获取关联页面的标题需要额外的 API 调用。可以在数据预处理时进行映射。

### Q5: 导出的数据缺少某些字段
**A:** 检查 Notion 数据库的字段名称是否与代码中一致。如有变化需要修改 `notion_connector.py`。

---

## 📊 数据库字段映射

| Notion 字段 | CSV 列名 | 类型 |
|------------|---------|------|
| 工作内容 | 工作内容 | 文本 |
| MIH Projects 项目库 | MIH Projects 项目库 | 关联 |
| 成员 | 成员 | 人员 |
| 日期 | 日期 | 日期 |
| 工时 h | 工时 h | 数字 |
| 工作阶段 | 工作阶段 | 单选 |
| 优先级 | 优先级 | Rollup |
| 项目属性 | 项目属性 | Rollup |

---

## 🔐 安全提醒

1. **不要**将 Token 提交到 Git
2. **不要**在公共场合分享 Token
3. 定期**轮换** Token（在 Notion Integration 页面重新生成）
4. 将 `.env` 和 `secrets.yaml` 添加到 `.gitignore`

---

## 🎉 下一步

设置完成后，你可以：

1. **自动化周报**：创建定时任务每周五自动导出分析
2. **集成到 Streamlit**：在 Web 界面添加"从 Notion 导入"按钮
3. **实时同步**：使用 Notion Webhooks 实现数据变更自动同步

有问题随时问我！

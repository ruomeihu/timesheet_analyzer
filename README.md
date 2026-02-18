# 🕐 团队工时分析系统 (Timesheet Analyzer)

> 从 Jupyter Notebook 到工程化项目的完整学习指南

## 📚 给 Iris 的 VS Code 入门教程

### 第一步：理解"工程化"是什么

**Before（你现在的方式）：**
```
一个巨大的 .ipynb 文件 → 所有代码混在一起 → 难以维护和复用
```

**After（工程化方式）：**
```
timesheet_analyzer/
├── config/          # 📁 配置文件（员工信息、节假日）
├── src/             # 📁 核心代码模块
├── app.py           # 🎨 Streamlit 前端界面
├── main.py          # 🚀 命令行入口
└── README.md        # 📖 说明文档
```

**好处：**
1. **单一职责**：每个文件只做一件事
2. **可复用**：模块可以被其他项目引用
3. **易维护**：修改某个功能只需要改一个文件
4. **可测试**：每个模块可以独立测试

---

### 第二步：VS Code 安装和配置

#### 2.1 下载安装
1. 访问 https://code.visualstudio.com
2. 下载对应系统版本（Windows/Mac）
3. 安装时勾选 "Add to PATH"

#### 2.2 必装插件（在 VS Code 左侧扩展图标中搜索安装）
| 插件名 | 作用 |
|-------|------|
| Python | Python 语言支持 |
| Pylance | 智能代码提示 |
| Jupyter | 运行 .ipynb 文件 |
| Chinese (Simplified) | 中文界面 |

#### 2.3 打开项目
```bash
# 方式1：命令行（推荐）
cd 你的项目路径
code .

# 方式2：VS Code 菜单
文件 → 打开文件夹 → 选择 timesheet_analyzer 文件夹
```

---

### 第三步：理解项目结构

```
timesheet_analyzer/
│
├── 📁 config/                    # 配置层
│   ├── __init__.py               # 使 config 成为 Python 包
│   ├── employees.yaml            # 员工配置（姓名、标准工时）
│   └── holidays.yaml             # 中国法定节假日配置
│
├── 📁 src/                       # 业务逻辑层
│   ├── __init__.py               # 使 src 成为 Python 包
│   ├── data_loader.py            # 数据加载：读取 CSV
│   ├── preprocessor.py           # 数据预处理：清洗、转换
│   ├── analyzer.py               # 分析引擎：计算各种指标
│   ├── visualizer.py             # 可视化：生成图表
│   ├── report_generator.py       # 报告生成：输出 Markdown
│   └── holiday_helper.py         # 节假日助手：处理调休
│
├── 📁 data/                      # 数据层
│   └── sample_timesheet.csv      # 示例数据
│
├── 📁 output/                    # 输出层
│   └── (生成的报告和图表)
│
├── app.py                        # Streamlit 前端入口
├── main.py                       # 命令行入口
├── requirements.txt              # 依赖包列表
└── README.md                     # 本文档
```

#### `__init__.py` 是什么？
这是 Python 的"包标识文件"。有了它，Python 才能识别文件夹为一个可导入的包。
```python
# 没有 __init__.py
from config.employees import xxx  # ❌ 报错

# 有 __init__.py
from config.employees import xxx  # ✅ 正常
```

---

### 第四步：运行项目

#### 4.1 安装依赖
```bash
# 打开 VS Code 终端：Ctrl + `（反引号）
pip install -r requirements.txt
```

#### 4.2 命令行模式
```bash
python main.py --input data/sample_timesheet.csv
```

#### 4.3 Streamlit 网页模式
```bash
streamlit run app.py
# 浏览器自动打开 http://localhost:8501
```

---

## 🔧 配置说明

### 员工配置 (config/employees.yaml)

```yaml
employees:
  - name_cn: "胡若玫"           # 中文名
    name_en: "Iris Hu"          # 英文名（与 Notion 一致）
    type: "全职"                # 类型：全职/兼职/按需
    standard_hours: 40          # 周标准工时
    department: "数据运营"       # 部门
```

**如何修改：** 直接编辑 `config/employees.yaml` 文件

### 节假日配置 (config/holidays.yaml)

```yaml
# 2025年节假日
holidays:
  2025:
    # 放假日期
    - date: "2025-01-01"
      name: "元旦"
      type: "holiday"
    
    # 调休上班日期
    - date: "2025-01-26"
      name: "春节调休"
      type: "workday"  # 周日上班
```

---

## 🎨 Streamlit 入门

### 什么是 Streamlit？
一个用 **纯 Python** 快速构建数据应用的框架，不需要学习 HTML/CSS/JavaScript。

### 核心概念

```python
import streamlit as st

# 1. 标题和文字
st.title("我的应用")
st.write("Hello, World!")

# 2. 侧边栏
with st.sidebar:
    option = st.selectbox("选择：", ["A", "B", "C"])

# 3. 文件上传
file = st.file_uploader("上传 CSV", type="csv")

# 4. 按钮交互
if st.button("点击分析"):
    st.success("分析完成！")

# 5. 显示数据表格
st.dataframe(df)

# 6. 显示图表
st.pyplot(fig)  # Matplotlib 图表
```

### Streamlit 的"魔法"
每次你与界面交互（点击按钮、上传文件），**整个脚本会从头到尾重新运行**。
这就是为什么要用 `st.cache_data` 缓存计算结果。

---

## 📊 边缘情况处理

### 1. 中国法定节假日

**问题：** 春节、国庆等长假 + 调休，导致：
- 某周可能只工作 2-3 天
- 周六/周日可能是调休工作日

**解决方案：** `holiday_helper.py`
```python
# 计算某周的实际标准工时
actual_standard = calculate_week_standard_hours(
    year=2025, 
    week_num=40,
    base_daily_hours=8
)
# 返回：如果这周有2天假期，返回 24h 而非 40h
```

### 2. 员工请假

**配置方式：** 在 `employees.yaml` 中添加
```yaml
employees:
  - name_cn: "魏超"
    leaves:
      - start: "2025-09-25"
        end: "2025-09-26"
        type: "年假"
```

### 3. 周边界判断

**问题：** 周六上班时，"本周"和"下周"的判断出错

**解决方案：** 使用 ISO 周数 + 节假日配置
```python
from datetime import date
# ISO 标准：周一是每周第一天
week_num = date(2025, 9, 27).isocalendar()[1]  # 返回周数
```

---

## 🚀 下一步学习

1. **Git 版本控制**：学习 `git init`, `git add`, `git commit`
2. **虚拟环境**：使用 `conda` 或 `venv` 隔离项目依赖
3. **单元测试**：为每个模块编写测试用例
4. **日志记录**：用 `logging` 替代 `print`

---

## ❓ 常见问题

### Q1: 为什么 `from src.analyzer import ...` 报错？
确保在项目根目录运行命令，或者设置 PYTHONPATH：
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/timesheet_analyzer"
```

### Q2: Streamlit 页面一直刷新？
使用 `@st.cache_data` 装饰器缓存数据处理函数。

### Q3: 中文乱码？
确保 CSV 文件是 UTF-8 编码，读取时指定 `encoding='utf-8-sig'`。

---

*文档生成时间：2025-01-23*

"""
团队工时分析系统 - Streamlit 前端

运行方式：
    streamlit run app.py
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import altair as alt
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import io
import json
import os

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.data_loader import load_timesheet, validate_data
from src.preprocessor import preprocess_data, filter_by_period
from src.analyzer import TimesheetAnalyzer
from src.visualizer import create_visualizations, create_single_chart
from src.report_generator import generate_markdown_report
from config import get_employees_config, add_employee_leave

# ============================================
# Altair 主题（MIH 品牌规范 · 数据可视化色板）
# 单色主导原则：B 端图表默认以蓝系为主，粉色仅做单点强调
# ============================================
MIH_CHART_PALETTE = [
    '#2F68B2',  # 品牌蓝（主系列）
    '#1A3A6E',  # 墨蓝
    '#5F8BC4',  # 中蓝
    '#62B4DD',  # 亮蓝
    '#B92957',  # 品牌粉（限做强调，谨慎使用）
    '#D97706',  # 橙
    '#1B7F4D',  # 绿
    '#7B5EA7',  # 紫
    '#C0392B',  # 红
    '#8C8C8C',  # 灰
]
# 兼容旧引用
CHART_COLORS = MIH_CHART_PALETTE

def _mih_theme():
    return {
        'config': {
            'background': 'transparent',
            'font': 'Inter, "Microsoft YaHei", -apple-system, sans-serif',
            'title': {'color': '#1F2933', 'fontSize': 14, 'fontWeight': 600, 'anchor': 'start'},
            'axis': {
                'labelColor': '#5C5C5C', 'titleColor': '#404040',
                'gridColor': '#F0F0F0', 'domainColor': '#D9D9D9',
                'tickColor': '#D9D9D9',
                'labelFontSize': 11, 'titleFontSize': 12,
                'labelFont': 'Inter, "Microsoft YaHei", sans-serif',
                'titleFont': 'Inter, "Microsoft YaHei", sans-serif',
            },
            'legend': {
                'labelColor': '#5C5C5C', 'titleColor': '#404040',
                'labelFontSize': 11, 'titleFontSize': 12,
            },
            'range': {
                'category': MIH_CHART_PALETTE,
                'ramp': ['#E9F1FA', '#CBE6F4', '#9DC8E8', '#6FA9D8', '#5F8BC4', '#2F68B2', '#0F348D'],
                'heatmap': ['#E9F1FA', '#CBE6F4', '#9DC8E8', '#6FA9D8', '#5F8BC4', '#2F68B2', '#0F348D'],
            },
            'view': {'stroke': 'transparent'},
        }
    }

alt.themes.register('mih', _mih_theme)
alt.themes.enable('mih')

# 尝试导入 AI 分析模块
try:
    from src.ai_analyzer import is_ai_available, get_ai_analyzer
    AI_MODULE_AVAILABLE = True
except ImportError:
    AI_MODULE_AVAILABLE = False

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================
# 页面配置
# ============================================
st.set_page_config(
    page_title="团队工时分析系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# 自定义样式（MIH 品牌规范 · 美年健康研究院）
# Token 来源: ~/.claude/skills/mih_brand_guidelines/assets/design_tokens.css
# 设计哲学: 数据为主角 · 单色主导（蓝+白+灰 ≥70%）· 节制即权威
# ============================================
st.markdown("""
<style>
    /* ── Web fonts: Inter (英文/数字) + IBM Plex Mono (等宽数字) ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    /* ── MIH design tokens · Light ── */
    :root {
        /* Brand */
        --mih-primary: #2F68B2;
        --mih-primary-hover: #1F4F8F;
        --mih-primary-active: #0F348D;
        --mih-primary-light: #CBE6F4;
        --mih-ink: #1A3A6E;
        /* Surface / text / border */
        --mih-bg: #FFFFFF;
        --mih-bg-subtle: #FAFAFA;
        --mih-surface: #FFFFFF;
        --mih-surface-hover: #F2F2F2;
        --mih-text-primary: #1F2933;
        --mih-text-secondary: #404040;
        --mih-text-tertiary: #5C5C5C;
        --mih-text-muted: #8C8C8C;
        --mih-border: #D9D9D9;
        --mih-border-soft: #F0F0F0;
        --mih-divider: #F2F2F2;
        /* Semantic（仅用于状态指示，不当装饰） */
        --mih-success: #1B7F4D;
        --mih-warning: #D97706;
        --mih-danger: #C0392B;
        /* Shadows（深蓝调，不用纯黑） */
        --mih-shadow-1: 0 1px 2px rgba(15, 52, 141, 0.06);
        --mih-shadow-2: 0 2px 8px rgba(15, 52, 141, 0.08);
        --mih-shadow-focus: 0 0 0 3px rgba(47, 104, 178, 0.2);
        /* Aliases used by existing markup */
        --card-bg: var(--mih-surface);
        --card-border: var(--mih-border-soft);
        --text-primary: var(--mih-text-primary);
        --text-secondary: var(--mih-text-tertiary);
        --bg-subtle: var(--mih-bg-subtle);
        --bg-sidebar: var(--mih-bg-subtle);
        --tab-list-bg: var(--mih-bg-subtle);
        --tab-active-bg: var(--mih-surface);
        --chart-header-border: var(--mih-divider);
        --chart-header-color: var(--mih-text-secondary);
        --sidebar-text: var(--mih-text-primary);
    }

    /* ── MIH design tokens · Dark ── */
    @media (prefers-color-scheme: dark) {
        :root {
            --mih-primary: #62B4DD;
            --mih-primary-hover: #7AC4E8;
            --mih-primary-active: #2F68B2;
            --mih-primary-light: rgba(98, 180, 221, 0.15);
            --mih-bg: #0F1419;
            --mih-bg-subtle: #1F2933;
            --mih-surface: #1F2933;
            --mih-surface-hover: #2D3748;
            --mih-text-primary: #F5F5F5;
            --mih-text-secondary: #D1D5DB;
            --mih-text-tertiary: #9CA3AF;
            --mih-text-muted: #6B7280;
            --mih-border: #374151;
            --mih-border-soft: #2D3748;
            --mih-divider: #2D3748;
            --mih-shadow-1: 0 1px 2px rgba(0, 0, 0, 0.4);
            --mih-shadow-2: 0 2px 8px rgba(0, 0, 0, 0.5);
        }
    }
    [data-theme="dark"] {
        --mih-primary: #62B4DD;
        --mih-primary-hover: #7AC4E8;
        --mih-primary-active: #2F68B2;
        --mih-primary-light: rgba(98, 180, 221, 0.15);
        --mih-bg: #0F1419;
        --mih-bg-subtle: #1F2933;
        --mih-surface: #1F2933;
        --mih-surface-hover: #2D3748;
        --mih-text-primary: #F5F5F5;
        --mih-text-secondary: #D1D5DB;
        --mih-text-tertiary: #9CA3AF;
        --mih-text-muted: #6B7280;
        --mih-border: #374151;
        --mih-border-soft: #2D3748;
        --mih-divider: #2D3748;
        --mih-shadow-1: 0 1px 2px rgba(0, 0, 0, 0.4);
        --mih-shadow-2: 0 2px 8px rgba(0, 0, 0, 0.5);
    }

    /* Dark mode: app/sidebar surfaces */
    @media (prefers-color-scheme: dark) {
        [data-testid="stAppViewContainer"],
        .main .block-container,
        [data-testid="stMainBlockContainer"] { background-color: var(--mih-bg) !important; color: var(--mih-text-primary) !important; }
        [data-testid="stHeader"] { background-color: var(--mih-bg) !important; }
        [data-testid="stSidebar"] > div:first-child { background-color: var(--mih-bg-subtle) !important; }
        [data-baseweb="select"] > div,
        [data-baseweb="select"] span,
        [data-baseweb="select"] input,
        [data-testid="stDateInput"] input { background-color: var(--mih-surface) !important; color: var(--mih-text-primary) !important; }
        [data-baseweb="select"] svg { fill: var(--mih-text-tertiary) !important; }
        [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"], [role="option"] { background-color: var(--mih-surface) !important; color: var(--mih-text-primary) !important; }
        [role="option"]:hover { background-color: var(--mih-surface-hover) !important; }
        [data-testid="stAlert"] { background-color: var(--mih-surface) !important; color: var(--mih-text-primary) !important; }
        [data-testid="stDataFrame"] { background-color: var(--mih-surface) !important; }
    }
    [data-theme="dark"] [data-testid="stAppViewContainer"],
    [data-theme="dark"] .main .block-container,
    [data-theme="dark"] [data-testid="stMainBlockContainer"] { background-color: var(--mih-bg) !important; color: var(--mih-text-primary) !important; }
    [data-theme="dark"] [data-testid="stHeader"] { background-color: var(--mih-bg) !important; }
    [data-theme="dark"] [data-testid="stSidebar"] > div:first-child { background-color: var(--mih-bg-subtle) !important; }

    /* ── Global typography ── */
    html, body, [class*="css"] {
        font-family: "Inter", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", -apple-system, BlinkMacSystemFont, sans-serif;
        font-feature-settings: "cv11", "ss01";
    }

    /* ── Hero section（极简版：去掉所有 gradient，仅留细底边作为品牌横线） ── */
    .hero-section {
        background: var(--mih-surface);
        border: 1px solid var(--mih-border-soft);
        border-radius: 8px;
        padding: 1.75rem 2rem 1.5rem;
        margin-bottom: 1.75rem;
        position: relative;
        overflow: hidden;
    }
    .hero-section::after {
        content: '';
        position: absolute;
        left: 0; right: 0; bottom: 0;
        height: 3px;
        background: var(--mih-primary);
    }
    .main-eyebrow {
        font-size: 0.7rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--mih-primary);
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .main-header {
        font-family: "Inter", "Microsoft YaHei", sans-serif;
        font-size: 1.875rem;
        font-weight: 700;
        color: var(--mih-text-primary);
        margin-bottom: 0.4rem;
        letter-spacing: -0.01em;
        line-height: 1.25;
    }
    .main-subtitle {
        color: var(--mih-text-tertiary);
        font-size: 0.875rem;
        margin-bottom: 0;
        line-height: 1.5;
    }

    /* ── Metric cards（统一蓝色顶条，不靠颜色区分 KPI） ── */
    [data-testid="stMetric"] {
        background: var(--mih-surface);
        border: 1px solid var(--mih-border-soft);
        border-top: 2px solid var(--mih-primary);
        border-radius: 4px;
        padding: 1rem 1.25rem;
        box-shadow: var(--mih-shadow-1);
        transition: box-shadow 200ms cubic-bezier(0.4, 0, 0.2, 1);
    }
    [data-testid="stMetric"]:hover {
        box-shadow: var(--mih-shadow-2);
    }
    [data-testid="stMetricLabel"] {
        color: var(--mih-text-tertiary);
        font-size: 0.8125rem;
        font-weight: 500;
        letter-spacing: 0.01em;
    }
    [data-testid="stMetricValue"] {
        font-family: "IBM Plex Mono", "SF Mono", "Roboto Mono", Consolas, monospace;
        color: var(--mih-text-primary);
        font-weight: 600;
        letter-spacing: -0.01em;
    }

    /* ── Tabs（克制：active 用细底边而非整块背景色） ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: transparent;
        border-bottom: 1px solid var(--mih-border-soft);
        border-radius: 0;
        padding: 0;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 0;
        padding: 10px 18px;
        font-weight: 500;
        font-size: 0.875rem;
        color: var(--mih-text-tertiary);
        border-bottom: 2px solid transparent;
        margin-bottom: -1px;
        transition: color 150ms cubic-bezier(0.4, 0, 0.2, 1), border-color 150ms cubic-bezier(0.4, 0, 0.2, 1);
    }
    .stTabs [aria-selected="true"] {
        color: var(--mih-primary);
        background: transparent;
        box-shadow: none;
        border-bottom: 2px solid var(--mih-primary);
    }
    .stTabs [aria-selected="false"]:hover {
        color: var(--mih-text-secondary);
        background: transparent;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: var(--mih-bg-subtle);
        border-right: 1px solid var(--mih-border-soft);
    }
    [data-testid="stSidebar"] * {
        color: var(--mih-text-primary) !important;
    }
    [data-testid="stSidebar"] .stRadio > label {
        font-weight: 500;
    }
    /* Sidebar step headers — 细蓝竖条，无渐变 */
    [data-testid="stSidebar"] .stSubheader {
        padding: 0.5rem 0 0.5rem 0.75rem;
        border-left: 2px solid var(--mih-primary);
        margin: 1.25rem 0 0.5rem 0;
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--mih-text-primary) !important;
    }

    /* ── DataFrames ── */
    [data-testid="stDataFrame"] {
        border-radius: 4px;
        overflow: hidden;
        border: 1px solid var(--mih-border-soft);
    }

    /* ── Buttons（实心蓝，无 gradient） ── */
    .stButton > button[kind="primary"] {
        background: var(--mih-primary);
        border: 1px solid var(--mih-primary);
        border-radius: 4px;
        color: #FFFFFF;
        font-weight: 500;
        font-size: 0.875rem;
        padding: 0.5rem 1.25rem;
        transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1);
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--mih-primary-hover);
        border-color: var(--mih-primary-hover);
        box-shadow: none;
        transform: none;
    }
    .stButton > button[kind="primary"]:active {
        background: var(--mih-primary-active);
    }
    .stButton > button[kind="secondary"] {
        background: var(--mih-surface);
        border: 1px solid var(--mih-border);
        border-radius: 4px;
        color: var(--mih-text-secondary);
        font-weight: 500;
        font-size: 0.875rem;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: var(--mih-primary);
        color: var(--mih-primary);
    }
    .stButton > button:focus-visible,
    .stDownloadButton > button:focus-visible {
        box-shadow: var(--mih-shadow-focus);
        outline: none;
    }

    /* ── Expander ── */
    .streamlit-expanderHeader {
        font-weight: 500;
        color: var(--mih-text-primary);
    }

    /* ── Horizontal block spacing ── */
    [data-testid="stHorizontalBlock"] {
        gap: 1rem;
    }

    /* ── Status colors（与品牌 semantic token 一致） ── */
    .status-normal  { color: var(--mih-success); }
    .status-warning { color: var(--mih-danger);  }
    .status-low     { color: var(--mih-warning); }

    /* ── Alert styling ── */
    [data-testid="stAlert"] {
        border-radius: 4px;
        border: 1px solid var(--mih-border-soft);
    }

    /* ── Chart card ── */
    .chart-card {
        background: var(--mih-surface);
        border: 1px solid var(--mih-border-soft);
        border-radius: 4px;
        overflow: hidden;
        box-shadow: none;
        margin-bottom: 1rem;
    }
    .chart-card-header {
        padding: 0.75rem 1.25rem;
        border-bottom: 1px solid var(--mih-divider);
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--mih-text-secondary);
        display: flex;
        align-items: center;
        gap: 0.5rem;
        letter-spacing: 0.005em;
    }
    .chart-card-body {
        padding: 0.5rem;
    }

    /* Fallback for un-wrapped Altair charts */
    [data-testid="stVegaLiteChart"] {
        background: var(--mih-surface);
        border: 1px solid var(--mih-border-soft);
        border-radius: 4px;
        padding: 0.75rem;
        box-shadow: none;
    }

    /* ── Welcome step cards ── */
    .welcome-step {
        text-align: center;
        padding: 1.75rem 1rem;
        background: var(--mih-surface);
        border: 1px solid var(--mih-border-soft);
        border-radius: 4px;
        transition: border-color 150ms cubic-bezier(0.4, 0, 0.2, 1), box-shadow 150ms cubic-bezier(0.4, 0, 0.2, 1);
    }
    .welcome-step:hover {
        border-color: var(--mih-primary);
        box-shadow: var(--mih-shadow-1);
    }
    .welcome-step-icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
        color: var(--mih-primary);
    }
    .welcome-step-title {
        font-weight: 600;
        font-size: 0.9375rem;
        color: var(--mih-text-primary);
        margin-bottom: 0.25rem;
    }
    .welcome-step-desc {
        color: var(--mih-text-tertiary);
        font-size: 0.8125rem;
        line-height: 1.5;
    }

    /* ── Download card ── */
    .download-card {
        background: var(--mih-surface);
        border: 1px solid var(--mih-border-soft);
        border-radius: 4px;
        padding: 1.25rem;
        text-align: center;
        margin-bottom: 0.75rem;
    }
    .download-card-icon {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
        color: var(--mih-primary);
    }
    .download-card-title {
        font-weight: 600;
        font-size: 0.9375rem;
        color: var(--mih-text-primary);
        margin-bottom: 0.25rem;
    }
    .download-card-desc {
        color: var(--mih-text-tertiary);
        font-size: 0.8125rem;
        margin-bottom: 0.875rem;
        line-height: 1.5;
    }

    /* ── Footer ── */
    .footer-text {
        color: var(--mih-text-muted);
        font-size: 0.75rem;
        text-align: center;
        padding: 1rem 0;
        letter-spacing: 0.01em;
    }

    /* Number-like content in dataframes uses Plex Mono */
    [data-testid="stDataFrame"] [role="gridcell"] {
        font-variant-numeric: tabular-nums;
    }

    /* ── Responsive: tablet (≤1024px) ── */
    @media (max-width: 1024px) {
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
            gap: 0.75rem;
        }
        [data-testid="stHorizontalBlock"] > div {
            flex: 1 1 100%;
            min-width: 0;
        }
        .hero-section { padding: 1.5rem 1.5rem; }
    }

    /* ── Responsive: mobile (≤768px) ── */
    @media (max-width: 768px) {
        .hero-section { padding: 1.25rem 1rem; }
        .main-header  { font-size: 1.375rem; }
        .main-subtitle { font-size: 0.8125rem; }
        [data-testid="stMetric"] { padding: 0.75rem 0.9rem; }
        [data-testid="stMetricValue"] { font-size: 1.25rem; }
        [data-testid="stMetricLabel"] { font-size: 0.75rem; }
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto;
            overflow-y: hidden;
            flex-wrap: nowrap;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: thin;
        }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { height: 4px; }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 12px;
            font-size: 0.8125rem;
            white-space: nowrap;
            flex-shrink: 0;
        }
        [data-testid="stDataFrame"],
        [data-testid="stVegaLiteChart"] { max-width: 100%; overflow-x: auto; }
        [data-testid="stVegaLiteChart"] { padding: 0.5rem; }
        .welcome-step  { padding: 1.25rem 0.75rem; }
        .download-card { padding: 1rem; }
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# Session State 初始化
# ============================================
if 'analysis_started' not in st.session_state:
    st.session_state.analysis_started = False
if 'loaded_data' not in st.session_state:
    st.session_state.loaded_data = None
if 'loaded_meta' not in st.session_state:
    st.session_state.loaded_meta = None
if 'analysis_params' not in st.session_state:
    st.session_state.analysis_params = {}

# ============================================
# 侧边栏：引导式操作流程
# ============================================
with st.sidebar:
    st.markdown("### ⚙️ 分析设置")

    uploaded_file = None
    notion_token = None
    selected_report = None
    has_valid_source = False

    # ── 第一步：选择数据来源 ──
    st.subheader("① 选择数据来源")
    data_source = st.radio(
        "选择数据来源",
        ["预生成报告（推荐）", "Notion 直连", "CSV 上传"],
        index=1,
        help="预生成报告：读取定时生成的快照（秒开）；Notion 直连：实时拉取最新数据；CSV 上传：手动上传文件"
    )

    if data_source == "Notion 直连":
        try:
            notion_token = st.secrets.get("NOTION_API_TOKEN", "") if hasattr(st, 'secrets') else ""
        except Exception:
            notion_token = ""
        if not notion_token:
            notion_token = os.getenv("NOTION_API_TOKEN", "")
        has_valid_source = bool(notion_token)
        if not notion_token:
            st.warning("未配置 NOTION_API_TOKEN")
    elif data_source == "预生成报告（推荐）":
        report_dir = Path("reports")
        csv_files = sorted(report_dir.glob("timesheet_*.csv"), reverse=True) if report_dir.exists() else []
        if csv_files:
            selected_report = st.selectbox(
                "选择周报数据",
                csv_files,
                format_func=lambda x: x.stem.replace("timesheet_", "周报 ")
            )
            has_valid_source = True
        else:
            st.warning("暂无预生成报告，请切换到其他数据源")
    else:
        uploaded_file = st.file_uploader(
            "上传工时 CSV 文件",
            type=['csv'],
            help="从 Notion 导出的工时数据 CSV 文件"
        )
        has_valid_source = uploaded_file is not None

    # ── 第二步：选择分析周 ──
    st.subheader("② 选择分析周")
    reference_date = st.date_input(
        "选择该周内的任意一天",
        value=date.today(),
        help="系统会自动计算该日期所在的完整周（周一~周日）"
    )
    # 计算并展示周范围
    _monday = reference_date - timedelta(days=reference_date.weekday())
    _sunday = _monday + timedelta(days=6)
    st.info(f"📅 将分析: {_monday.strftime('%m/%d')}(周一) ~ {_sunday.strftime('%m/%d')}(周日)")

    # ── 第三步：可选设置 ──
    st.subheader("③ 可选设置")
    consider_holidays = st.checkbox("考虑节假日", value=True, help="根据法定节假日调整标准工时")
    consider_leaves = st.checkbox("考虑请假", value=True, help="根据员工请假记录调整标准工时")

    with st.expander("🤖 AI 分析设置"):
        if not AI_MODULE_AVAILABLE:
            st.warning("AI 模块未安装，请运行: `pip install anthropic`")
            api_key = None
            ai_enabled = False
        else:
            try:
                api_key = st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st, 'secrets') else ""
            except Exception:
                api_key = ""
            if not api_key:
                api_key = os.getenv("ANTHROPIC_API_KEY")

            if api_key:
                st.success("已从环境变量读取 API Key")
            else:
                st.info("未检测到 ANTHROPIC_API_KEY，请手动输入")

            manual_key = st.text_input(
                "Anthropic API Key",
                type="password",
                help="输入后将覆盖环境变量中的 API Key"
            )
            if manual_key:
                api_key = manual_key

            ai_enabled = is_ai_available(api_key)

    with st.expander("👥 员工配置预览"):
        config = get_employees_config()
        employees = config.get('employees', [])

        emp_df = pd.DataFrame([
            {
                '姓名': e.get('name_cn', ''),
                '英文名': e.get('name_en', ''),
                '类型': e.get('type', ''),
                '职位': e.get('position', e.get('description', '')),
                '标准工时': e.get('standard_hours', 'N/A')
            }
            for e in employees
        ])
        st.dataframe(emp_df, use_container_width=True, hide_index=True)
        st.caption("💡 修改员工配置请编辑 `config/employees.yaml`")

    # ── 开始分析按钮 ──
    st.divider()
    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        # 校验必填项
        if data_source == "Notion 直连" and not notion_token:
            st.error("请先配置 NOTION_API_TOKEN（Streamlit Secrets 或环境变量）")
        elif data_source == "CSV 上传" and uploaded_file is None:
            st.error("请先上传 CSV 文件")
        elif data_source == "预生成报告（推荐）" and selected_report is None:
            st.error("暂无可用的预生成报告")
        else:
            st.session_state.analysis_started = True
            st.session_state.analysis_params = {
                'data_source': data_source,
                'reference_date': reference_date,
                'consider_holidays': consider_holidays,
                'consider_leaves': consider_leaves,
                'notion_token': notion_token,
                'selected_report': str(selected_report) if selected_report else None,
                'uploaded_file_content': uploaded_file.getvalue() if uploaded_file else None,
            }
            # 实际加载数据放到主内容区，这里只保存参数
            st.session_state.loaded_data = None
            st.session_state.loaded_meta = None
            st.session_state.pop('ai_insights', None)  # 强制重跑 AI 分析
            st.rerun()

# ============================================
# 缓存函数定义
# ============================================
@st.cache_data
def load_and_process(file_content: bytes, ref_date: date):
    """缓存数据加载和预处理（CSV 上传用）"""
    df_raw = load_timesheet(io.BytesIO(file_content))
    df, meta = preprocess_data(df_raw, ref_date)
    return df, meta

@st.cache_data(ttl=300)
def fetch_and_process_from_notion(_token: str, ref_date: date):
    """从 Notion 拉取并预处理数据（缓存 5 分钟）"""
    from src.notion_connector import NotionConnector
    connector = NotionConnector(_token)
    monday = ref_date - timedelta(days=ref_date.weekday())
    next_sunday = monday + timedelta(days=13)
    df_raw = connector.fetch_timesheet(
        monday.strftime("%Y-%m-%d"),
        next_sunday.strftime("%Y-%m-%d")
    )
    df, meta = preprocess_data(df_raw, ref_date)
    return df, meta

# ============================================
# 主内容区
# ============================================
st.markdown('''
<div class="hero-section">
    <div class="main-eyebrow">美年健康研究院 · MIH</div>
    <h1 class="main-header">团队工时分析系统</h1>
    <p class="main-subtitle">追踪工时数据 · 解析工作负荷 · 洞察项目投入</p>
</div>
''', unsafe_allow_html=True)

# 门控：未开始分析时显示欢迎页
if not st.session_state.analysis_started:
    st.markdown("#### 三步开始分析")

    cols = st.columns(3)
    steps = [
        ("1️⃣", "选择数据源", "Notion 直连、预生成报告或 CSV 上传"),
        ("2️⃣", "选择分析周", "选任意一天，自动计算周一~周日"),
        ("3️⃣", "开始分析", "一键生成完整的工时分析报告"),
    ]
    for col, (icon, title, desc) in zip(cols, steps):
        with col:
            st.markdown(f'''
            <div class="welcome-step">
                <div class="welcome-step-icon">{icon}</div>
                <div class="welcome-step-title">{title}</div>
                <div class="welcome-step-desc">{desc}</div>
            </div>
            ''', unsafe_allow_html=True)

    st.markdown("")

    with st.expander("📖 数据来源说明"):
        st.markdown("""
        - **预生成报告**：读取 GitHub Actions 定时生成的快照，秒开
        - **Notion 直连**：实时拉取最新数据（需配置 API Token）
        - **CSV 上传**：手动上传从 Notion 导出的 CSV 文件
        """)

    st.info("👈 请在左侧配置数据来源和分析周，然后点击「开始分析」")

    st.stop()

# 设置变更检测
_current_params = {
    'data_source': data_source,
    'reference_date': reference_date,
    'consider_holidays': consider_holidays,
    'consider_leaves': consider_leaves,
}
_saved_params = st.session_state.analysis_params
if (_current_params['data_source'] != _saved_params.get('data_source')
    or _current_params['reference_date'] != _saved_params.get('reference_date')
    or _current_params['consider_holidays'] != _saved_params.get('consider_holidays')
    or _current_params['consider_leaves'] != _saved_params.get('consider_leaves')):
    st.warning("⚠️ 设置已变更，当前显示的是上次分析的结果。请点击侧边栏「开始分析」刷新。")

# 数据加载（仅在 loaded_data 为空时执行）
if st.session_state.loaded_data is None:
    params = st.session_state.analysis_params
    try:
        if params['data_source'] == "Notion 直连":
            with st.spinner("正在从 Notion 获取数据..."):
                df, meta = fetch_and_process_from_notion(params['notion_token'], params['reference_date'])
        elif params['data_source'] == "预生成报告（推荐）":
            with st.spinner("正在加载预生成报告..."):
                df_raw = load_timesheet(params['selected_report'])
                df, meta = preprocess_data(df_raw, params['reference_date'])
        else:
            with st.spinner("正在加载数据..."):
                df, meta = load_and_process(params['uploaded_file_content'], params['reference_date'])
            validation = validate_data(pd.read_csv(io.BytesIO(params['uploaded_file_content']), encoding='utf-8-sig'))
            if not validation['valid']:
                st.warning("⚠️ 数据质量问题：" + "；".join(validation['issues']))

        st.session_state.loaded_data = df
        st.session_state.loaded_meta = meta
        st.session_state['data_fetched_at'] = datetime.now().isoformat(timespec="seconds")

    except Exception as e:
        st.error(f"❌ 数据加载失败: {e}")
        st.session_state.analysis_started = False
        st.stop()

df = st.session_state.loaded_data
meta = st.session_state.loaded_meta
reference_date = st.session_state.analysis_params['reference_date']
consider_holidays = st.session_state.analysis_params['consider_holidays']
consider_leaves = st.session_state.analysis_params['consider_leaves']

# ============================================
# 分析
# ============================================
analyzer = TimesheetAnalyzer(df)

# AI 深度分析自动运行 (与 auto_weekly_report.py 行为一致;失败不阻断主流程)
if ai_enabled and api_key and 'ai_insights' not in st.session_state:
    with st.spinner("🤖 正在调用 Claude API 进行深度分析 (约 30-60 秒)..."):
        try:
            _ai_result = analyzer.generate_ai_insights("本周", api_key)
            if _ai_result:
                st.session_state['ai_insights'] = _ai_result
                st.session_state['ai_insights_ts'] = datetime.now().isoformat(timespec="seconds")
        except Exception as _e:
            st.warning(f"AI 深度分析失败 (不影响其他功能): {_e}")

# 过滤数据
df_current = filter_by_period(df, "本周")
df_next = filter_by_period(df, "下周")

# 获取分析结果
current_summary = analyzer.get_summary("本周")
current_members = analyzer.analyze_members("本周", consider_holidays, consider_leaves)
current_projects = analyzer.analyze_projects("本周")
insights = analyzer.generate_insights("本周")

next_summary = analyzer.get_summary("下周")
next_members = analyzer.analyze_members("下周")
next_projects = analyzer.analyze_projects("下周")

# ============================================
# 展示结果
# ============================================

# 总览指标
st.subheader("📈 本周概览")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="总工时",
        value=f"{current_summary['total_hours']} h",
        delta=None
    )

with col2:
    st.metric(
        label="工作天数",
        value=f"{current_summary['working_days']} 天"
    )

with col3:
    st.metric(
        label="项目数",
        value=f"{current_summary['project_count']} 个"
    )

with col4:
    st.metric(
        label="团队成员",
        value=f"{current_summary['member_count']} 人"
    )

if current_summary['date_range']:
    st.caption(f"📅 分析期间: {current_summary['date_range'][0]} 至 {current_summary['date_range'][1]}")

st.divider()

# 标签页
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "👥 人员分析",
    "📁 项目分析",
    "📊 图表中心",
    "📅 下周安排",
    "🤖 AI 深度分析",
    "📄 报告下载",
    "🏖️ 请假登记"
])

# ============================================
# Tab 1: 人员分析
# ============================================
with tab1:
    if current_members:
        # ① 核心指标
        col1, col2, col3, col4 = st.columns(4)

        normal = len([m for m in current_members if '正常' in m.status])
        overloaded = len([m for m in current_members if '超负荷' in m.status])
        underloaded = len([m for m in current_members if '偏低' in m.status])
        flexible = len([m for m in current_members if '按需' in m.status])

        with col1:
            st.metric("✅ 正常", f"{normal} 人")
        with col2:
            st.metric("⚠️ 超负荷", f"{overloaded} 人")
        with col3:
            st.metric("📉 偏低", f"{underloaded} 人")
        with col4:
            st.metric("🔄 按需", f"{flexible} 人")

        st.divider()

        # ② 全员工时表格
        member_df = pd.DataFrame([
            {
                '姓名': m.name,
                '类型': m.type,
                '总工时': f"{m.total_hours}h",
                '标准工时': f"{m.standard_hours}h" if m.standard_hours else "N/A",
                '达成率': m.achievement_rate if m.achievement_rate else 0,
                '日均': f"{m.daily_avg}h",
                '任务数': m.task_count,
                '状态': m.status
            }
            for m in current_members
        ])

        st.dataframe(
            member_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                '达成率': st.column_config.ProgressColumn(
                    "达成率",
                    help="工时达成百分比",
                    min_value=0,
                    max_value=150,
                    format="%d%%",
                ),
                '状态': st.column_config.TextColumn(width='medium')
            }
        )

        st.divider()

        # ③ 人员事项明细下钻
        if len(df_current) > 0:
            st.subheader("🔍 人员事项明细")

            member_names = [m.name for m in current_members]
            overloaded_names = [m.name for m in current_members if '超负荷' in m.status]
            default_idx = member_names.index(overloaded_names[0]) if overloaded_names else 0

            selected_member = st.selectbox(
                "选择成员查看明细",
                options=member_names,
                index=default_idx,
                key="member_drilldown"
            )

            m_data = df_current[df_current['成员_中文'] == selected_member]
            if len(m_data) > 0:
                proj_groups = m_data.groupby('项目名称_清理').agg(
                    工时=('工时 h', 'sum'),
                    任务数=('工时 h', 'count')
                ).sort_values('工时', ascending=False)

                detail_rows = []
                for proj_name, row in proj_groups.iterrows():
                    tasks_in_proj = m_data[m_data['项目名称_清理'] == proj_name]
                    task_list = []
                    for _, t in tasks_in_proj.sort_values('工时 h', ascending=False).iterrows():
                        desc = str(t.get('工作内容', '')).strip() or '（无描述）'
                        if len(desc) > 30:
                            desc = desc[:30] + "..."
                        task_list.append(f"{desc}({t['工时 h']}h)")
                    detail_rows.append({
                        '项目': str(proj_name)[:25] + ('...' if len(str(proj_name)) > 25 else ''),
                        '工时': f"{row['工时']:.1f}h",
                        '任务数': int(row['任务数']),
                        '具体事项': '；'.join(task_list)
                    })

                st.dataframe(
                    pd.DataFrame(detail_rows),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("该成员本周无工时记录")

        # ④ 人员洞察（只显示 warning/opportunity）
        people_insights = [i for i in insights if i['type'] in ('warning', 'opportunity')]
        if people_insights:
            st.divider()
            st.subheader("💡 人员洞察")
            for insight in people_insights:
                if insight['severity'] == 'high':
                    st.error(f"**{insight['title']}**\n\n{insight['content']}")
                elif insight['severity'] == 'medium':
                    st.warning(f"**{insight['title']}**\n\n{insight['content']}")
                else:
                    st.info(f"**{insight['title']}**\n\n{insight['content']}")
    else:
        st.info("本周暂无数据")

# ============================================
# Tab 2: 项目分析
# ============================================
with tab2:
    if current_projects:
        # ① 核心指标
        _total_h = current_summary['total_hours']
        _proj_cnt = current_summary['project_count']
        _avg_h = round(_total_h / _proj_cnt, 1) if _proj_cnt > 0 else 0
        _collab_cnt = len([p for p in current_projects if p.member_count > 1])

        pc1, pc2, pc3, pc4 = st.columns(4)
        with pc1:
            st.metric("总投入工时", f"{_total_h} h")
        with pc2:
            st.metric("活跃项目数", f"{_proj_cnt} 个")
        with pc3:
            st.metric("平均工时/项目", f"{_avg_h} h")
        with pc4:
            st.metric("多人协作项目", f"{_collab_cnt} 个")

        st.divider()

        # ② 项目工时排名表格
        project_df = pd.DataFrame([
            {
                '排名': i,
                '项目名称': p.name[:40] + ('...' if len(p.name) > 40 else ''),
                '投入工时': f"{p.total_hours}h",
                '占比': f"{p.percentage}%",
                '参与人数': p.member_count,
                '属性': p.attribute,
                '优先级': p.priority
            }
            for i, p in enumerate(current_projects[:15], 1)
        ])

        st.dataframe(
            project_df,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        # ③ 重点项目下钻（TOP 3）
        if len(df_current) > 0:
            st.subheader("🔍 重点项目明细（TOP 3）")

            for proj in current_projects[:3]:
                proj_data = df_current[df_current['项目名称_清理'] == proj.name]
                with st.expander(f"**{proj.name}** — {proj.total_hours}h（{proj.percentage}%）"):
                    if len(proj_data) > 0:
                        for member in proj_data['成员_中文'].unique():
                            member_data = proj_data[proj_data['成员_中文'] == member]
                            member_hours = member_data['工时 h'].sum()
                            st.markdown(f"**{member}**（{member_hours:.1f}h）：")
                            tasks = member_data.sort_values('工时 h', ascending=False)
                            for _, row in tasks.iterrows():
                                task_name = str(row.get('工作内容', '')).strip() or '（无描述）'
                                st.markdown(f"- {task_name}（{row['工时 h']}h）")
                    else:
                        st.info("无明细数据")

        # ④ 项目洞察（未立项分析 + risk/info insights）
        st.divider()
        st.subheader("💡 项目洞察")

        # 未立项/临时指派分析
        if len(df_current) > 0:
            adhoc_data = df_current[df_current['项目名称_清理'].str.contains('未立项|临时指派', na=False)]
            if len(adhoc_data) > 0:
                total_hours_all = df_current['工时 h'].sum()
                adhoc_hours = adhoc_data['工时 h'].sum()
                adhoc_pct = adhoc_hours / total_hours_all * 100 if total_hours_all > 0 else 0
                adhoc_members = adhoc_data['成员_中文'].unique()

                st.warning(
                    f"**⚠️ 未立项/临时指派工时**\n\n"
                    f"共 {adhoc_hours:.1f}h（占比 {adhoc_pct:.1f}%），涉及 {len(adhoc_members)} 人：{', '.join(adhoc_members)}"
                )

                with st.expander("查看未立项明细"):
                    adhoc_detail = []
                    for _, row in adhoc_data.sort_values('工时 h', ascending=False).iterrows():
                        task = str(row.get('工作内容', '')).strip() or '（无描述）'
                        if len(task) > 50:
                            task = task[:50] + "..."
                        adhoc_detail.append({
                            '日期': str(row.get('日期', ''))[:10],
                            '成员': row.get('成员_中文', ''),
                            '工作内容': task,
                            '工时': f"{row['工时 h']}h"
                        })
                    st.dataframe(
                        pd.DataFrame(adhoc_detail),
                        use_container_width=True,
                        hide_index=True
                    )

        # 项目相关 insights (risk / info)
        project_insights = [i for i in insights if i['type'] in ('risk', 'info')]
        for insight in project_insights:
            if insight['severity'] == 'high':
                st.error(f"**{insight['title']}**\n\n{insight['content']}")
            elif insight['severity'] == 'medium':
                st.warning(f"**{insight['title']}**\n\n{insight['content']}")
            else:
                st.info(f"**{insight['title']}**\n\n{insight['content']}")
    else:
        st.info("本周暂无项目数据")

# ============================================
# Tab 3: 图表中心（Altair）
# ============================================
with tab3:
    if len(df_current) > 0:
        # --- Row 1 ---
        r1c1, r1c2 = st.columns(2)

        with r1c1:
            st.markdown('<div class="chart-card"><div class="chart-card-header">👥 人员工时柱状图</div><div class="chart-card-body">', unsafe_allow_html=True)
            bar_data = pd.DataFrame([
                {'成员': m.name, '实际工时': m.total_hours,
                 '标准工时': m.standard_hours if m.standard_hours else 0,
                 '达成率': f"{m.achievement_rate}%" if m.achievement_rate else "N/A"}
                for m in current_members
            ])
            bar_melted = bar_data.melt(
                id_vars=['成员', '达成率'], value_vars=['实际工时', '标准工时'],
                var_name='类型', value_name='工时'
            )
            chart_bar = alt.Chart(bar_melted).mark_bar().encode(
                y=alt.Y('成员:N', sort='-x', title=None),
                x=alt.X('工时:Q', title='工时 (h)'),
                color=alt.Color('类型:N', scale=alt.Scale(range=['#2F68B2', '#D9D9D9'])),
                tooltip=['成员', '类型', '工时', '达成率']
            ).properties(height=max(len(current_members) * 35, 200))
            st.altair_chart(chart_bar, use_container_width=True)
            st.markdown('</div></div>', unsafe_allow_html=True)

        with r1c2:
            st.markdown('<div class="chart-card"><div class="chart-card-header">🍩 项目工时分布</div><div class="chart-card-body">', unsafe_allow_html=True)
            top_n = 8
            donut_items = []
            other_hours = 0.0
            for idx, p in enumerate(current_projects):
                if idx < top_n:
                    donut_items.append({'项目': p.name[:20], '工时': p.total_hours})
                else:
                    other_hours += p.total_hours
            if other_hours > 0:
                donut_items.append({'项目': '其他', '工时': round(other_hours, 1)})
            donut_df = pd.DataFrame(donut_items)
            chart_donut = alt.Chart(donut_df).mark_arc(innerRadius=50).encode(
                theta=alt.Theta('工时:Q'),
                color=alt.Color('项目:N', sort=None),
                tooltip=['项目', '工时']
            ).properties(height=300)
            st.altair_chart(chart_donut, use_container_width=True)
            st.markdown('</div></div>', unsafe_allow_html=True)

        # --- Row 2 ---
        r2c1, r2c2 = st.columns(2)

        with r2c1:
            st.markdown('<div class="chart-card"><div class="chart-card-header">📏 工时达成率</div><div class="chart-card-body">', unsafe_allow_html=True)
            rate_data = pd.DataFrame([
                {'成员': m.name, '达成率': m.achievement_rate if m.achievement_rate else 0}
                for m in current_members if m.standard_hours and m.standard_hours > 0
            ])
            if len(rate_data) > 0:
                rate_data['状态'] = rate_data['达成率'].apply(
                    lambda x: '超负荷' if x > 120 else ('偏低' if x < 70 else '正常')
                )
                status_color = alt.Scale(
                    domain=['超负荷', '偏低', '正常'],
                    range=['#C0392B', '#D97706', '#1B7F4D']
                )
                bars = alt.Chart(rate_data).mark_bar().encode(
                    y=alt.Y('成员:N', sort='-x', title=None),
                    x=alt.X('达成率:Q', title='达成率 (%)'),
                    color=alt.Color('状态:N', scale=status_color, legend=None),
                    tooltip=['成员', alt.Tooltip('达成率:Q', format='.1f'), '状态']
                ).properties(height=max(len(rate_data) * 35, 200))

                rule_data = pd.DataFrame([
                    {'阈值': 70, '标签': '偏低线 70%'},
                    {'阈值': 100, '标签': '标准 100%'},
                    {'阈值': 120, '标签': '超负荷 120%'},
                ])
                rules = alt.Chart(rule_data).mark_rule(strokeDash=[4, 4]).encode(
                    x='阈值:Q',
                    color=alt.value('#8C8C8C'),
                    tooltip=['标签']
                )
                st.altair_chart(bars + rules, use_container_width=True)
            else:
                st.info("无达成率数据")
            st.markdown('</div></div>', unsafe_allow_html=True)

        with r2c2:
            st.markdown('<div class="chart-card"><div class="chart-card-header">🏷️ 项目属性分布</div><div class="chart-card-body">', unsafe_allow_html=True)
            attr_data = analyzer.analyze_by_attribute("本周")
            if attr_data:
                attr_df = pd.DataFrame([
                    {'属性': str(k) if pd.notna(k) else '未分类', '工时': round(v, 1)}
                    for k, v in sorted(attr_data.items(), key=lambda x: x[1], reverse=True)
                ])
                chart_attr = alt.Chart(attr_df).mark_bar().encode(
                    y=alt.Y('属性:N', sort='-x', title=None),
                    x=alt.X('工时:Q', title='工时 (h)'),
                    color=alt.value('#1A3A6E'),
                    tooltip=['属性', '工时']
                ).properties(height=max(len(attr_df) * 35, 150))
                st.altair_chart(chart_attr, use_container_width=True)
            else:
                st.info("无属性数据")
            st.markdown('</div></div>', unsafe_allow_html=True)

        # --- Row 3 ---
        r3c1, r3c2 = st.columns(2)

        with r3c1:
            st.markdown('<div class="chart-card"><div class="chart-card-header">📈 每日工时趋势</div><div class="chart-card-body">', unsafe_allow_html=True)
            trend = df_current.groupby('日期_date')['工时 h'].sum().reset_index()
            trend.columns = ['日期', '工时']
            trend = trend.sort_values('日期')

            area = alt.Chart(trend).mark_area(opacity=0.12, color='#2F68B2').encode(
                x=alt.X('日期:T', title=None),
                y=alt.Y('工时:Q', title='工时 (h)')
            )
            line = alt.Chart(trend).mark_line(point=True, color='#2F68B2').encode(
                x=alt.X('日期:T', title=None),
                y=alt.Y('工时:Q', title='工时 (h)'),
                tooltip=[alt.Tooltip('日期:T', format='%m-%d'), '工时']
            )
            st.altair_chart(area + line, use_container_width=True)
            st.markdown('</div></div>', unsafe_allow_html=True)

        with r3c2:
            st.markdown('<div class="chart-card"><div class="chart-card-header">🎯 优先级分布</div><div class="chart-card-body">', unsafe_allow_html=True)
            priority_data = analyzer.analyze_by_priority("本周")
            if priority_data:
                pri_df = pd.DataFrame([
                    {'优先级': str(k) if pd.notna(k) else '未设置', '工时': round(v, 1)}
                    for k, v in sorted(priority_data.items(), key=lambda x: x[1], reverse=True)
                ])
                chart_pri = alt.Chart(pri_df).mark_bar().encode(
                    y=alt.Y('优先级:N', sort='-x', title=None),
                    x=alt.X('工时:Q', title='工时 (h)'),
                    color=alt.value('#5F8BC4'),
                    tooltip=['优先级', '工时']
                ).properties(height=max(len(pri_df) * 35, 150))
                st.altair_chart(chart_pri, use_container_width=True)
            else:
                st.info("无优先级数据")
            st.markdown('</div></div>', unsafe_allow_html=True)

        # --- 底部全宽：热力图 ---
        st.divider()
        st.markdown('<div class="chart-card"><div class="chart-card-header">🔥 工作强度热力图</div><div class="chart-card-body">', unsafe_allow_html=True)
        heat_df = df_current.groupby(['成员_中文', '日期_date'])['工时 h'].sum().reset_index()
        heat_df.columns = ['成员', '日期', '工时']

        heat_rect = alt.Chart(heat_df).mark_rect(cornerRadius=3).encode(
            x=alt.X('日期:T', title=None, axis=alt.Axis(format='%m-%d')),
            y=alt.Y('成员:N', title=None),
            color=alt.Color('工时:Q', scale=alt.Scale(scheme='blues'), title='工时 (h)'),
            tooltip=['成员', alt.Tooltip('日期:T', format='%m-%d'), alt.Tooltip('工时:Q', format='.1f')]
        )
        _median = heat_df['工时'].median()
        heat_df['_text_color'] = heat_df['工时'].apply(lambda x: '高' if x > _median else '低')
        heat_text = alt.Chart(heat_df).mark_text(fontSize=11).encode(
            x=alt.X('日期:T'),
            y=alt.Y('成员:N'),
            text=alt.Text('工时:Q', format='.1f'),
            color=alt.Color('_text_color:N',
                            scale=alt.Scale(domain=['高', '低'], range=['white', '#1F2933']),
                            legend=None)
        )
        st.altair_chart(
            (heat_rect + heat_text).properties(height=max(heat_df['成员'].nunique() * 35, 200)),
            use_container_width=True
        )
        st.markdown('</div></div>', unsafe_allow_html=True)
    else:
        st.info("本周暂无数据，无法生成图表")

# ============================================
# Tab 4: 下周安排
# ============================================
with tab4:
    if next_summary['total_hours'] > 0:
        # 概览指标行
        nc1, nc2, nc3 = st.columns(3)
        with nc1:
            st.metric("预计总工时", f"{next_summary['total_hours']} h")
        with nc2:
            st.metric("参与人数", f"{next_summary.get('member_count', len(next_members))} 人")
        with nc3:
            st.metric("涉及项目", f"{next_summary.get('project_count', len(next_projects))} 个")

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="chart-card"><div class="chart-card-header">👥 人员工时安排</div><div class="chart-card-body">', unsafe_allow_html=True)
            if next_members:
                next_bar_data = pd.DataFrame([
                    {'成员': m.name, '预计工时': m.total_hours}
                    for m in next_members
                ])
                chart_next_member = alt.Chart(next_bar_data).mark_bar(cornerRadiusEnd=4).encode(
                    y=alt.Y('成员:N', sort='-x', title=None),
                    x=alt.X('预计工时:Q', title='工时 (h)'),
                    color=alt.value('#2F68B2'),
                    tooltip=['成员', '预计工时']
                ).properties(height=max(len(next_members) * 35, 150))
                st.altair_chart(chart_next_member, use_container_width=True)
            st.markdown('</div></div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="chart-card"><div class="chart-card-header">📁 项目工时安排</div><div class="chart-card-body">', unsafe_allow_html=True)
            if next_projects:
                next_proj_data = pd.DataFrame([
                    {'项目': p.name[:25], '预计工时': p.total_hours}
                    for p in next_projects[:8]
                ])
                chart_next_proj = alt.Chart(next_proj_data).mark_bar(cornerRadiusEnd=4).encode(
                    y=alt.Y('项目:N', sort='-x', title=None),
                    x=alt.X('预计工时:Q', title='工时 (h)'),
                    color=alt.value('#1A3A6E'),
                    tooltip=['项目', '预计工时']
                ).properties(height=max(len(next_projects[:8]) * 35, 150))
                st.altair_chart(chart_next_proj, use_container_width=True)
            st.markdown('</div></div>', unsafe_allow_html=True)
    else:
        st.info("暂无下周工时安排数据")

# ============================================
# Tab 5: AI 深度分析
# ============================================
with tab5:
    st.subheader("🤖 Claude AI 深度工时分析")

    if not AI_MODULE_AVAILABLE:
        st.warning(
            "AI 分析模块未安装。请运行以下命令安装依赖：\n\n"
            "```bash\npip install anthropic python-dotenv\n```"
        )
    elif not ai_enabled:
        st.warning(
            "AI 分析需要配置 Anthropic API Key。\n\n"
            "请在左侧边栏设置 API Key，或设置环境变量 `ANTHROPIC_API_KEY`。"
        )
    else:
        # 快速扫视（不需要 API 调用）
        st.markdown("### 15分钟快速扫视")
        st.caption("基于规则的快速分析，实时显示，无需 API 调用")

        quick_scan = analyzer.generate_quick_scan("本周")

        if quick_scan:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("#### 🚨 异常值")
                if quick_scan.anomalies:
                    for a in quick_scan.anomalies:
                        st.error(f"**{a.get('member', 'N/A')}**: {a.get('value', '')} - {a.get('concern', '')}")
                else:
                    st.success("未检测到异常")

            with col2:
                st.markdown("#### 🎯 核心项目状态")
                for p in quick_scan.core_projects:
                    if p.get('status') == '充足':
                        st.success(f"**{p.get('project', '')}**: {p.get('hours', 0)}h ({p.get('percentage', '')})")
                    else:
                        st.warning(f"**{p.get('project', '')}**: {p.get('hours', 0)}h ({p.get('percentage', '')})")

            with col3:
                st.markdown("#### ⚫ 黑洞时间")
                if quick_scan.black_holes:
                    for bh in quick_scan.black_holes:
                        st.warning(f"**{bh.get('category', '')}**: {bh.get('hours', 0)}h ({bh.get('percentage', '')})")
                else:
                    st.success("未检测到黑洞时间")

            if quick_scan.action_items:
                st.markdown("#### ✅ 立即行动项")
                for item in quick_scan.action_items:
                    st.info(f"- {item}")

        st.divider()

        # AI 深度分析
        st.markdown("### Claude AI 深度分析")
        st.caption("使用 Claude API 进行四维度十指标的深度分析")

        st.markdown("""
        **分析框架：**
        - **战略一致性**：战略 vs 琐事比例、重点项目投入度
        - **执行效率**：碎片化程度、会议占比
        - **团队健康**：负荷分布、异常填充
        - **财务合规**：资本化占比、跨部门支持
        """)

        ai_result = st.session_state.get('ai_insights')

        if ai_result:
            st.caption("✅ 分析结果已自动生成 (开始分析时随主流程一起跑)")
            # 执行摘要
            st.markdown("#### 📋 执行摘要")
            st.info(ai_result.executive_summary)

            # 四维度分析
            for dim in ai_result.dimensions:
                with st.expander(f"📊 {dim.dimension}", expanded=True):
                    for ind in dim.indicators:
                        ind_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(
                            ind.get('severity', 'low'), '⚪'
                        )
                        st.markdown(f"**{ind_icon} {ind.get('name', '')}**")
                        st.write(f"- 当前值: {ind.get('value', 'N/A')}")
                        st.write(f"- 评估: {ind.get('assessment', 'N/A')}")
                        st.write(f"- 发现: {ind.get('finding', '')}")
                        st.divider()
                    st.markdown(f"*{dim.summary}*")

            # 建议
            if ai_result.recommendations:
                st.markdown("#### 💡 优化建议")
                for rec in ai_result.recommendations:
                    priority_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(
                        rec.get('priority', 'medium'), '⚪'
                    )
                    with st.container():
                        st.markdown(f"**{priority_icon} {rec.get('title', '')}** [{rec.get('category', '')}]")
                        st.write(rec.get('description', ''))
                        st.caption(f"预期效果: {rec.get('expected_impact', '')}")
                        st.divider()

            if st.button("🔄 重新运行 AI 分析"):
                st.session_state.pop('ai_insights', None)
                st.rerun()
        else:
            st.info("AI 深度分析未生成 (可能是 API Key 缺失或调用失败)。点击下面按钮手动重试。")
            if st.button("🚀 立即运行 AI 深度分析", type="primary"):
                with st.spinner("正在调用 Claude API..."):
                    try:
                        _result = analyzer.generate_ai_insights("本周", api_key)
                        if _result:
                            st.session_state['ai_insights'] = _result
                            st.session_state['ai_insights_ts'] = datetime.now().isoformat(timespec="seconds")
                            st.rerun()
                        else:
                            st.error("AI 分析返回空结果，请检查 API Key。")
                    except Exception as e:
                        st.error(f"AI 分析出错: {e}")

            if st.button("清除分析结果"):
                del st.session_state['ai_insights']
                st.rerun()

# ============================================
# Tab 6: 报告下载
# ============================================
with tab6:
    st.subheader("📄 报告与数据导出")

    # 获取 AI 洞察（如果有）
    ai_insights = st.session_state.get('ai_insights', None)

    if ai_insights:
        st.success("报告将包含 AI 深度分析结果")
    else:
        st.info("报告不包含 AI 分析结果。如需添加，请先在「AI 深度分析」标签页运行分析。")

    # 生成报告
    report_content = generate_markdown_report(
        summary=current_summary,
        member_results=current_members,
        project_results=current_projects,
        insights=insights,
        next_week_summary=next_summary,
        next_week_members=next_members,
        next_week_projects=next_projects,
        ai_insights=ai_insights,
        df=df
    )

    # 报告预览卡片 (默认收起,需要时点开)
    with st.expander("📖 报告预览", expanded=False):
        st.markdown(report_content)

    # Gamma 在线 PPT
    # 优先级: session_state override (本次会话刚重生过) > sidecar (CI 或上次落盘)
    # session_state 兜住 Streamlit Cloud 文件系统易失的问题
    _ref_monday = reference_date - timedelta(days=reference_date.weekday())
    _gamma_url = None
    _matched_date = None
    _sidecar_data = None
    _sidecar_path = None

    _override_url = st.session_state.get('gamma_url_override')
    _override_date = st.session_state.get('gamma_override_date')
    if _override_url and _override_date == reference_date.isoformat():
        _gamma_url = _override_url
        _matched_date = reference_date
        _sidecar_data = {
            "gammaUrl": _override_url,
            "generatedAt": st.session_state.get('gamma_override_generated_at'),
            "source": "streamlit_manual",
        }
    else:
        for _json_path in Path("reports").glob("report_*.json"):
            try:
                _file_date = datetime.strptime(_json_path.stem.replace("report_", ""), "%Y%m%d").date()
            except ValueError:
                continue
            if _file_date - timedelta(days=_file_date.weekday()) == _ref_monday:
                _matched_date = _file_date
                _sidecar_path = _json_path
                try:
                    _sidecar_data = json.loads(_json_path.read_text(encoding="utf-8"))
                    _gamma_url = _sidecar_data.get("gammaUrl")
                except (json.JSONDecodeError, OSError):
                    _sidecar_data = None
                    _gamma_url = None
                break

    # 新鲜度判断: 数据/AI 时间戳晚于 PPT 生成时间 → 提示重生
    _data_ts = st.session_state.get('data_fetched_at')
    _ai_ts = st.session_state.get('ai_insights_ts')
    _generated_at = _sidecar_data.get("generatedAt") if _sidecar_data else None
    _is_stale = False
    if _generated_at:
        if (_data_ts and _data_ts > _generated_at) or (_ai_ts and _ai_ts > _generated_at):
            _is_stale = True

    with st.expander("🎬 Gamma 在线 PPT", expanded=True):
        if _gamma_url:
            if _is_stale:
                st.warning(
                    f"⚠️ 当前已加载的数据/分析比这份 PPT 更新 "
                    f"(PPT 基于 {_generated_at} 生成)，建议重新生成。"
                )
            elif _generated_at:
                _src_label = "本次会话手动重生" if _sidecar_data.get("source") == "streamlit_manual" else "定时任务"
                st.caption(f"📅 此 PPT 基于 {_generated_at} 的数据生成 · {_src_label}")

            _embed_url = _gamma_url.replace("/docs/", "/embed/")
            components.iframe(_embed_url, height=540, scrolling=False)
        else:
            st.info(f"本周 ({_ref_monday.strftime('%Y-%m-%d')} 起) 暂无 Gamma PPT，点下面按钮立即生成。")

        # 操作按钮区
        _col_a, _col_b, _col_c = st.columns([1, 1, 1])
        with _col_a:
            _regen_clicked = st.button(
                "🔄 重新生成 PPT",
                use_container_width=True,
                type="primary" if _is_stale or not _gamma_url else "secondary",
                help="基于当前已加载的数据 + 重跑 AI 深度分析,调用 Gamma 重新生成 PPT (~3–5 分钟)",
            )
        with _col_b:
            if _gamma_url:
                st.link_button("✏️ 在 Gamma 中编辑", _gamma_url, use_container_width=True)
        with _col_c:
            if _matched_date:
                _pdf_path = Path("reports") / f"report_{_matched_date.strftime('%Y%m%d')}.pdf"
                if _pdf_path.exists():
                    st.download_button(
                        "📥 下载 PDF",
                        data=_pdf_path.read_bytes(),
                        file_name=_pdf_path.name,
                        mime="application/pdf",
                        use_container_width=True,
                    )

        if _regen_clicked:
            from src.report_pipeline import render_report_artifacts
            _gamma_key = (
                st.secrets.get("GAMMA_API_KEY", "") if hasattr(st, 'secrets') else ""
            ) or os.getenv("GAMMA_API_KEY", "")
            if not _gamma_key:
                st.error("未检测到 GAMMA_API_KEY，无法调用 Gamma。请配置 Streamlit Secrets 或环境变量。")
            else:
                _regen_ai = ai_insights
                # 用户选择「一并自动重跑 AI」,api_key 可用时先重跑
                if api_key and ai_enabled:
                    with st.spinner("🤖 重跑 AI 深度分析 (~30–60 秒)..."):
                        try:
                            _regen_ai = analyzer.generate_ai_insights("本周", api_key)
                            if _regen_ai:
                                st.session_state['ai_insights'] = _regen_ai
                                st.session_state['ai_insights_ts'] = datetime.now().isoformat(timespec="seconds")
                        except Exception as _e:
                            st.warning(f"AI 重跑失败,将使用现有 AI 结果继续: {_e}")
                            _regen_ai = ai_insights
                else:
                    st.info("未配置 ANTHROPIC_API_KEY,跳过 AI 重跑,直接用现有分析重生 PPT。")

                with st.spinner("🎬 调用 Gamma 生成 PPT (~3–5 分钟,请勿关闭页面)..."):
                    try:
                        _artifacts = render_report_artifacts(
                            df=df,
                            summary=current_summary,
                            member_results=current_members,
                            project_results=current_projects,
                            insights=insights,
                            next_week_summary=next_summary,
                            next_week_members=next_members,
                            next_week_projects=next_projects,
                            ai_insights=_regen_ai,
                            reference_date=reference_date,
                            output_dir="reports",
                            source="streamlit_manual",
                        )
                    except Exception as _e:
                        st.error(f"流水线异常: {_e}")
                        _artifacts = None

                if _artifacts and _artifacts.get("gamma_url"):
                    st.session_state['gamma_url_override'] = _artifacts["gamma_url"]
                    st.session_state['gamma_override_date'] = reference_date.isoformat()
                    st.session_state['gamma_override_generated_at'] = _artifacts["generated_at"]
                    st.success(f"✅ PPT 已重新生成: {_artifacts['gamma_url']}")
                    st.rerun()
                else:
                    st.error("Gamma 生成失败或超时,请稍后重试或检查 GAMMA_API_KEY 配额。")

    st.divider()

    # 下载区域 — 三列卡片布局
    dl1, dl2, dl3 = st.columns(3)

    with dl1:
        st.markdown('''
        <div class="download-card">
            <div class="download-card-icon">📝</div>
            <div class="download-card-title">Markdown 报告</div>
            <div class="download-card-desc">包含完整分析、图表描述与建议</div>
        </div>
        ''', unsafe_allow_html=True)
        st.download_button(
            label="📥 下载报告",
            data=report_content,
            file_name=f"工时分析报告_{reference_date.strftime('%Y%m%d')}.md",
            mime="text/markdown",
            use_container_width=True
        )

    with dl2:
        st.markdown('''
        <div class="download-card">
            <div class="download-card-icon">📊</div>
            <div class="download-card-title">本周原始数据</div>
            <div class="download-card-desc">CSV 格式，可导入 Excel 分析</div>
        </div>
        ''', unsafe_allow_html=True)
        if len(df_current) > 0:
            csv_current = df_current.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 下载本周数据",
                data=csv_current,
                file_name=f"本周工时数据_{reference_date.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.caption("暂无本周数据")

    with dl3:
        st.markdown('''
        <div class="download-card">
            <div class="download-card-icon">📅</div>
            <div class="download-card-title">下周计划数据</div>
            <div class="download-card-desc">CSV 格式，下周工时安排明细</div>
        </div>
        ''', unsafe_allow_html=True)
        if len(df_next) > 0:
            csv_next = df_next.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 下载下周数据",
                data=csv_next,
                file_name=f"下周工时数据_{reference_date.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.caption("暂无下周数据")

# ============================================
# Tab 7: 请假登记
# ============================================
with tab7:
    st.subheader("🏖️ 员工请假登记")
    st.caption("登记后将写入 config/employees.yaml，自动用于工时达成率计算。")

    employees_cfg = get_employees_config()
    employee_options = [emp.get('name_cn') for emp in employees_cfg.get('employees', []) if emp.get('name_cn')]

    if not employee_options:
        st.warning("未在 employees.yaml 中找到任何员工。")
    else:
        with st.form("leave_entry_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1:
                selected_name = st.selectbox("员工姓名", employee_options)
                leave_type = st.selectbox("请假类型", ["年假", "病假", "事假", "调休"])
            with fc2:
                leave_start = st.date_input("请假开始日期", value=reference_date)
                leave_end = st.date_input("请假结束日期", value=reference_date)

            note_text = st.text_area("备注（可选）", placeholder="例如：陪家人就医", height=80)
            submitted = st.form_submit_button("✅ 提交请假登记", use_container_width=True)

            if submitted:
                if leave_end < leave_start:
                    st.error("❌ 请假结束日期不能早于开始日期。")
                else:
                    try:
                        add_employee_leave(
                            name_cn=selected_name,
                            start=leave_start.strftime('%Y-%m-%d'),
                            end=leave_end.strftime('%Y-%m-%d'),
                            leave_type=leave_type,
                            note=note_text.strip(),
                        )
                        days = (leave_end - leave_start).days + 1
                        st.success(
                            f"✅ 已登记成功：{selected_name} 「{leave_type}」"
                            f" {leave_start} → {leave_end}（共 {days} 天）。"
                        )
                    except Exception as e:
                        st.error(f"❌ 写入失败：{e}")

        st.divider()

        # 显示该员工已有请假记录（重新加载以反映刚刚的写入）
        view_name = st.selectbox(
            "查看员工已有请假记录",
            employee_options,
            index=employee_options.index(selected_name) if 'selected_name' in locals() and selected_name in employee_options else 0,
            key="leave_view_selector",
        )
        latest_cfg = get_employees_config()
        target_emp = next(
            (emp for emp in latest_cfg.get('employees', []) if emp.get('name_cn') == view_name),
            None,
        )
        existing_leaves = (target_emp or {}).get('leaves') or []

        if existing_leaves:
            leaves_df = pd.DataFrame([
                {
                    "开始": lv.get('start'),
                    "结束": lv.get('end'),
                    "类型": lv.get('type'),
                    "备注": lv.get('note', ''),
                }
                for lv in existing_leaves
            ])
            st.dataframe(leaves_df, use_container_width=True, hide_index=True)
        else:
            st.info(f"📭 {view_name} 暂无请假记录。")

# ============================================
# 页脚
# ============================================
st.markdown("---")
st.markdown(
    f'<p class="footer-text">📊 团队工时分析系统 &nbsp;·&nbsp; 参考日期: {reference_date} &nbsp;·&nbsp; 数据记录: {meta["total_records"]} 条</p>',
    unsafe_allow_html=True
)

"""
团队工时分析系统 - Streamlit 前端

运行方式：
    streamlit run app.py
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import io
import os

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.data_loader import load_timesheet, validate_data
from src.preprocessor import preprocess_data, filter_by_period
from src.analyzer import TimesheetAnalyzer
from src.visualizer import create_visualizations, create_single_chart
from src.report_generator import generate_markdown_report
from config import get_employees_config

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
# 自定义样式
# ============================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .status-normal { color: #27ae60; }
    .status-warning { color: #e74c3c; }
    .status-low { color: #f39c12; }
</style>
""", unsafe_allow_html=True)

# ============================================
# 侧边栏
# ============================================
with st.sidebar:
    st.header("⚙️ 设置")

    # 数据源选择
    st.subheader("📁 数据来源")
    data_source = st.radio(
        "选择数据来源",
        ["预生成报告（推荐）", "Notion 直连", "CSV 上传"],
        index=1,
        help="预生成报告：读取定时生成的快照（秒开）；Notion 直连：实时拉取最新数据；CSV 上传：手动上传文件"
    )

    uploaded_file = None
    notion_token = None

    if data_source == "Notion 直连":
        # Token 优先从 Streamlit secrets 读取，其次环境变量
        notion_token = st.secrets.get("NOTION_API_TOKEN", "") if hasattr(st, 'secrets') else ""
        if not notion_token:
            notion_token = os.getenv("NOTION_API_TOKEN", "")
        if not notion_token:
            st.error("未配置 NOTION_API_TOKEN，请在 Streamlit Secrets 或环境变量中添加")
            st.stop()
    elif data_source == "预生成报告（推荐）":
        report_dir = Path("reports")
        csv_files = sorted(report_dir.glob("timesheet_*.csv"), reverse=True) if report_dir.exists() else []
        if csv_files:
            selected_report = st.selectbox(
                "选择周报数据",
                csv_files,
                format_func=lambda x: x.stem.replace("timesheet_", "周报 ")
            )
        else:
            st.warning("暂无预生成报告，请切换到其他数据源")
            st.stop()
    else:
        uploaded_file = st.file_uploader(
            "上传工时 CSV 文件",
            type=['csv'],
            help="从 Notion 导出的工时数据 CSV 文件"
        )
    
    # 参考日期
    st.subheader("📅 参考日期")
    reference_date = st.date_input(
        "选择参考日期",
        value=date.today(),
        help="用于判断'本周'和'下周'的基准日期"
    )
    
    # 分析选项
    st.subheader("🔧 分析选项")
    consider_holidays = st.checkbox("考虑节假日", value=True, help="根据法定节假日调整标准工时")
    consider_leaves = st.checkbox("考虑请假", value=True, help="根据员工请假记录调整标准工时")
    
    # AI 分析设置
    st.subheader("🤖 AI 分析设置")

    # 检查 AI 模块是否可用
    if not AI_MODULE_AVAILABLE:
        st.warning("AI 模块未安装，请运行: `pip install anthropic`")
        api_key = None
        ai_enabled = False
    else:
        # 优先从 Streamlit secrets，其次环境变量
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st, 'secrets') else ""
        if not api_key:
            api_key = os.getenv("ANTHROPIC_API_KEY")

        if api_key:
            st.success("已从环境变量读取 API Key")
        else:
            st.info("未检测到环境变量 ANTHROPIC_API_KEY，请手动输入")

        # 手动输入（覆盖环境变量）
        with st.expander("手动输入 API Key", expanded=not bool(api_key)):
            manual_key = st.text_input(
                "Anthropic API Key",
                type="password",
                help="输入后将覆盖环境变量中的 API Key"
            )
            if manual_key:
                api_key = manual_key

        ai_enabled = is_ai_available(api_key)

    # 员工配置预览
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

# ============================================
# 主内容区
# ============================================
st.markdown('<h1 class="main-header">📊 团队工时分析系统</h1>', unsafe_allow_html=True)

# 检查是否有数据（CSV 上传模式需要检查文件）
if data_source == "CSV 上传" and uploaded_file is None:
    st.info("👈 请在左侧上传工时 CSV 文件开始分析")

    with st.expander("📖 使用说明", expanded=True):
        st.markdown("""
        ### 快速开始

        1. **准备数据**：从 Notion 工时数据库导出 CSV 文件
        2. **上传文件**：点击左侧「上传工时 CSV 文件」
        3. **设置日期**：选择参考日期（用于判断本周/下周）
        4. **查看报告**：系统自动生成分析报告和图表

        ### 其他数据源

        - **Notion 直连**：无需手动导出，直接从 Notion 实时拉取数据
        - **预生成报告**：读取 GitHub Actions 定时生成的快照，秒开
        """)

    st.stop()

# ============================================
# 数据加载和预处理
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

try:
    if data_source == "Notion 直连":
        with st.spinner("正在从 Notion 获取数据..."):
            df, meta = fetch_and_process_from_notion(notion_token, reference_date)
    elif data_source == "预生成报告（推荐）":
        with st.spinner("正在加载预生成报告..."):
            df_raw = load_timesheet(str(selected_report))
            df, meta = preprocess_data(df_raw, reference_date)
    else:
        with st.spinner("正在加载数据..."):
            df, meta = load_and_process(uploaded_file.getvalue(), reference_date)
        validation = validate_data(pd.read_csv(io.BytesIO(uploaded_file.getvalue()), encoding='utf-8-sig'))
        if not validation['valid']:
            st.warning("⚠️ 数据质量问题：" + "；".join(validation['issues']))

except Exception as e:
    st.error(f"❌ 数据加载失败: {e}")
    st.stop()

# ============================================
# 分析
# ============================================
analyzer = TimesheetAnalyzer(df)

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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "👥 人员分析",
    "📁 项目分析",
    "📈 图表",
    "📅 下周安排",
    "🤖 AI 深度分析",
    "📄 报告下载"
])

# ============================================
# Tab 1: 人员分析
# ============================================
with tab1:
    if current_members:
        # 状态分布
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
        
        # 人员工时表格
        member_df = pd.DataFrame([
            {
                '姓名': m.name,
                '类型': m.type,
                '总工时': f"{m.total_hours}h",
                '标准工时': f"{m.standard_hours}h" if m.standard_hours else "N/A",
                '达成率': f"{m.achievement_rate}%" if m.achievement_rate else "N/A",
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
                '状态': st.column_config.TextColumn(width='medium')
            }
        )
        
        # 洞察建议
        if insights:
            st.subheader("💡 洞察建议")
            for insight in insights:
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
        # 项目工时表格
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
        
        # 按属性分布
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 项目属性分布")
            attr_data = analyzer.analyze_by_attribute("本周")
            if attr_data:
                attr_df = pd.DataFrame([
                    {'属性': k, '工时': v}
                    for k, v in sorted(attr_data.items(), key=lambda x: x[1], reverse=True)
                ])
                st.bar_chart(attr_df.set_index('属性'))
        
        with col2:
            st.subheader("🎯 优先级分布")
            priority_data = analyzer.analyze_by_priority("本周")
            if priority_data:
                priority_df = pd.DataFrame([
                    {'优先级': k, '工时': v}
                    for k, v in sorted(priority_data.items(), key=lambda x: x[1], reverse=True)
                ])
                st.bar_chart(priority_df.set_index('优先级'))
    else:
        st.info("本周暂无项目数据")

# ============================================
# Tab 3: 图表
# ============================================
with tab3:
    if len(df_current) > 0:
        st.subheader("📊 可视化图表")
        
        # 生成完整图表
        fig = create_visualizations(
            df=df_current,
            member_results=current_members,
            project_results=current_projects,
            return_fig=True
        )
        
        if fig:
            st.pyplot(fig)
        
        # 单独图表选择
        st.divider()
        st.subheader("🔍 单独查看")
        
        chart_type = st.selectbox(
            "选择图表类型",
            options=[
                ('member_hours', '人员工时统计'),
                ('project_pie', '项目工时分布'),
                ('daily_trend', '每日工时趋势'),
                ('achievement_rate', '工时达成率'),
                ('attribute', '项目属性分布'),
                ('heatmap', '工作强度热力图')
            ],
            format_func=lambda x: x[1]
        )
        
        single_fig = create_single_chart(
            chart_type=chart_type[0],
            df=df_current,
            member_results=current_members,
            project_results=current_projects
        )
        st.pyplot(single_fig)
    else:
        st.info("本周暂无数据，无法生成图表")

# ============================================
# Tab 4: 下周安排
# ============================================
with tab4:
    if next_summary['total_hours'] > 0:
        st.metric("预计总工时", f"{next_summary['total_hours']} h")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👥 人员安排")
            if next_members:
                next_member_df = pd.DataFrame([
                    {'成员': m.name, '预计工时': f"{m.total_hours}h"}
                    for m in next_members
                ])
                st.dataframe(next_member_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("📁 主要项目")
            if next_projects:
                next_project_df = pd.DataFrame([
                    {'项目': p.name[:30], '预计工时': f"{p.total_hours}h"}
                    for p in next_projects[:8]
                ])
                st.dataframe(next_project_df, use_container_width=True, hide_index=True)
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

        if st.button("🚀 启动 Claude AI 深度分析", type="primary"):
            with st.spinner("正在调用 Claude API 进行深度分析，请稍候..."):
                try:
                    ai_result = analyzer.generate_ai_insights("本周", api_key)

                    if ai_result:
                        # 保存到 session state
                        st.session_state['ai_insights'] = ai_result

                        # 执行摘要
                        st.markdown("#### 📋 执行摘要")
                        st.info(ai_result.executive_summary)

                        # 四维度分析
                        for dim in ai_result.dimensions:
                            severity_color = {
                                'high': 'red',
                                'medium': 'orange',
                                'low': 'green'
                            }.get(dim.severity, 'gray')

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
                                priority_icon = {
                                    'high': '🔴',
                                    'medium': '🟡',
                                    'low': '🟢'
                                }.get(rec.get('priority', 'medium'), '⚪')

                                with st.container():
                                    st.markdown(f"**{priority_icon} {rec.get('title', '')}** [{rec.get('category', '')}]")
                                    st.write(rec.get('description', ''))
                                    st.caption(f"预期效果: {rec.get('expected_impact', '')}")
                                    st.divider()

                        st.success("AI 分析完成！结果已保存，可在报告下载中导出。")
                    else:
                        st.error("AI 分析返回空结果，请检查 API Key 是否正确。")

                except Exception as e:
                    st.error(f"AI 分析出错: {e}")
                    st.exception(e)

        # 显示之前的分析结果
        if 'ai_insights' in st.session_state:
            st.divider()
            st.markdown("#### 📝 上次分析结果")
            st.caption("上次 AI 分析的结果已保存，可在报告下载中导出。")

            if st.button("清除分析结果"):
                del st.session_state['ai_insights']
                st.rerun()

# ============================================
# Tab 6: 报告下载
# ============================================
with tab6:
    st.subheader("📄 生成 Markdown 报告")

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
        ai_insights=ai_insights
    )
    
    # 预览
    with st.expander("📖 报告预览", expanded=False):
        st.markdown(report_content)
    
    # 下载按钮
    st.download_button(
        label="📥 下载 Markdown 报告",
        data=report_content,
        file_name=f"工时分析报告_{reference_date.strftime('%Y%m%d')}.md",
        mime="text/markdown"
    )
    
    st.divider()
    
    # 原始数据下载
    st.subheader("📊 原始数据下载")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if len(df_current) > 0:
            csv_current = df_current.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 下载本周数据 (CSV)",
                data=csv_current,
                file_name=f"本周工时数据_{reference_date.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    with col2:
        if len(df_next) > 0:
            csv_next = df_next.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 下载下周数据 (CSV)",
                data=csv_next,
                file_name=f"下周工时数据_{reference_date.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

# ============================================
# 页脚
# ============================================
st.divider()
st.caption(f"📊 团队工时分析系统 | 参考日期: {reference_date} | 数据记录: {meta['total_records']} 条")

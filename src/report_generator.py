"""
报告生成模块

生成 Markdown 格式的分析报告，使用 --- 分页以适配 Gamma PPT 生成。

分页方案（14 页）：
  1. 封面 — 标题、分析周期、部门、生成时间
  2. 执行摘要 — 关键指标 + AI 洞察摘要 + 团队状态分布
  3. 人员工时总览 — 汇总表格
  4. 项目投入总览 — TOP 10 + 属性分布
  5. TOP 1 项目明细
  6. TOP 2 项目明细
  7. TOP 3 + 未立项分析
  8. 超负荷人员分析
  9. 其他成员分析
  10. 下周安排
  11. AI 洞察：预警与行动
  12. AI 洞察：战略与效率（战略一致性 + 执行效率）
  13. AI 洞察：健康与合规（团队健康 + 财务合规）
  14. 优化建议
"""
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

PAGE_BREAK = "\n\n---\n\n"


def _generate_project_detail_page(df_period: pd.DataFrame, project) -> List[str]:
    """生成单个项目的事项明细"""
    lines = []

    lines.append(f"### {project.name}（{project.total_hours}h / {project.percentage}%）")
    lines.append("")

    proj_data = df_period[df_period['项目名称_清理'] == project.name]

    for member in proj_data['成员_中文'].unique():
        member_data = proj_data[proj_data['成员_中文'] == member]
        member_hours = member_data['工时 h'].sum()
        lines.append(f"**{member}**（{member_hours:.1f}h）：")

        tasks = member_data.sort_values('工时 h', ascending=False)
        for _, row in tasks.iterrows():
            task_name = row.get('工作内容', '') or '（无描述）'
            task_name = str(task_name).strip() or '（无描述）'
            lines.append(f"- {task_name}（{row['工时 h']}h）")

        lines.append("")

    return lines


def _generate_adhoc_section(df_period: pd.DataFrame) -> List[str]:
    """生成未立项/临时指派分析"""
    lines = []
    total_hours = df_period['工时 h'].sum() if len(df_period) > 0 else 0

    adhoc_keywords = ['未立项', '临时指派']
    adhoc_data = df_period[df_period['项目名称_清理'].str.contains('|'.join(adhoc_keywords), na=False)]

    if len(adhoc_data) > 0:
        adhoc_hours = adhoc_data['工时 h'].sum()
        adhoc_pct = adhoc_hours / total_hours * 100 if total_hours > 0 else 0
        adhoc_count = len(adhoc_data)
        adhoc_members = adhoc_data['成员_中文'].unique()

        lines.append("### ⚠️ 未立项/临时指派工时分析")
        lines.append("")
        lines.append(f"- **总工时：** {adhoc_hours:.1f}h，占全部工时的 **{adhoc_pct:.1f}%**")
        lines.append(f"- **任务条数：** {adhoc_count} 条")
        lines.append(f"- **涉及人员：** {', '.join(adhoc_members)}")
        lines.append("")

        lines.append("| 日期 | 成员 | 工作内容 | 工时 |")
        lines.append("|------|------|----------|------|")
        for _, row in adhoc_data.sort_values('工时 h', ascending=False).iterrows():
            date_str = str(row.get('日期', ''))[:10]
            member = row.get('成员_中文', '')
            task = str(row.get('工作内容', '')).strip() or '（无描述）'
            if len(task) > 50:
                task = task[:50] + "..."
            lines.append(f"| {date_str} | {member} | {task} | {row['工时 h']}h |")
        lines.append("")

    return lines


def _generate_member_detail(df_period: pd.DataFrame, member) -> List[str]:
    """生成单个成员的事项明细表格"""
    lines = []

    lines.append(f"#### {member.name}（{member.type} / {member.total_hours}h / {member.status}）")
    lines.append("")

    m_data = df_period[df_period['成员_中文'] == member.name]
    if len(m_data) == 0:
        return lines

    proj_groups = m_data.groupby('项目名称_清理').agg(
        工时=('工时 h', 'sum'),
        任务数=('工时 h', 'count')
    ).sort_values('工时', ascending=False)

    lines.append("| 项目 | 工时 | 任务数 | 具体事项 |")
    lines.append("|------|------|--------|----------|")

    for proj_name, row in proj_groups.iterrows():
        tasks_in_proj = m_data[m_data['项目名称_清理'] == proj_name]
        task_list = []
        for _, t in tasks_in_proj.sort_values('工时 h', ascending=False).iterrows():
            desc = str(t.get('工作内容', '')).strip() or '（无描述）'
            if len(desc) > 30:
                desc = desc[:30] + "..."
            task_list.append(f"{desc}({t['工时 h']}h)")

        proj_display = str(proj_name)
        if len(proj_display) > 25:
            proj_display = proj_display[:25] + "..."
        lines.append(f"| {proj_display} | {row['工时']:.1f}h | {int(row['任务数'])} | {'；'.join(task_list)} |")

    lines.append("")

    return lines


def generate_markdown_report(
    summary: Dict,
    member_results: List,
    project_results: List,
    insights: List[Dict],
    next_week_summary: Optional[Dict] = None,
    next_week_members: Optional[List] = None,
    next_week_projects: Optional[List] = None,
    ai_insights=None,
    df=None
) -> str:
    """
    生成 Markdown 格式的分析报告（13 页分页，适配 Gamma PPT）

    Parameters
    ----------
    summary : Dict
        本周汇总信息
    member_results : List[MemberAnalysis]
        成员分析结果
    project_results : List[ProjectAnalysis]
        项目分析结果
    insights : List[Dict]
        洞察建议（保留参数兼容性，不再输出到报告）
    next_week_summary : Dict, optional
        下周汇总（如果有）
    next_week_members : List, optional
        下周成员安排
    next_week_projects : List, optional
        下周项目安排
    ai_insights : AIInsightResult, optional
        AI 深度分析结果
    df : pd.DataFrame, optional
        预处理后的工时 DataFrame，用于生成项目细化分析

    Returns
    -------
    str
        Markdown 格式的报告内容
    """
    # 预处理：获取本周 DataFrame
    df_period = None
    if df is not None and len(df) > 0:
        df_period = df[df['周期类型'] == '本周'] if '周期类型' in df.columns else df
        if len(df_period) == 0:
            df_period = None

    pages = []

    # ===== 第 1 页：封面 =====
    page1 = []
    page1.append("# 团队工时分析报告")
    page1.append("")
    if summary.get('date_range'):
        page1.append(f"**分析周期：** {summary['date_range'][0]} 至 {summary['date_range'][1]}")
    page1.append("")
    page1.append("**部门：** 美年健康研究院 数据平台部")
    page1.append("")
    page1.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pages.append("\n".join(page1))

    # ===== 第 2 页：执行摘要 =====
    page2 = []
    page2.append("## 📊 执行摘要")
    page2.append("")
    page2.append(f"- **总工时：** {summary['total_hours']} 小时")
    page2.append(f"- **工作天数：** {summary['working_days']} 天")
    page2.append(f"- **涉及项目：** {summary['project_count']} 个")
    page2.append(f"- **团队规模：** {summary['member_count']} 人")
    page2.append("")

    if ai_insights and ai_insights.executive_summary:
        page2.append("### AI 洞察摘要")
        page2.append("")
        page2.append(f"> {ai_insights.executive_summary}")
        page2.append("")

    if member_results:
        normal = len([m for m in member_results if '正常' in m.status])
        overloaded = len([m for m in member_results if '超负荷' in m.status])
        underloaded = len([m for m in member_results if '偏低' in m.status])
        flexible = len([m for m in member_results if '按需' in m.status])

        page2.append("### 团队状态分布")
        page2.append("")
        page2.append(f"- ✅ **正常负荷：** {normal} 人")
        page2.append(f"- ⚠️ **超负荷：** {overloaded} 人")
        page2.append(f"- 📉 **负荷偏低：** {underloaded} 人")
        page2.append(f"- 🔄 **按需工作：** {flexible} 人")
    pages.append("\n".join(page2))

    # ===== 第 3 页：人员工时总览 =====
    page3 = []
    page3.append("## 👥 人员工时总览")
    page3.append("")
    if member_results:
        page3.append("| 姓名 | 类型 | 总工时 | 标准工时 | 达成率 | 日均 | 任务数 | 状态 |")
        page3.append("|------|------|--------|----------|--------|------|--------|------|")
        for m in member_results:
            standard = f"{m.standard_hours}h" if m.standard_hours else "N/A"
            rate = f"{m.achievement_rate}%" if m.achievement_rate else "N/A"
            status_clean = m.status.replace('⚠️ ', '').replace('✅ ', '').replace('📉 ', '').replace('🔄 ', '')
            page3.append(f"| {m.name} | {m.type} | {m.total_hours}h | {standard} | {rate} | {m.daily_avg}h | {m.task_count} | {status_clean} |")
    pages.append("\n".join(page3))

    # ===== 第 4 页：项目投入总览 =====
    page4 = []
    page4.append("## 📁 项目投入总览")
    page4.append("")
    if project_results:
        page4.append("### TOP 10 项目工时投入")
        page4.append("")
        page4.append("| 排名 | 项目名称 | 投入工时 | 占比 | 参与人数 |")
        page4.append("|------|----------|----------|------|----------|")
        for i, p in enumerate(project_results[:10], 1):
            name = p.name[:40] + "..." if len(p.name) > 40 else p.name
            page4.append(f"| {i} | {name} | {p.total_hours}h | {p.percentage}% | {p.member_count} |")
        page4.append("")

        # 属性分布
        attr_groups = {}
        for p in project_results:
            attr = p.attribute
            if attr not in attr_groups:
                attr_groups[attr] = 0
            attr_groups[attr] += p.total_hours

        if attr_groups:
            total = sum(attr_groups.values())
            page4.append("### 项目属性分布")
            page4.append("")
            page4.append("| 项目属性 | 工时 | 占比 |")
            page4.append("|----------|------|------|")
            for attr, hours in sorted(attr_groups.items(), key=lambda x: x[1], reverse=True):
                pct = hours / total * 100 if total > 0 else 0
                page4.append(f"| {attr} | {hours:.1f}h | {pct:.1f}% |")
    pages.append("\n".join(page4))

    # ===== 第 5-7 页：TOP 项目明细 + 未立项分析 =====
    if df_period is not None and project_results:
        top3 = project_results[:3]

        # 第 5 页：TOP 1
        if len(top3) >= 1:
            page5 = []
            page5.append("## 🔍 重点项目明细（1/3）")
            page5.append("")
            page5.extend(_generate_project_detail_page(df_period, top3[0]))
            pages.append("\n".join(page5))

        # 第 6 页：TOP 2
        if len(top3) >= 2:
            page6 = []
            page6.append("## 🔍 重点项目明细（2/3）")
            page6.append("")
            page6.extend(_generate_project_detail_page(df_period, top3[1]))
            pages.append("\n".join(page6))

        # 第 7 页：TOP 3 + 未立项
        if len(top3) >= 3:
            page7 = []
            page7.append("## 🔍 重点项目明细（3/3）+ 未立项分析")
            page7.append("")
            page7.extend(_generate_project_detail_page(df_period, top3[2]))
            page7.extend(_generate_adhoc_section(df_period))
            pages.append("\n".join(page7))

    # ===== 第 8 页：超负荷人员分析 =====
    if df_period is not None and member_results:
        overloaded_members = [m for m in member_results if '超负荷' in m.status]
        if not overloaded_members:
            # 没有超负荷人员时取前 2 人
            overloaded_members = member_results[:2]

        page8 = []
        page8.append("## ⚠️ 超负荷人员分析")
        page8.append("")
        for m in overloaded_members:
            page8.extend(_generate_member_detail(df_period, m))
        pages.append("\n".join(page8))

        # ===== 第 9 页：其他成员分析 =====
        overloaded_names = {m.name for m in overloaded_members}
        other_members = [m for m in member_results if m.name not in overloaded_names]

        if other_members:
            page9 = []
            page9.append("## 📋 其他成员分析")
            page9.append("")
            for m in other_members:
                page9.extend(_generate_member_detail(df_period, m))
            pages.append("\n".join(page9))

    # ===== 第 10 页：下周安排 =====
    if next_week_summary and next_week_summary.get('total_hours', 0) > 0:
        page10 = []
        page10.append("## 📅 下周工时安排")
        page10.append("")
        page10.append(f"**预计总工时：** {next_week_summary['total_hours']} 小时")
        page10.append("")

        if next_week_members:
            page10.append("### 人员安排")
            page10.append("")
            page10.append("| 成员 | 预计工时 |")
            page10.append("|------|----------|")
            for m in next_week_members:
                page10.append(f"| {m.name} | {m.total_hours}h |")
            page10.append("")

        if next_week_projects:
            page10.append("### 主要项目")
            page10.append("")
            page10.append("| 项目名称 | 预计工时 |")
            page10.append("|----------|----------|")
            for p in next_week_projects[:8]:
                name = p.name[:35] + "..." if len(p.name) > 35 else p.name
                page10.append(f"| {name} | {p.total_hours}h |")

        pages.append("\n".join(page10))

    # ===== 第 11-14 页：AI 深度分析 =====
    if ai_insights:
        qs = ai_insights.quick_scan

        # 第 11 页：预警与行动
        page11 = []
        page11.append("## 🤖 AI 洞察：预警与行动")
        page11.append("")

        if qs.anomalies:
            page11.append("### 🚨 异常值警报")
            page11.append("")
            for a in qs.anomalies:
                page11.append(f"**{a.get('type', '异常')}** — {a.get('member', 'N/A')}")
                page11.append("")
                page11.append(f"- 当前值: {a.get('value', 'N/A')}")
                page11.append(f"- 关注点: {a.get('concern', '')}")
                page11.append("")

        if qs.action_items:
            page11.append("### ✅ 立即行动项")
            page11.append("")
            for item in qs.action_items:
                page11.append(f"- [ ] {item}")

        pages.append("\n".join(page11))

        # 第 12 页：战略一致性 + 执行效率
        dims = ai_insights.dimensions
        first_half = [d for d in dims if d.dimension in ('战略一致性', '执行效率与模式')]
        second_half = [d for d in dims if d.dimension not in ('战略一致性', '执行效率与模式')]

        # 如果维度名称不匹配预期，按前后各半拆分
        if not first_half and not second_half:
            mid = (len(dims) + 1) // 2
            first_half = dims[:mid]
            second_half = dims[mid:]

        if first_half:
            page12 = []
            page12.append("## 🤖 AI 洞察：战略与效率")
            page12.append("")

            for dim in first_half:
                severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(dim.severity, '⚪')
                page12.append(f"### {severity_icon} {dim.dimension}")
                page12.append("")

                for ind in dim.indicators:
                    ind_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(ind.get('severity', 'low'), '⚪')
                    page12.append(f"#### {ind_icon} {ind.get('name', '')}")
                    page12.append("")
                    page12.append(f"- **当前值**: {ind.get('value', 'N/A')}")
                    page12.append(f"- **评估**: {ind.get('assessment', 'N/A')}")
                    page12.append(f"- **发现**: {ind.get('finding', '')}")
                    page12.append("")

                page12.append(f"**维度总结**: {dim.summary}")
                page12.append("")

            pages.append("\n".join(page12))

        # 第 13 页：团队健康 + 财务合规
        if second_half:
            page13 = []
            page13.append("## 🤖 AI 洞察：健康与合规")
            page13.append("")

            for dim in second_half:
                severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(dim.severity, '⚪')
                page13.append(f"### {severity_icon} {dim.dimension}")
                page13.append("")

                for ind in dim.indicators:
                    ind_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(ind.get('severity', 'low'), '⚪')
                    page13.append(f"#### {ind_icon} {ind.get('name', '')}")
                    page13.append("")
                    page13.append(f"- **当前值**: {ind.get('value', 'N/A')}")
                    page13.append(f"- **评估**: {ind.get('assessment', 'N/A')}")
                    page13.append(f"- **发现**: {ind.get('finding', '')}")
                    page13.append("")

                page13.append(f"**维度总结**: {dim.summary}")
                page13.append("")

            pages.append("\n".join(page13))

        # 第 14 页：优化建议
        if ai_insights.recommendations:
            page14 = []
            page14.append("## 📋 优化建议")
            page14.append("")

            page14.append("| 优先级 | 类别 | 建议 | 预期效果 |")
            page14.append("|--------|------|------|----------|")
            for rec in ai_insights.recommendations:
                priority_cn = {'high': '🔴 高', 'medium': '🟡 中', 'low': '🟢 低'}.get(
                    rec.get('priority', 'medium'), '中'
                )
                page14.append(
                    f"| {priority_cn} | {rec.get('category', '')} | {rec.get('title', '')} | {rec.get('expected_impact', '')} |"
                )
            page14.append("")

            page14.append("### 建议详情")
            page14.append("")
            for rec in ai_insights.recommendations:
                priority_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(rec.get('priority', 'medium'), '⚪')
                page14.append(f"**{priority_icon} {rec.get('title', '')}**")
                page14.append("")
                page14.append(rec.get('description', ''))
                page14.append("")

            pages.append("\n".join(page14))

    # ===== 组装：用 --- 分隔各页 =====
    report = PAGE_BREAK.join(pages)

    # 页脚
    report += f"\n\n---\n\n*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"

    return report


def save_report(content: str, filepath: Path) -> bool:
    """
    保存报告到文件

    Returns
    -------
    bool
        是否保存成功
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"保存报告失败: {e}")
        return False

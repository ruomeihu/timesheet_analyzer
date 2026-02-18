"""
报告生成模块

生成 Markdown 格式的分析报告
"""
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


def generate_ai_insights_section(ai_result) -> str:
    """
    生成 AI 洞察的 Markdown 部分

    Parameters
    ----------
    ai_result : AIInsightResult
        AI 分析结果

    Returns
    -------
    str
        Markdown 格式的 AI 洞察内容
    """
    lines = []

    lines.append("## 🤖 AI 深度分析洞察")
    lines.append("")

    # 执行摘要
    if ai_result.executive_summary:
        lines.append("### 执行摘要")
        lines.append("")
        lines.append(f"> {ai_result.executive_summary}")
        lines.append("")

    # 快速扫视
    qs = ai_result.quick_scan

    if qs.anomalies:
        lines.append("### 🚨 异常值警报")
        lines.append("")
        for a in qs.anomalies:
            lines.append(f"- **{a.get('type', '异常')}** | {a.get('member', 'N/A')}: {a.get('value', 'N/A')} - {a.get('concern', '')}")
        lines.append("")

    if qs.action_items:
        lines.append("### ✅ 立即行动项")
        lines.append("")
        for item in qs.action_items:
            lines.append(f"- [ ] {item}")
        lines.append("")

    # 四维度分析
    for dim in ai_result.dimensions:
        severity_icon = {
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }.get(dim.severity, '⚪')

        lines.append(f"### {severity_icon} 维度: {dim.dimension}")
        lines.append("")

        for ind in dim.indicators:
            ind_severity = ind.get('severity', 'low')
            ind_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(ind_severity, '⚪')

            lines.append(f"#### {ind_icon} {ind.get('name', '')}")
            lines.append("")
            lines.append(f"- **当前值**: {ind.get('value', 'N/A')}")
            lines.append(f"- **评估**: {ind.get('assessment', 'N/A')}")
            lines.append(f"- **发现**: {ind.get('finding', '')}")
            lines.append("")

        lines.append(f"**维度总结**: {dim.summary}")
        lines.append("")

    # 建议
    if ai_result.recommendations:
        lines.append("### 📋 优化建议")
        lines.append("")
        lines.append("| 优先级 | 类别 | 建议 | 预期效果 |")
        lines.append("|--------|------|------|----------|")

        for rec in ai_result.recommendations:
            priority_cn = {'high': '🔴 高', 'medium': '🟡 中', 'low': '🟢 低'}.get(
                rec.get('priority', 'medium'), '中'
            )
            lines.append(
                f"| {priority_cn} | {rec.get('category', '')} | {rec.get('title', '')} | {rec.get('expected_impact', '')} |"
            )
        lines.append("")

        # 详细建议
        lines.append("#### 建议详情")
        lines.append("")
        for rec in ai_result.recommendations:
            priority_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(rec.get('priority', 'medium'), '⚪')
            lines.append(f"**{priority_icon} {rec.get('title', '')}**")
            lines.append("")
            lines.append(rec.get('description', ''))
            lines.append("")

    return "\n".join(lines)


def generate_markdown_report(
    summary: Dict,
    member_results: List,
    project_results: List,
    insights: List[Dict],
    next_week_summary: Optional[Dict] = None,
    next_week_members: Optional[List] = None,
    next_week_projects: Optional[List] = None,
    ai_insights = None
) -> str:
    """
    生成 Markdown 格式的分析报告
    
    Parameters
    ----------
    summary : Dict
        本周汇总信息
    member_results : List[MemberAnalysis]
        成员分析结果
    project_results : List[ProjectAnalysis]
        项目分析结果
    insights : List[Dict]
        洞察建议
    next_week_summary : Dict, optional
        下周汇总（如果有）
    next_week_members : List, optional
        下周成员安排
    next_week_projects : List, optional
        下周项目安排
    ai_insights : AIInsightResult, optional
        AI 深度分析结果

    Returns
    -------
    str
        Markdown 格式的报告内容
    """
    lines = []
    
    # 标题
    lines.append("# 团队工时分析报告")
    lines.append("")
    lines.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if summary.get('date_range'):
        lines.append(f"**分析期间：** {summary['date_range'][0]} 至 {summary['date_range'][1]}")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # 执行摘要
    lines.append("## 📊 执行摘要")
    lines.append("")
    lines.append(f"- **总工时：** {summary['total_hours']} 小时")
    lines.append(f"- **工作天数：** {summary['working_days']} 天")
    lines.append(f"- **涉及项目：** {summary['project_count']} 个")
    lines.append(f"- **团队规模：** {summary['member_count']} 人")
    lines.append("")
    
    # 团队状态
    if member_results:
        normal = len([m for m in member_results if '正常' in m.status])
        overloaded = len([m for m in member_results if '超负荷' in m.status])
        underloaded = len([m for m in member_results if '偏低' in m.status])
        flexible = len([m for m in member_results if '按需' in m.status])
        
        lines.append("### 团队状态分布")
        lines.append("")
        lines.append(f"- ✅ **正常负荷：** {normal} 人")
        lines.append(f"- ⚠️ **超负荷：** {overloaded} 人")
        lines.append(f"- 📉 **负荷偏低：** {underloaded} 人")
        lines.append(f"- 🔄 **按需工作：** {flexible} 人")
        lines.append("")
    
    # 人员工时详情
    lines.append("## 👥 人员工时分析")
    lines.append("")
    
    if member_results:
        lines.append("| 姓名 | 类型 | 总工时 | 标准工时 | 达成率 | 日均 | 任务数 | 状态 |")
        lines.append("|------|------|--------|----------|--------|------|--------|------|")
        
        for m in member_results:
            standard = f"{m.standard_hours}h" if m.standard_hours else "N/A"
            rate = f"{m.achievement_rate}%" if m.achievement_rate else "N/A"
            status_clean = m.status.replace('⚠️ ', '').replace('✅ ', '').replace('📉 ', '').replace('🔄 ', '')
            
            lines.append(f"| {m.name} | {m.type} | {m.total_hours}h | {standard} | {rate} | {m.daily_avg}h | {m.task_count} | {status_clean} |")
        
        lines.append("")
        
        # 人员详情
        lines.append("### 人员工时详情")
        lines.append("")
        
        for m in member_results:
            lines.append(f"#### {m.name} ({m.type})")
            lines.append("")
            lines.append(f"- **总工时：** {m.total_hours} 小时")
            lines.append(f"- **日均工时：** {m.daily_avg} 小时")
            lines.append(f"- **任务数量：** {m.task_count} 个")
            lines.append(f"- **工作天数：** {m.working_days} 天")
            
            if m.standard_hours:
                lines.append(f"- **标准工时：** {m.standard_hours} 小时/周")
                lines.append(f"- **达成率：** {m.achievement_rate}%")
            
            if m.leave_days > 0:
                lines.append(f"- **请假天数：** {m.leave_days} 天")
            
            lines.append(f"- **工作状态：** {m.status}")
            lines.append("")
    
    # 项目分析
    lines.append("## 📁 项目投入分析")
    lines.append("")
    
    if project_results:
        lines.append("### TOP 10 项目工时投入")
        lines.append("")
        lines.append("| 排名 | 项目名称 | 投入工时 | 占比 | 参与人数 |")
        lines.append("|------|----------|----------|------|----------|")
        
        for i, p in enumerate(project_results[:10], 1):
            name = p.name[:40] + "..." if len(p.name) > 40 else p.name
            lines.append(f"| {i} | {name} | {p.total_hours}h | {p.percentage}% | {p.member_count} |")
        
        lines.append("")
        
        # 按属性分类
        attr_groups = {}
        for p in project_results:
            attr = p.attribute
            if attr not in attr_groups:
                attr_groups[attr] = 0
            attr_groups[attr] += p.total_hours
        
        if attr_groups:
            total = sum(attr_groups.values())
            lines.append("### 项目属性分布")
            lines.append("")
            lines.append("| 项目属性 | 工时 | 占比 |")
            lines.append("|----------|------|------|")
            
            for attr, hours in sorted(attr_groups.items(), key=lambda x: x[1], reverse=True):
                pct = hours / total * 100 if total > 0 else 0
                lines.append(f"| {attr} | {hours:.1f}h | {pct:.1f}% |")
            
            lines.append("")
    
    # 下周安排
    if next_week_summary and next_week_summary.get('total_hours', 0) > 0:
        lines.append("## 📅 下周工时安排")
        lines.append("")
        lines.append(f"**预计总工时：** {next_week_summary['total_hours']} 小时")
        lines.append("")
        
        if next_week_members:
            lines.append("### 人员安排")
            lines.append("")
            lines.append("| 成员 | 预计工时 |")
            lines.append("|------|----------|")
            
            for m in next_week_members:
                lines.append(f"| {m.name} | {m.total_hours}h |")
            
            lines.append("")
        
        if next_week_projects:
            lines.append("### 主要项目")
            lines.append("")
            lines.append("| 项目名称 | 预计工时 |")
            lines.append("|----------|----------|")
            
            for p in next_week_projects[:8]:
                name = p.name[:35] + "..." if len(p.name) > 35 else p.name
                lines.append(f"| {name} | {p.total_hours}h |")
            
            lines.append("")
    
    # 洞察建议
    if insights:
        lines.append("## 💡 关键洞察与优化建议")
        lines.append("")

        for insight in insights:
            lines.append(f"### {insight['title']}")
            lines.append("")
            lines.append(insight['content'])
            lines.append("")

    # AI 深度分析洞察
    if ai_insights:
        lines.append("")
        lines.append(generate_ai_insights_section(ai_insights))
        lines.append("")

    # 页脚
    lines.append("---")
    lines.append("")
    lines.append(f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    
    return "\n".join(lines)


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

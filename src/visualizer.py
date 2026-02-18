"""
可视化模块

生成各种工时分析图表
"""
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import io

# 设置中文字体
def setup_chinese_font():
    """配置中文字体支持"""
    font_candidates = [
        'Arial Unicode MS',  # macOS
        'SimHei',            # Windows
        'WenQuanYi Micro Hei',  # Linux
        'Noto Sans CJK SC',  # 通用
        'DejaVu Sans'        # 后备
    ]
    
    available_fonts = [f.name for f in matplotlib.font_manager.fontManager.ttflist]
    
    for font in font_candidates:
        if font in available_fonts:
            plt.rcParams['font.sans-serif'] = [font]
            plt.rcParams['axes.unicode_minus'] = False
            return font
    
    # 如果没找到中文字体，使用默认字体
    return None


# 初始化字体
setup_chinese_font()


def create_visualizations(
    df: pd.DataFrame,
    member_results: List,
    project_results: List,
    output_path: Optional[Path] = None,
    return_fig: bool = False
) -> Optional[plt.Figure]:
    """
    创建工时分析可视化图表
    
    Parameters
    ----------
    df : pd.DataFrame
        预处理后的数据（已过滤周期）
    member_results : List[MemberAnalysis]
        成员分析结果
    project_results : List[ProjectAnalysis]
        项目分析结果
    output_path : Path, optional
        输出文件路径，如果提供则保存图片
    return_fig : bool
        是否返回 Figure 对象（用于 Streamlit）
    
    Returns
    -------
    plt.Figure or None
        如果 return_fig=True，返回 Figure 对象
    """
    fig = plt.figure(figsize=(18, 12))
    fig.suptitle('团队工时分析报告', fontsize=16, fontweight='bold', y=0.98)
    
    # 1. 人员工时柱状图
    ax1 = plt.subplot(2, 3, 1)
    _plot_member_hours(ax1, member_results)
    
    # 2. 项目工时饼图
    ax2 = plt.subplot(2, 3, 2)
    _plot_project_pie(ax2, project_results)
    
    # 3. 每日工时趋势
    ax3 = plt.subplot(2, 3, 3)
    _plot_daily_trend(ax3, df)
    
    # 4. 工时达成率
    ax4 = plt.subplot(2, 3, 4)
    _plot_achievement_rate(ax4, member_results)
    
    # 5. 项目属性分布
    ax5 = plt.subplot(2, 3, 5)
    _plot_attribute_distribution(ax5, df)
    
    # 6. 人员工作强度热力图
    ax6 = plt.subplot(2, 3, 6)
    _plot_heatmap(ax6, df)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    if output_path:
        plt.savefig(output_path, dpi=200, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
    
    if return_fig:
        return fig
    else:
        plt.close(fig)
        return None


def _plot_member_hours(ax: plt.Axes, results: List) -> None:
    """绘制人员工时柱状图"""
    if not results:
        ax.text(0.5, 0.5, '无数据', ha='center', va='center', fontsize=12)
        ax.set_title('人员工时统计')
        return
    
    names = [r.name for r in results]
    hours = [r.total_hours for r in results]
    standards = [r.standard_hours or 0 for r in results]
    
    x = np.arange(len(names))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, hours, width, label='实际工时', color='steelblue', alpha=0.8)
    bars2 = ax.bar(x + width/2, standards, width, label='标准工时', color='lightgray', alpha=0.8)
    
    ax.set_xlabel('成员')
    ax.set_ylabel('工时 (小时)')
    ax.set_title('人员工时统计')
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha='right')
    ax.legend()
    
    # 添加数值标签
    for bar in bars1:
        height = bar.get_height()
        if height > 0:
            ax.annotate(f'{height:.0f}',
                       xy=(bar.get_x() + bar.get_width()/2, height),
                       xytext=(0, 3), textcoords='offset points',
                       ha='center', va='bottom', fontsize=9)


def _plot_project_pie(ax: plt.Axes, results: List) -> None:
    """绘制项目工时饼图"""
    if not results:
        ax.text(0.5, 0.5, '无数据', ha='center', va='center', fontsize=12)
        ax.set_title('项目工时分布')
        return
    
    # 取 TOP 8，其余合并为"其他"
    top_n = 8
    top_results = results[:top_n]
    other_hours = sum(r.total_hours for r in results[top_n:])
    
    names = [r.name[:15] + '...' if len(r.name) > 15 else r.name for r in top_results]
    hours = [r.total_hours for r in top_results]
    
    if other_hours > 0:
        names.append('其他')
        hours.append(other_hours)
    
    colors = plt.cm.Set3(np.linspace(0, 1, len(names)))
    
    wedges, texts, autotexts = ax.pie(
        hours, 
        labels=names,
        autopct='%1.1f%%',
        colors=colors,
        startangle=90,
        pctdistance=0.8
    )
    
    # 调整标签字体大小
    for text in texts:
        text.set_fontsize(8)
    for autotext in autotexts:
        autotext.set_fontsize(8)
    
    ax.set_title('项目工时分布 (TOP 8)')


def _plot_daily_trend(ax: plt.Axes, df: pd.DataFrame) -> None:
    """绘制每日工时趋势"""
    if len(df) == 0:
        ax.text(0.5, 0.5, '无数据', ha='center', va='center', fontsize=12)
        ax.set_title('每日工时趋势')
        return
    
    daily_hours = df.groupby('日期')['工时 h'].sum().sort_index()
    
    ax.plot(daily_hours.index, daily_hours.values, 
            marker='o', linewidth=2, markersize=8, color='steelblue')
    ax.fill_between(daily_hours.index, 0, daily_hours.values, alpha=0.3, color='steelblue')
    
    ax.set_xlabel('日期')
    ax.set_ylabel('总工时')
    ax.set_title('每日工时趋势')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3)


def _plot_achievement_rate(ax: plt.Axes, results: List) -> None:
    """绘制工时达成率"""
    # 过滤有达成率的成员
    valid_results = [r for r in results if r.achievement_rate is not None]
    
    if not valid_results:
        ax.text(0.5, 0.5, '无数据', ha='center', va='center', fontsize=12)
        ax.set_title('工时达成率')
        return
    
    names = [r.name for r in valid_results]
    rates = [r.achievement_rate for r in valid_results]
    
    # 根据达成率设置颜色
    colors = []
    for rate in rates:
        if rate >= 120:
            colors.append('#e74c3c')  # 红色 - 超负荷
        elif rate <= 70:
            colors.append('#f39c12')  # 橙色 - 偏低
        else:
            colors.append('#27ae60')  # 绿色 - 正常
    
    bars = ax.barh(names, rates, color=colors, alpha=0.8)
    
    # 添加参考线
    ax.axvline(x=100, color='gray', linestyle='--', linewidth=1, alpha=0.7)
    ax.axvline(x=70, color='orange', linestyle=':', linewidth=1, alpha=0.5)
    ax.axvline(x=120, color='red', linestyle=':', linewidth=1, alpha=0.5)
    
    ax.set_xlabel('达成率 (%)')
    ax.set_title('工时达成率')
    
    # 添加数值标签
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
               f'{rate:.0f}%', va='center', fontsize=9)


def _plot_attribute_distribution(ax: plt.Axes, df: pd.DataFrame) -> None:
    """绘制项目属性分布"""
    if '项目属性' not in df.columns or len(df) == 0:
        ax.text(0.5, 0.5, '无数据', ha='center', va='center', fontsize=12)
        ax.set_title('项目属性分布')
        return
    
    attr_hours = df.groupby('项目属性')['工时 h'].sum().sort_values(ascending=True)
    
    colors = plt.cm.Pastel1(np.linspace(0, 1, len(attr_hours)))
    bars = ax.barh(attr_hours.index, attr_hours.values, color=colors, alpha=0.8)
    
    ax.set_xlabel('工时')
    ax.set_title('项目属性分布')
    
    # 添加数值标签
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2,
               f'{width:.1f}h', va='center', fontsize=9)


def _plot_heatmap(ax: plt.Axes, df: pd.DataFrame) -> None:
    """绘制人员工作强度热力图"""
    if len(df) == 0:
        ax.text(0.5, 0.5, '无数据', ha='center', va='center', fontsize=12)
        ax.set_title('工作强度热力图')
        return
    
    pivot_data = df.pivot_table(
        values='工时 h',
        index='成员_中文',
        columns=df['日期'].dt.strftime('%m-%d'),
        aggfunc='sum',
        fill_value=0
    )
    
    im = ax.imshow(pivot_data.values, cmap='YlOrRd', aspect='auto')
    
    ax.set_xticks(range(len(pivot_data.columns)))
    ax.set_xticklabels(pivot_data.columns, rotation=45, ha='right')
    ax.set_yticks(range(len(pivot_data.index)))
    ax.set_yticklabels(pivot_data.index)
    ax.set_title('工作强度热力图')
    
    plt.colorbar(im, ax=ax, shrink=0.8, label='工时')
    
    # 添加数值标注
    for i in range(len(pivot_data.index)):
        for j in range(len(pivot_data.columns)):
            value = pivot_data.iloc[i, j]
            if value > 0:
                color = 'white' if value > pivot_data.values.max()/2 else 'black'
                ax.text(j, i, f'{value:.1f}', ha='center', va='center',
                       color=color, fontsize=8)


def create_single_chart(
    chart_type: str,
    df: pd.DataFrame = None,
    member_results: List = None,
    project_results: List = None,
    figsize: Tuple[int, int] = (10, 6)
) -> plt.Figure:
    """
    创建单个图表
    
    Parameters
    ----------
    chart_type : str
        图表类型：'member_hours', 'project_pie', 'daily_trend', 
                  'achievement_rate', 'attribute', 'heatmap'
    
    Returns
    -------
    plt.Figure
        图表对象
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    if chart_type == 'member_hours' and member_results:
        _plot_member_hours(ax, member_results)
    elif chart_type == 'project_pie' and project_results:
        _plot_project_pie(ax, project_results)
    elif chart_type == 'daily_trend' and df is not None:
        _plot_daily_trend(ax, df)
    elif chart_type == 'achievement_rate' and member_results:
        _plot_achievement_rate(ax, member_results)
    elif chart_type == 'attribute' and df is not None:
        _plot_attribute_distribution(ax, df)
    elif chart_type == 'heatmap' and df is not None:
        _plot_heatmap(ax, df)
    else:
        ax.text(0.5, 0.5, '无法生成图表', ha='center', va='center')
    
    plt.tight_layout()
    return fig

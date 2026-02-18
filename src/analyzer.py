"""
分析引擎模块

提供各种工时分析功能
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_employees_config
from src.holiday_helper import HolidayHelper, get_week_standard_hours
from src.preprocessor import get_employee_leaves


@dataclass
class MemberAnalysis:
    """成员分析结果"""
    name: str
    name_en: str
    type: str  # 全职/兼职/按需
    total_hours: float
    standard_hours: Optional[float]
    achievement_rate: Optional[float]  # 达成率
    daily_avg: float
    task_count: int
    working_days: int
    status: str  # 正常/超负荷/偏低/按需
    department: str
    leave_days: int = 0  # 请假天数


@dataclass  
class ProjectAnalysis:
    """项目分析结果"""
    name: str
    total_hours: float
    percentage: float
    member_count: int
    task_count: int
    attribute: str  # 项目属性
    priority: str  # 优先级


class TimesheetAnalyzer:
    """
    工时分析引擎
    
    提供：
    - 成员工时分析
    - 项目投入分析
    - 工作阶段分析
    - 趋势分析
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化分析器
        
        Parameters
        ----------
        df : pd.DataFrame
            预处理后的工时数据
        """
        self.df = df
        self.config = get_employees_config()
        self.defaults = self.config.get('defaults', {})
        self.holiday_helper = HolidayHelper()
    
    def analyze_members(
        self,
        period: str = "本周",
        consider_holidays: bool = True,
        consider_leaves: bool = True
    ) -> List[MemberAnalysis]:
        """
        分析成员工时
        
        Parameters
        ----------
        period : str
            分析周期，"本周"/"下周"/"往期"
        consider_holidays : bool
            是否考虑节假日调整标准工时
        consider_leaves : bool
            是否考虑请假
        
        Returns
        -------
        List[MemberAnalysis]
            成员分析结果列表
        """
        df_period = self.df[self.df['周期类型'] == period].copy()
        
        if len(df_period) == 0:
            return []
        
        # 获取日期范围
        date_range = (df_period['日期_date'].min(), df_period['日期_date'].max())
        
        # 计算周标准工时（考虑节假日）
        week_standard = None
        if consider_holidays and len(df_period) > 0:
            sample_date = df_period['日期_date'].iloc[0]
            iso_year, iso_week = sample_date.isocalendar()[:2]
            week_standard = get_week_standard_hours(iso_year, iso_week)
        
        results = []
        thresholds = self.defaults.get('thresholds', {'overload': 1.2, 'underload': 0.7})
        
        for member in df_period['成员_中文'].unique():
            member_data = df_period[df_period['成员_中文'] == member]
            
            # 基本统计
            total_hours = member_data['工时 h'].sum()
            task_count = len(member_data)
            working_days = member_data['日期_date'].nunique()
            daily_avg = total_hours / working_days if working_days > 0 else 0
            
            # 获取员工配置
            emp_type = member_data['员工类型'].iloc[0]
            base_standard = member_data['标准工时'].iloc[0]
            department = member_data['部门'].iloc[0] if '部门' in member_data.columns else ''

            # 获取入职日期
            onboard_date_str = None
            if '入职日期' in member_data.columns:
                onboard_date_str = member_data['入职日期'].iloc[0]

            # 计算实际标准工时（考虑节假日和请假）
            standard_hours = base_standard
            leave_days = 0
            daily_hours = self.defaults.get('daily_hours', 8)

            if standard_hours and consider_holidays and week_standard:
                # 调整为节假日后的标准工时比例
                ratio = week_standard / 40  # 假设基准是40小时/周
                standard_hours = base_standard * ratio

            # 考虑入职日期：如果员工在分析周期内入职，扣除入职前的工作日
            if standard_hours and onboard_date_str:
                try:
                    onboard_dt = datetime.strptime(str(onboard_date_str), '%Y-%m-%d').date()
                    if onboard_dt > date_range[0]:
                        # 入职日期在分析周期内（或之后），需要调整
                        if onboard_dt > date_range[1]:
                            # 入职日期在分析周期之后，标准工时为 0
                            standard_hours = 0
                        else:
                            # 计算入职前的工作日数
                            days_before = 0
                            d = date_range[0]
                            while d < onboard_dt:
                                if self.holiday_helper.is_workday(d):
                                    days_before += 1
                                d += timedelta(days=1)
                            standard_hours -= days_before * daily_hours
                            standard_hours = max(0, standard_hours)
                except (ValueError, TypeError):
                    pass  # 日期格式无效则忽略

            if standard_hours and consider_leaves:
                # 计算请假天数
                leaves = get_employee_leaves(member, date_range[0], date_range[1])
                leave_days = sum(l['days'] for l in leaves)
                # 减去请假时间
                standard_hours -= leave_days * daily_hours
                standard_hours = max(0, standard_hours)  # 不能为负
            
            # 计算达成率和状态
            achievement_rate = None
            status = "🔄 按需"
            
            if standard_hours and standard_hours > 0:
                achievement_rate = total_hours / standard_hours
                
                if achievement_rate >= thresholds['overload']:
                    status = "⚠️ 超负荷"
                elif achievement_rate <= thresholds['underload']:
                    status = "📉 偏低"
                else:
                    status = "✅ 正常"
            
            # 获取英文名
            name_en = member_data['成员_原始'].iloc[0] if '成员_原始' in member_data.columns else member
            
            results.append(MemberAnalysis(
                name=member,
                name_en=name_en,
                type=emp_type,
                total_hours=round(total_hours, 1),
                standard_hours=round(standard_hours, 1) if standard_hours else None,
                achievement_rate=round(achievement_rate * 100, 1) if achievement_rate else None,
                daily_avg=round(daily_avg, 1),
                task_count=task_count,
                working_days=working_days,
                status=status,
                department=department,
                leave_days=leave_days
            ))
        
        # 按总工时降序排列
        results.sort(key=lambda x: x.total_hours, reverse=True)
        
        return results
    
    def analyze_projects(self, period: str = "本周") -> List[ProjectAnalysis]:
        """
        分析项目工时投入
        
        Parameters
        ----------
        period : str
            分析周期
        
        Returns
        -------
        List[ProjectAnalysis]
            项目分析结果列表
        """
        df_period = self.df[self.df['周期类型'] == period].copy()
        
        if len(df_period) == 0:
            return []
        
        total_hours = df_period['工时 h'].sum()
        
        results = []
        
        for project in df_period['项目名称_清理'].unique():
            project_data = df_period[df_period['项目名称_清理'] == project]
            
            hours = project_data['工时 h'].sum()
            percentage = (hours / total_hours * 100) if total_hours > 0 else 0
            
            # 获取项目属性和优先级
            attribute = project_data['项目属性'].iloc[0] if '项目属性' in project_data.columns else '未分类'
            priority = project_data['优先级'].iloc[0] if '优先级' in project_data.columns else '中'
            
            results.append(ProjectAnalysis(
                name=project,
                total_hours=round(hours, 1),
                percentage=round(percentage, 1),
                member_count=project_data['成员_中文'].nunique(),
                task_count=len(project_data),
                attribute=attribute if pd.notna(attribute) else '未分类',
                priority=priority if pd.notna(priority) else '中'
            ))
        
        # 按工时降序排列
        results.sort(key=lambda x: x.total_hours, reverse=True)
        
        return results
    
    def analyze_by_attribute(self, period: str = "本周") -> Dict[str, float]:
        """按项目属性分析工时分布"""
        df_period = self.df[self.df['周期类型'] == period].copy()
        
        if '项目属性' not in df_period.columns or len(df_period) == 0:
            return {}
        
        return df_period.groupby('项目属性')['工时 h'].sum().to_dict()
    
    def analyze_by_priority(self, period: str = "本周") -> Dict[str, float]:
        """按优先级分析工时分布"""
        df_period = self.df[self.df['周期类型'] == period].copy()
        
        if '优先级' not in df_period.columns or len(df_period) == 0:
            return {}
        
        return df_period.groupby('优先级')['工时 h'].sum().to_dict()
    
    def analyze_by_stage(self, period: str = "本周") -> Dict[str, float]:
        """按工作阶段分析工时分布"""
        df_period = self.df[self.df['周期类型'] == period].copy()
        
        if '工作阶段' not in df_period.columns or len(df_period) == 0:
            return {}
        
        return df_period.groupby('工作阶段')['工时 h'].sum().to_dict()
    
    def analyze_daily_trend(self, period: str = "本周") -> pd.Series:
        """分析每日工时趋势"""
        df_period = self.df[self.df['周期类型'] == period].copy()
        
        if len(df_period) == 0:
            return pd.Series(dtype=float)
        
        return df_period.groupby('日期')['工时 h'].sum().sort_index()
    
    def get_summary(self, period: str = "本周") -> Dict:
        """
        获取周期汇总信息
        
        Returns
        -------
        dict
            包含 total_hours, working_days, project_count, member_count 等
        """
        df_period = self.df[self.df['周期类型'] == period].copy()
        
        if len(df_period) == 0:
            return {
                'total_hours': 0,
                'working_days': 0,
                'project_count': 0,
                'member_count': 0,
                'task_count': 0,
                'date_range': None
            }
        
        return {
            'total_hours': round(df_period['工时 h'].sum(), 1),
            'working_days': df_period['日期_date'].nunique(),
            'project_count': df_period['项目名称_清理'].nunique(),
            'member_count': df_period['成员_中文'].nunique(),
            'task_count': len(df_period),
            'date_range': (
                df_period['日期_date'].min().strftime('%Y-%m-%d'),
                df_period['日期_date'].max().strftime('%Y-%m-%d')
            )
        }
    
    def generate_insights(self, period: str = "本周") -> List[Dict]:
        """
        生成分析洞察
        
        Returns
        -------
        List[Dict]
            洞察列表，每条包含 type, title, content, severity
        """
        insights = []
        
        member_results = self.analyze_members(period)
        project_results = self.analyze_projects(period)
        summary = self.get_summary(period)
        
        if not member_results:
            return insights
        
        # 1. 超负荷预警
        overloaded = [m for m in member_results if '超负荷' in m.status]
        if overloaded:
            insights.append({
                'type': 'warning',
                'title': '⚠️ 超负荷预警',
                'content': f"{len(overloaded)} 人工作负荷过重：" + 
                          ", ".join([f"{m.name}({m.achievement_rate}%)" for m in overloaded]),
                'severity': 'high'
            })
        
        # 2. 资源优化建议
        underloaded = [m for m in member_results if '偏低' in m.status]
        if underloaded:
            available = sum(
                (m.standard_hours - m.total_hours) 
                for m in underloaded 
                if m.standard_hours
            )
            insights.append({
                'type': 'opportunity',
                'title': '📈 资源优化机会',
                'content': f"{len(underloaded)} 人有富余产能，共可承接约 {available:.0f} 小时任务",
                'severity': 'medium'
            })
        
        # 3. 项目集中度分析
        if project_results and summary['total_hours'] > 0:
            top3_hours = sum(p.total_hours for p in project_results[:3])
            top3_ratio = top3_hours / summary['total_hours'] * 100
            
            if top3_ratio > 70:
                insights.append({
                    'type': 'risk',
                    'title': '🎯 资源集中度风险',
                    'content': f"TOP3 项目占比 {top3_ratio:.0f}%，建议分散风险",
                    'severity': 'medium'
                })
        
        # 4. 协作项目分析
        collaborative = [p for p in project_results if p.member_count > 1]
        if collaborative:
            insights.append({
                'type': 'info',
                'title': '🤝 团队协作',
                'content': f"{len(collaborative)} 个项目有多人协作",
                'severity': 'low'
            })

        return insights

    def generate_ai_insights(
        self,
        period: str = "本周",
        api_key: Optional[str] = None
    ):
        """
        使用 Claude AI 生成深度洞察

        Parameters
        ----------
        period : str
            分析周期
        api_key : str, optional
            API Key，不提供则从环境变量读取

        Returns
        -------
        AIInsightResult or None
            AI 分析结果，如果 AI 不可用则返回 None
        """
        try:
            from src.ai_analyzer import get_ai_analyzer
        except ImportError:
            return None

        ai_analyzer = get_ai_analyzer(api_key)

        if ai_analyzer is None:
            return None

        member_results = self.analyze_members(period)
        project_results = self.analyze_projects(period)
        summary = self.get_summary(period)

        return ai_analyzer.analyze(
            df=self.df,
            member_results=member_results,
            project_results=project_results,
            summary=summary,
            period=period
        )

    def generate_quick_scan(self, period: str = "本周"):
        """
        快速扫视分析（本地计算，无需 API）

        Parameters
        ----------
        period : str
            分析周期

        Returns
        -------
        QuickScanResult
            快速扫视结果
        """
        try:
            from src.ai_analyzer import AIAnalyzer, QuickScanResult
        except ImportError:
            # 如果导入失败，返回空结果
            return None

        member_results = self.analyze_members(period)
        project_results = self.analyze_projects(period)
        summary = self.get_summary(period)

        # 创建一个临时分析器实例（不需要 API Key）
        # 使用静态方法风格调用
        analyzer = AIAnalyzer.__new__(AIAnalyzer)
        analyzer.config = self.config

        return analyzer.generate_quick_scan(
            df=self.df,
            member_results=member_results,
            project_results=project_results,
            summary=summary,
            period=period
        )

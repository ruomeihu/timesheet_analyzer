"""
数据预处理模块

负责清洗、转换原始工时数据
"""
import pandas as pd
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_employees_config
from src.holiday_helper import HolidayHelper


def preprocess_data(
    df: pd.DataFrame,
    reference_date: Optional[date] = None
) -> Tuple[pd.DataFrame, Dict]:
    """
    预处理工时数据
    
    Parameters
    ----------
    df : pd.DataFrame
        原始数据
    reference_date : date, optional
        参考日期（用于判断"本周"/"下周"），默认为今天
    
    Returns
    -------
    Tuple[pd.DataFrame, Dict]
        (处理后的数据, 元信息)
    """
    df = df.copy()
    
    # 1. 日期处理
    df['日期'] = pd.to_datetime(df['日期'])
    df['日期_date'] = df['日期'].dt.date
    
    # 2. 成员名称标准化
    df = _standardize_member_names(df)
    
    # 3. 项目名称清理
    df = _clean_project_names(df)
    
    # 4. 添加周期信息
    if reference_date is None:
        reference_date = date.today()
    df = _add_period_info(df, reference_date)

    # 4.5 剔除已离职成员（离职生效周及之后整周不出现）
    df = _filter_departed_members(df, reference_date)

    # 5. 添加员工配置信息
    df = _add_employee_info(df)
    
    # 生成元信息
    meta = {
        'reference_date': reference_date,
        'date_range': (df['日期_date'].min(), df['日期_date'].max()),
        'total_records': len(df),
        'unique_members': df['成员_中文'].nunique(),
        'unique_projects': df['项目名称_清理'].nunique()
    }
    
    return df, meta


def _standardize_member_names(df: pd.DataFrame) -> pd.DataFrame:
    """标准化成员名称，添加中文名"""
    config = get_employees_config()
    
    # 创建英文名 -> 中文名的映射
    name_mapping = {}
    for emp in config.get('employees', []):
        name_en = emp.get('name_en', '').lower().strip()
        name_cn = emp.get('name_cn', emp.get('name_en', ''))
        name_mapping[name_en] = name_cn
    
    def get_cn_name(name: str) -> str:
        """获取中文名"""
        if pd.isna(name):
            return "未知"
        name_lower = name.lower().strip()
        return name_mapping.get(name_lower, name)
    
    df['成员_中文'] = df['成员'].apply(get_cn_name)
    df['成员_原始'] = df['成员']
    
    return df


def _clean_project_names(df: pd.DataFrame) -> pd.DataFrame:
    """清理项目名称，去除 Notion 链接"""
    
    def clean_name(name: str) -> str:
        if pd.isna(name):
            return "未分类"
        # 去除 Notion 链接部分
        # 格式：项目名称 (https://www.notion.so/xxx)
        cleaned = re.sub(r'\s*\(https?://[^\)]+\)', '', str(name))
        return cleaned.strip() or "未分类"
    
    # 处理项目名称字段（可能叫不同的名字）
    project_col = None
    for col in ['MIH Projects 项目库', '项目名称', '项目']:
        if col in df.columns:
            project_col = col
            break
    
    if project_col:
        df['项目名称_清理'] = df[project_col].apply(clean_name)
    else:
        df['项目名称_清理'] = "未分类"
    
    return df


def _add_period_info(df: pd.DataFrame, reference_date: date) -> pd.DataFrame:
    """添加周期信息（本周/下周/往期）"""
    helper = HolidayHelper()
    
    # 获取参考日期的周信息
    ref_info = helper.get_date_week_info(reference_date)
    current_week = ref_info['week_num']
    current_year = ref_info['year']
    
    def get_period(row_date: date) -> str:
        """判断周期类型"""
        info = helper.get_date_week_info(row_date)
        
        if info['year'] == current_year:
            if info['week_num'] == current_week:
                return "本周"
            elif info['week_num'] == current_week + 1:
                return "下周"
            elif info['week_num'] < current_week:
                return "往期"
            else:
                return "未来"
        elif info['year'] < current_year:
            return "往期"
        else:
            return "未来"
    
    df['周期类型'] = df['日期_date'].apply(get_period)
    
    # 添加 ISO 周信息
    df['ISO年'] = df['日期_date'].apply(lambda d: d.isocalendar()[0])
    df['ISO周'] = df['日期_date'].apply(lambda d: d.isocalendar()[1])
    df['星期'] = df['日期_date'].apply(
        lambda d: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][d.weekday()]
    )
    
    return df


def _filter_departed_members(df: pd.DataFrame, reference_date: date) -> pd.DataFrame:
    """剔除已离职成员的全部工时行。

    判定按「报告周」粒度而非按行日期：只要成员的 offboard_date 落在
    reference_date 所属 ISO 周（含）或更早，就把该成员在本 DataFrame 里的
    全部行剔除——即离职生效周及之后整周不出现（含其离职前几天的工时）。
    离职生效周之前的周（如重生旧报告）不受影响。

    offboard_date 语义 = 离职生效日（含），与 onboard_date（首个在职日，含）对称。
    """
    config = get_employees_config()

    # name_cn -> offboard_date（仅取配置了该字段的员工）
    offboard_map = {}
    for emp in config.get('employees', []):
        raw = emp.get('offboard_date')
        if not raw:
            continue
        try:
            offboard_map[emp.get('name_cn', '')] = (
                datetime.strptime(str(raw), '%Y-%m-%d').date()
            )
        except (ValueError, TypeError):
            continue  # 日期格式无效则忽略，不影响其他成员

    if not offboard_map:
        return df

    # 报告周的周日（ISO 周一为首日）
    week_monday = reference_date - timedelta(days=reference_date.weekday())
    week_sunday = week_monday + timedelta(days=6)

    departed = [
        name for name, off_date in offboard_map.items()
        if off_date <= week_sunday
    ]
    if not departed:
        return df

    return df[~df['成员_中文'].isin(departed)].copy()


def _add_employee_info(df: pd.DataFrame) -> pd.DataFrame:
    """添加员工配置信息"""
    config = get_employees_config()
    defaults = config.get('defaults', {})
    
    # 创建员工信息映射
    emp_info = {}
    for emp in config.get('employees', []):
        name_cn = emp.get('name_cn', '')
        emp_info[name_cn] = {
            'type': emp.get('type', '按需'),
            'standard_hours': emp.get('standard_hours'),
            'department': emp.get('department', ''),
            'leaves': emp.get('leaves', []),
            'onboard_date': emp.get('onboard_date')
        }
    
    def get_emp_type(name: str) -> str:
        return emp_info.get(name, {}).get('type', '按需')
    
    def get_standard_hours(name: str) -> Optional[float]:
        return emp_info.get(name, {}).get('standard_hours')
    
    def get_department(name: str) -> str:
        return emp_info.get(name, {}).get('department', '')

    def get_onboard_date(name: str) -> Optional[str]:
        return emp_info.get(name, {}).get('onboard_date')

    df['员工类型'] = df['成员_中文'].apply(get_emp_type)
    df['标准工时'] = df['成员_中文'].apply(get_standard_hours)
    df['部门'] = df['成员_中文'].apply(get_department)
    df['入职日期'] = df['成员_中文'].apply(get_onboard_date)

    return df


def filter_by_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """按周期过滤数据"""
    return df[df['周期类型'] == period].copy()


def get_employee_leaves(
    employee_name: str,
    start_date: date,
    end_date: date
) -> List[Dict]:
    """
    获取员工在指定期间的请假记录
    
    Returns
    -------
    List[Dict]
        请假记录列表，每条包含 start, end, type, days
    """
    config = get_employees_config()
    
    for emp in config.get('employees', []):
        if emp.get('name_cn') == employee_name:
            leaves = emp.get('leaves', [])
            filtered = []
            
            for leave in leaves:
                leave_start = datetime.strptime(leave['start'], '%Y-%m-%d').date()
                leave_end = datetime.strptime(leave['end'], '%Y-%m-%d').date()
                
                # 检查是否与查询期间重叠
                if leave_start <= end_date and leave_end >= start_date:
                    # 计算在查询期间内的请假天数
                    actual_start = max(leave_start, start_date)
                    actual_end = min(leave_end, end_date)
                    days = (actual_end - actual_start).days + 1
                    
                    filtered.append({
                        'start': actual_start,
                        'end': actual_end,
                        'type': leave.get('type', '请假'),
                        'days': days
                    })
            
            return filtered
    
    return []

"""
节假日处理模块

处理中国法定节假日、调休工作日的判断
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_holidays_config


class HolidayHelper:
    """
    节假日助手类
    
    处理：
    - 判断某天是否为工作日/假日
    - 计算某周的实际工作天数
    - 计算考虑节假日后的标准工时
    """
    
    def __init__(self):
        """初始化，加载节假日配置"""
        self._config = get_holidays_config()
        self._holidays = {}  # {date: {'name': str, 'type': str}}
        self._parse_config()
    
    def _parse_config(self):
        """解析配置文件"""
        holidays_data = self._config.get('holidays', {})
        
        for year, items in holidays_data.items():
            for item in items:
                d = datetime.strptime(item['date'], '%Y-%m-%d').date()
                self._holidays[d] = {
                    'name': item['name'],
                    'type': item['type']  # 'holiday' or 'workday'
                }
    
    def is_holiday(self, d: date) -> bool:
        """
        判断是否为假日（不上班）
        
        包括：法定假日 + 普通周末（非调休）
        """
        # 检查是否为法定假日
        if d in self._holidays:
            return self._holidays[d]['type'] == 'holiday'
        
        # 检查是否为普通周末
        return d.weekday() >= 5  # 5=周六, 6=周日
    
    def is_workday(self, d: date) -> bool:
        """
        判断是否为工作日
        
        包括：普通工作日（周一到周五）+ 调休工作日
        """
        # 检查是否为调休工作日
        if d in self._holidays:
            return self._holidays[d]['type'] == 'workday'
        
        # 检查是否为普通工作日
        return d.weekday() < 5
    
    def get_holiday_info(self, d: date) -> Optional[Dict]:
        """获取某天的假日信息（如果有）"""
        return self._holidays.get(d)
    
    def get_week_workdays(self, year: int, week_num: int) -> List[date]:
        """
        获取某周的所有工作日列表
        
        Parameters
        ----------
        year : int
            年份
        week_num : int
            ISO 周数
        
        Returns
        -------
        List[date]
            该周所有工作日
        """
        # 计算该周的周一日期
        jan_4 = date(year, 1, 4)  # ISO 标准：1月4日一定在第1周
        week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
        target_monday = week_1_monday + timedelta(weeks=week_num - 1)
        
        workdays = []
        for i in range(7):  # 周一到周日
            d = target_monday + timedelta(days=i)
            if self.is_workday(d):
                workdays.append(d)
        
        return workdays
    
    def get_week_standard_hours(
        self, 
        year: int, 
        week_num: int,
        daily_hours: float = 8.0
    ) -> float:
        """
        计算某周的标准工时（考虑节假日）
        
        Parameters
        ----------
        year : int
            年份
        week_num : int
            ISO 周数
        daily_hours : float
            日标准工时，默认 8 小时
        
        Returns
        -------
        float
            该周标准工时
        """
        workdays = self.get_week_workdays(year, week_num)
        return len(workdays) * daily_hours
    
    def get_date_week_info(self, d: date) -> Dict:
        """
        获取某个日期的周信息
        
        Returns
        -------
        dict
            包含 year, week_num, weekday, is_workday, holiday_info
        """
        iso_cal = d.isocalendar()
        
        return {
            'year': iso_cal[0],  # ISO 年
            'week_num': iso_cal[1],  # ISO 周数
            'weekday': iso_cal[2],  # 周几 (1=周一, 7=周日)
            'weekday_cn': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][iso_cal[2] - 1],
            'is_workday': self.is_workday(d),
            'is_holiday': self.is_holiday(d),
            'holiday_info': self.get_holiday_info(d)
        }
    
    def get_period_summary(
        self, 
        start_date: date, 
        end_date: date
    ) -> Dict:
        """
        获取一段时期的工作日统计
        
        Returns
        -------
        dict
            包含 total_days, workdays, holidays, special_days
        """
        total_days = (end_date - start_date).days + 1
        workdays = 0
        holidays = 0
        special_days = []  # 调休或法定假日
        
        current = start_date
        while current <= end_date:
            if self.is_workday(current):
                workdays += 1
            else:
                holidays += 1
            
            if current in self._holidays:
                info = self._holidays[current]
                special_days.append({
                    'date': current,
                    'name': info['name'],
                    'type': info['type']
                })
            
            current += timedelta(days=1)
        
        return {
            'total_days': total_days,
            'workdays': workdays,
            'holidays': holidays,
            'special_days': special_days
        }


# 便捷函数
_helper = None

def get_helper() -> HolidayHelper:
    """获取单例 HolidayHelper"""
    global _helper
    if _helper is None:
        _helper = HolidayHelper()
    return _helper


def is_workday(d: date) -> bool:
    """判断是否为工作日"""
    return get_helper().is_workday(d)


def get_week_standard_hours(year: int, week_num: int, daily_hours: float = 8.0) -> float:
    """获取某周标准工时"""
    return get_helper().get_week_standard_hours(year, week_num, daily_hours)

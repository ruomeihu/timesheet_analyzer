"""
数据加载模块

负责从 CSV 文件加载 Notion 导出的工时数据
"""
import pandas as pd
from pathlib import Path
from typing import Union, Optional
import io


def load_timesheet(
    source: Union[str, Path, io.BytesIO],
    encoding: str = 'utf-8-sig'
) -> pd.DataFrame:
    """
    加载工时数据 CSV 文件
    
    Parameters
    ----------
    source : str, Path, or BytesIO
        CSV 文件路径或上传的文件对象（Streamlit）
    encoding : str
        文件编码，默认 'utf-8-sig'（处理 BOM）
    
    Returns
    -------
    pd.DataFrame
        原始工时数据
    
    Raises
    ------
    FileNotFoundError
        文件不存在
    ValueError
        文件格式错误
    
    Examples
    --------
    >>> df = load_timesheet('data/timesheet.csv')
    >>> df = load_timesheet(uploaded_file)  # Streamlit 上传
    """
    try:
        # 处理不同输入类型
        if isinstance(source, io.BytesIO):
            df = pd.read_csv(source, encoding=encoding)
        else:
            filepath = Path(source)
            if not filepath.exists():
                raise FileNotFoundError(f"文件不存在: {filepath}")
            df = pd.read_csv(filepath, encoding=encoding)
        
        # 验证必要字段
        required_columns = ['成员', '日期', '工时 h']
        missing = [col for col in required_columns if col not in df.columns]
        
        if missing:
            raise ValueError(f"CSV 缺少必要字段: {missing}")
        
        return df
        
    except pd.errors.EmptyDataError:
        raise ValueError("CSV 文件为空")
    except pd.errors.ParserError as e:
        raise ValueError(f"CSV 解析错误: {e}")


def validate_data(df: pd.DataFrame) -> dict:
    """
    验证数据质量
    
    Returns
    -------
    dict
        验证结果，包含 valid (bool) 和 issues (list)
    """
    issues = []
    
    # 检查空值
    null_counts = df[['成员', '日期', '工时 h']].isnull().sum()
    for col, count in null_counts.items():
        if count > 0:
            issues.append(f"'{col}' 列有 {count} 个空值")
    
    # 检查工时范围
    if (df['工时 h'] < 0).any():
        issues.append("存在负数工时")
    if (df['工时 h'] > 24).any():
        issues.append("存在单日工时超过 24 小时的记录")
    
    # 检查日期格式
    try:
        pd.to_datetime(df['日期'])
    except Exception:
        issues.append("日期格式异常")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'row_count': len(df),
        'date_range': (df['日期'].min(), df['日期'].max()) if len(df) > 0 else None
    }

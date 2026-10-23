"""
工时分析核心模块

包含：
- data_loader: 数据加载
- preprocessor: 数据预处理
- analyzer: 分析引擎
- visualizer: 可视化
- report_generator: 报告生成
- holiday_helper: 节假日处理

⚠️ 包级导出必须惰性加载：schedule_gate.py 在只装了 pyyaml 的 CI gate job 里
导入 src.holiday_helper，这里若直接 import data_loader 等会拉起 pandas 而崩溃
（2026-09-25 起定时周报/提醒因此连续 4 周未运行）。
"""

from importlib import import_module

_EXPORTS = {
    'load_timesheet': '.data_loader',
    'preprocess_data': '.preprocessor',
    'TimesheetAnalyzer': '.analyzer',
    'create_visualizations': '.visualizer',
    'generate_markdown_report': '.report_generator',
    'HolidayHelper': '.holiday_helper',
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    if name in _EXPORTS:
        return getattr(import_module(_EXPORTS[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

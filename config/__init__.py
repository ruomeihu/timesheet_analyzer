"""
配置模块

提供员工配置和节假日配置的加载功能
"""
from pathlib import Path
import yaml

CONFIG_DIR = Path(__file__).parent


def load_yaml(filename: str) -> dict:
    """加载 YAML 配置文件"""
    filepath = CONFIG_DIR / filename
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_employees_config() -> dict:
    """获取员工配置"""
    return load_yaml('employees.yaml')


def get_holidays_config() -> dict:
    """获取节假日配置"""
    return load_yaml('holidays.yaml')

"""
配置模块

提供员工配置和节假日配置的加载功能
"""
from pathlib import Path
import yaml

CONFIG_DIR = Path(__file__).parent
EMPLOYEES_FILE = CONFIG_DIR / 'employees.yaml'


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


def add_leave_to_yaml_text(yaml_text: str, name_cn: str, start: str, end: str,
                           leave_type: str, note: str = "") -> str:
    """
    纯文本变换：在 employees.yaml 内容中给指定员工追加一条请假记录。

    不触碰文件系统，保留原内容的注释和格式（ruamel round-trip）。
    GitHub 同步路径用它对仓库最新内容做变换，本地写入路径同样复用。

    Parameters
    ----------
    yaml_text : str
        employees.yaml 的完整文本内容
    name_cn : str
        员工中文名（与 employees.yaml 中 name_cn 一致）
    start, end : str
        起止日期，格式 YYYY-MM-DD
    leave_type : str
        请假类型：年假 / 病假 / 事假 / 调休
    note : str, optional
        备注，空字符串时不写入 note 字段

    Returns
    -------
    str
        追加请假记录后的 yaml 文本

    Raises
    ------
    ValueError
        name_cn 在员工列表中不存在
    """
    import io
    from ruamel.yaml import YAML
    from ruamel.yaml.scalarstring import DoubleQuotedScalarString as DQ

    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    yaml_rt.allow_unicode = True
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    yaml_rt.width = 4096  # 防止长行被换行打断

    data = yaml_rt.load(io.StringIO(yaml_text))

    target = None
    for emp in data.get('employees', []):
        if emp.get('name_cn') == name_cn:
            target = emp
            break
    if target is None:
        raise ValueError(f"未找到员工 name_cn={name_cn}")

    new_leave = {
        'start': DQ(start),
        'end': DQ(end),
        'type': DQ(leave_type),
    }
    if note:
        new_leave['note'] = DQ(note)

    leaves = target.get('leaves')
    if leaves is None:
        target['leaves'] = [new_leave]
    else:
        leaves.append(new_leave)

    buf = io.StringIO()
    yaml_rt.dump(data, buf)
    return buf.getvalue()


def add_employee_leave(name_cn: str, start: str, end: str, leave_type: str, note: str = "") -> None:
    """
    向 employees.yaml 中指定员工追加一条请假记录，保留原文件注释和格式。

    Parameters
    ----------
    name_cn : str
        员工中文名（与 employees.yaml 中 name_cn 一致）
    start, end : str
        起止日期，格式 YYYY-MM-DD
    leave_type : str
        请假类型：年假 / 病假 / 事假 / 调休
    note : str, optional
        备注，空字符串时不写入 note 字段
    """
    with open(EMPLOYEES_FILE, 'r', encoding='utf-8') as f:
        yaml_text = f.read()

    new_text = add_leave_to_yaml_text(yaml_text, name_cn, start, end, leave_type, note)

    with open(EMPLOYEES_FILE, 'w', encoding='utf-8') as f:
        f.write(new_text)

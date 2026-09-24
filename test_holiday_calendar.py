#!/usr/bin/env python3
"""
节假日日历 + 定时任务门控测试。

依赖 config/holidays.yaml 中 2026 年：
  - 9/20（周日）国庆调休上班
  - 9/25-9/27 中秋放假
  - 10/1-10/7 国庆放假，10/10（周六）调休上班

测试范围：
  - HolidayHelper：get_day_type / get_week_calendar / get_last_workday_of_week / count_workdays
  - 请假天数只计工作日（get_employee_leaves）
  - schedule_gate.should_run：reminder / report 两种判定

使用方法：
  python test_holiday_calendar.py
"""

import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import src.preprocessor as preprocessor
from schedule_gate import should_run
from src.holiday_helper import get_helper


def test_day_type():
    h = get_helper()
    assert h.get_day_type(date(2026, 9, 20)) == "调休工作日"
    assert h.get_day_type(date(2026, 9, 25)) == "法定假日"
    assert h.get_day_type(date(2026, 9, 19)) == "周末"
    assert h.get_day_type(date(2026, 9, 24)) == "工作日"
    print("✅ get_day_type")


def test_week_calendar():
    cal = get_helper().get_week_calendar(date(2026, 9, 17))
    assert [d["date"] for d in cal][0] == "2026-09-14" and len(cal) == 7
    sunday = cal[6]
    assert sunday["date"] == "2026-09-20" and sunday["day_type"] == "调休工作日"
    assert sunday["weekday"] == "周日" and sunday["name"] == "国庆调休"
    print("✅ get_week_calendar（9/20 调休工作日）")


def test_last_workday_of_week():
    h = get_helper()
    cases = {
        date(2026, 9, 24): date(2026, 9, 24),   # 中秋周：周四
        date(2026, 9, 18): date(2026, 9, 20),   # 调休周：周日
        date(2026, 9, 30): date(2026, 9, 30),   # 国庆前：周三
        date(2026, 10, 8): date(2026, 10, 10),  # 国庆后：调休周六
        date(2026, 9, 11): date(2026, 9, 11),   # 普通周：周五
    }
    for d, expected in cases.items():
        got = h.get_last_workday_of_week(d)
        assert got == expected, f"{d}: 期望 {expected}，实际 {got}"
    print("✅ get_last_workday_of_week")


def test_leave_counts_workdays_only():
    cfg = {"employees": [{"name_cn": "测试", "leaves": [
        {"start": "2026-09-24", "end": "2026-09-28", "type": "年假"}]}]}
    with patch.object(preprocessor, "get_employees_config", return_value=cfg):
        this_week = preprocessor.get_employee_leaves("测试", date(2026, 9, 21), date(2026, 9, 27))
        whole = preprocessor.get_employee_leaves("测试", date(2026, 9, 21), date(2026, 10, 4))
    assert this_week[0]["days"] == 1, this_week   # 仅 9/24
    assert whole[0]["days"] == 2, whole           # 9/24 + 9/28
    print("✅ 请假只计工作日（9/24-9/28 → 2 天）")


def test_gate_reminder():
    assert should_run("reminder", date(2026, 9, 24))[0] is True
    assert should_run("reminder", date(2026, 9, 25))[0] is False   # 中秋
    assert should_run("reminder", date(2026, 9, 18))[0] is False   # 调休周周五不是最后工作日
    assert should_run("reminder", date(2026, 9, 20))[0] is True
    assert should_run("reminder", date(2026, 10, 10))[0] is True   # 调休周六
    print("✅ schedule_gate reminder")


def test_gate_report():
    with tempfile.TemporaryDirectory() as tmp:
        reports = Path(tmp)
        assert should_run("report", date(2026, 9, 23), reports)[0] is False  # 早于最后工作日
        assert should_run("report", date(2026, 9, 24), reports)[0] is True
        assert should_run("report", date(2026, 9, 25), reports)[0] is True   # cron 延迟跨午夜补跑
        (reports / "report_20260925.json").write_text("{}")                  # 本周 sidecar 用周五命名
        assert should_run("report", date(2026, 9, 24), reports)[0] is False  # 已生成则跳过
        assert should_run("report", date(2026, 9, 26), reports)[0] is False
    print("✅ schedule_gate report")


if __name__ == "__main__":
    test_day_type()
    test_week_calendar()
    test_last_workday_of_week()
    test_leave_counts_workdays_only()
    test_gate_reminder()
    test_gate_report()
    print("\n全部通过")

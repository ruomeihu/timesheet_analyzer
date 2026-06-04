#!/usr/bin/env python3
"""
离职成员剔除测试：preprocess_data 按「报告周」粒度剔除已离职成员。

依赖 config/employees.yaml 中赵启的 offboard_date = 2026-06-05。

测试范围：
  - 报告周 = 2026-06-05（离职生效周）→ 赵启整周被剔除，在职成员保留
  - 报告周 = 2026-05-28（离职前一周）→ 赵启仍保留（历史不被回溯剔除）

使用方法：
  python test_offboard_filter.py
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.preprocessor import preprocess_data


# 赵启 name_en == name_cn == "赵启"；魏超 name_en == "Weichao"
DEPARTED = "赵启"
ACTIVE = "魏超"


def _make_df(rows):
    """rows: list of (成员, 'YYYY-MM-DD', 工时h)"""
    return pd.DataFrame(
        [
            {"成员": m, "日期": d, "工时 h": h, "MIH Projects 项目库": "示例项目"}
            for m, d, h in rows
        ]
    )


def test_departed_excluded_in_offboard_week():
    """报告周 = 离职生效周：赵启整周（含离职前几天）被剔除，魏超保留。"""
    df = _make_df([
        (DEPARTED, "2026-06-01", 8),  # 周一，离职前
        (DEPARTED, "2026-06-02", 8),  # 周二，离职前
        (DEPARTED, "2026-06-03", 8),  # 周三，离职前
        ("Weichao", "2026-06-01", 8),
        ("Weichao", "2026-06-05", 8),
    ])

    processed, meta = preprocess_data(df, reference_date=date(2026, 6, 5))
    members = set(processed["成员_中文"].unique())

    assert DEPARTED not in members, f"离职成员赵启应被剔除，实际: {members}"
    assert ACTIVE in members, f"在职成员魏超应保留，实际: {members}"
    assert meta["unique_members"] == 1, f"unique_members 应为 1，实际 {meta['unique_members']}"
    print(f"  ✅ 离职生效周：赵启已剔除，剩余成员 {members}")


def test_departed_kept_before_offboard_week():
    """报告周 = 离职前一周：赵启仍应出现（历史不被回溯剔除）。"""
    df = _make_df([
        (DEPARTED, "2026-05-25", 8),
        (DEPARTED, "2026-05-26", 8),
        ("Weichao", "2026-05-25", 8),
    ])

    processed, _ = preprocess_data(df, reference_date=date(2026, 5, 28))
    members = set(processed["成员_中文"].unique())

    assert DEPARTED in members, f"离职前一周赵启应保留，实际: {members}"
    assert ACTIVE in members, f"魏超应保留，实际: {members}"
    print(f"  ✅ 离职前一周：赵启正常保留，成员 {members}")


if __name__ == "__main__":
    print("=" * 60)
    print("离职成员剔除测试")
    print("=" * 60)
    test_departed_excluded_in_offboard_week()
    test_departed_kept_before_offboard_week()
    print("=" * 60)
    print("全部通过 ✅")
    print("=" * 60)

#!/usr/bin/env python3
"""
未识别成员剔除测试：preprocess_data 丢弃「成员」无法解析的工时行。

背景：员工离职后 Notion 账号被删除，其工时行的「成员」person 字段会变成
  - name: null   → _get_person_name 返回 None → 成员_中文 = "未知"
  - people 空数组 → 返回 ""，存 CSV 再读 → NaN → 成员_中文 = "未知"
按名字匹配的 offboard 过滤（_filter_departed_members）此时已无法命中，
会漏剔出一个幻影「未知 / 按需」成员。本测试守护这条链路。

「未知」只可能来自删号/空填——未在 yaml 映射的正常人名会原样透传，
绝不会变「未知」，因此整行丢弃是语义安全的。

使用方法：
  python test_unidentified_filter.py
"""

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.preprocessor import preprocess_data


def _make_df(rows):
    """rows: list of (成员, 'YYYY-MM-DD', 工时h)"""
    return pd.DataFrame(
        [
            {"成员": m, "日期": d, "工时 h": h, "MIH Projects 项目库": "示例项目"}
            for m, d, h in rows
        ]
    )


def test_member_name_null_dropped():
    """成员 = None（Notion name=null）的行应被剔除，不得变成「未知」成员。"""
    df = _make_df([
        (None, "2026-06-02", 8),   # 删号成员，name=null
        (None, "2026-06-03", 8),
        ("Weichao", "2026-06-02", 8),
    ])
    processed, meta = preprocess_data(df, reference_date=date(2026, 6, 5))
    members = set(processed["成员_中文"].unique())

    assert "未知" not in members, f"name=null 行应被剔除，实际: {members}"
    assert "魏超" in members, f"在职成员魏超应保留，实际: {members}"
    assert meta["unique_members"] == 1, f"unique_members 应为 1，实际 {meta['unique_members']}"
    print(f"  ✅ name=null：未知行已剔除，剩余成员 {members}")


def test_member_empty_dropped():
    """成员 = 空字符串 / NaN（people 空数组、CSV 往返）的行应被剔除。"""
    df = _make_df([
        ("", "2026-06-02", 8),
        (np.nan, "2026-06-03", 8),
        ("Weichao", "2026-06-02", 8),
    ])
    processed, meta = preprocess_data(df, reference_date=date(2026, 6, 5))
    members = set(processed["成员_中文"].unique())

    assert "未知" not in members and "" not in members, f"空成员行应被剔除，实际: {members}"
    assert "魏超" in members
    assert meta["unique_members"] == 1, f"unique_members 应为 1，实际 {meta['unique_members']}"
    print(f"  ✅ 空/NaN：未知行已剔除，剩余成员 {members}")


def test_unmapped_name_kept():
    """未在 yaml 映射的真实人名应原样保留（不能误杀为未知）。"""
    df = _make_df([
        ("某外部协作者", "2026-06-02", 8),
        ("Weichao", "2026-06-02", 8),
    ])
    processed, _ = preprocess_data(df, reference_date=date(2026, 6, 5))
    members = set(processed["成员_中文"].unique())

    assert "某外部协作者" in members, f"未映射真实人名应保留，实际: {members}"
    assert "魏超" in members
    print(f"  ✅ 未映射人名：原样保留，成员 {members}")


if __name__ == "__main__":
    print("=" * 60)
    print("未识别成员剔除测试")
    print("=" * 60)
    test_member_name_null_dropped()
    test_member_empty_dropped()
    test_unmapped_name_kept()
    print("=" * 60)
    print("全部通过 ✅")
    print("=" * 60)

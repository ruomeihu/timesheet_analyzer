"""
项目进度分析（动量 + 停滞）

给"项目进度概览"提供数据：按项目算本周 vs 上周工时动量、是否停滞、谁在投入。
数据来源是 reports/timesheet_*.csv 每周存档（唯一能拿到"上周"的来源，三种数据源下都可用）。

与 analyzer.py 的区别：analyzer 是单周期单 df 设计；本模块专做跨周聚合。
刻意不走 preprocess_data —— 避开 _filter_departed_members，否则离职成员在
trailing 周的项目历史工时会被错误清零（项目动量需要完整历史）。
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd

from src.preprocessor import _standardize_member_names, _clean_project_names


# 动量阈值
UP_RATIO = 1.15
DOWN_RATIO = 0.85
_PRIORITY_RANK = {"高": 0, "中": 1, "低": 2}


@dataclass
class ProjectProgress:
    name: str
    attribute: str
    priority: str
    this_week_hours: float
    last_week_hours: float
    momentum: str  # 'up' | 'flat' | 'down' | 'new'
    weekly_series: List[Tuple[str, float]]  # [(ISO周标签, 工时), ...] 时间升序
    stalled: bool
    weeks_since_active: int
    last_active_date: Optional[date]
    current_stage: str
    contributors: List[Tuple[str, float]] = field(default_factory=list)        # 本周
    prior_contributors: List[Tuple[str, float]] = field(default_factory=list)  # 停滞时=最后活跃周


def _iso_ordinal(d: date) -> int:
    """把日期映射成可比较/可相减的 ISO 周序号（窗口内同年，足够用）。"""
    y, w, _ = d.isocalendar()
    return y * 53 + w


def _mode(series: pd.Series, default: str = "") -> str:
    s = series.dropna()
    if s.empty:
        return default
    m = s.mode()
    return str(m.iloc[0]) if not m.empty else default


def load_recent_weeks(
    reports_dir: str = "reports",
    n_weeks: int = 4,
    reference_date: Optional[date] = None,
) -> pd.DataFrame:
    """合并最近 n_weeks 周的存档 CSV，去重 + 标准化，返回含 ISO 周字段的 df。

    窗口 = [reference_date 所在周的周一往前 (n_weeks-1) 周, 该周周日]。
    """
    if reference_date is None:
        reference_date = date.today()
    files = sorted(glob.glob(os.path.join(reports_dir, "timesheet_*.csv")))
    if not files:
        return pd.DataFrame()

    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df.drop_duplicates(
        subset=["成员", "日期", "工作内容", "MIH Projects 项目库", "工时 h"]
    )
    df["日期_date"] = pd.to_datetime(df["日期"]).dt.date
    df["工时 h"] = pd.to_numeric(df["工时 h"], errors="coerce").fillna(0.0)

    week_monday = reference_date - timedelta(days=reference_date.weekday())
    window_start = week_monday - timedelta(weeks=n_weeks - 1)
    window_end = week_monday + timedelta(days=6)
    df = df[(df["日期_date"] >= window_start) & (df["日期_date"] <= window_end)].copy()
    if df.empty:
        return df

    df = _standardize_member_names(df)
    df = _clean_project_names(df)
    df["ISO年"] = df["日期_date"].apply(lambda d: d.isocalendar()[0])
    df["ISO周"] = df["日期_date"].apply(lambda d: d.isocalendar()[1])
    for col in ("工作阶段", "优先级", "项目属性"):
        if col not in df.columns:
            df[col] = ""
    return df


def _week_label(iso_year: int, iso_week: int) -> str:
    return f"{iso_year}-W{iso_week:02d}"


def project_progress(
    df: pd.DataFrame,
    reference_date: date,
    n_weeks: int = 4,
) -> List[ProjectProgress]:
    """按项目计算动量 / 停滞 / 投入人。df 来自 load_recent_weeks。"""
    if df is None or df.empty:
        return []

    this_y, this_w, _ = reference_date.isocalendar()
    last_d = reference_date - timedelta(days=7)
    last_y, last_w, _ = last_d.isocalendar()
    this_key, last_key = (this_y, this_w), (last_y, last_w)
    this_ord = _iso_ordinal(reference_date)

    results: List[ProjectProgress] = []
    for proj, pdf in df.groupby("项目名称_清理"):
        weekly = pdf.groupby(["ISO年", "ISO周"])["工时 h"].sum()
        weekly_map = {(int(y), int(w)): round(float(h), 1) for (y, w), h in weekly.items()}
        total = sum(weekly_map.values())
        if total <= 0:
            continue

        this_h = weekly_map.get(this_key, 0.0)
        last_h = weekly_map.get(last_key, 0.0)

        # 活跃周（>0）按时间排序
        active_keys = sorted([k for k, v in weekly_map.items() if v > 0])
        last_active_key = active_keys[-1] if active_keys else None
        last_active_rows = pdf[(pdf["ISO年"] == last_active_key[0]) & (pdf["ISO周"] == last_active_key[1])] if last_active_key else pdf.iloc[0:0]

        stalled = this_h == 0 and any(v > 0 for k, v in weekly_map.items() if k != this_key)
        if last_active_key:
            last_active_date = max(last_active_rows["日期_date"])
            weeks_since_active = this_ord - _iso_ordinal(last_active_date)
        else:
            last_active_date, weeks_since_active = None, 0

        # 动量
        if this_h == 0:
            momentum = "down"  # 停滞也算降温方向，UI 用 stalled 单独标
        elif last_h == 0:
            momentum = "new"
        elif this_h >= UP_RATIO * last_h:
            momentum = "up"
        elif this_h <= DOWN_RATIO * last_h:
            momentum = "down"
        else:
            momentum = "flat"

        # 投入人
        def _contrib(rows) -> List[Tuple[str, float]]:
            g = rows.groupby("成员_中文")["工时 h"].sum().sort_values(ascending=False)
            return [(str(n), round(float(h), 1)) for n, h in g.items() if h > 0]

        this_rows = pdf[(pdf["ISO年"] == this_key[0]) & (pdf["ISO周"] == this_key[1])]
        contributors = _contrib(this_rows)
        prior_contributors = _contrib(last_active_rows) if stalled else []

        # 当前阶段 = 最近活跃周该项目工作阶段众数（背景信息）
        stage_rows = this_rows if not this_rows.empty else last_active_rows
        current_stage = _mode(stage_rows["工作阶段"], default="—")

        weekly_series = [
            (_week_label(y, w), weekly_map[(y, w)])
            for (y, w) in sorted(weekly_map.keys())
        ]

        results.append(ProjectProgress(
            name=str(proj),
            attribute=_mode(pdf["项目属性"], default="未分类"),
            priority=_mode(pdf["优先级"], default="—"),
            this_week_hours=round(this_h, 1),
            last_week_hours=round(last_h, 1),
            momentum=momentum,
            weekly_series=weekly_series,
            stalled=stalled,
            weeks_since_active=weeks_since_active,
            last_active_date=last_active_date,
            current_stage=current_stage,
            contributors=contributors,
            prior_contributors=prior_contributors,
        ))

    # 排序：需要关注优先 —— 停滞 > 降温 > 其余；同级按优先级、再按本周工时
    def _sort_key(p: ProjectProgress):
        bucket = 0 if p.stalled else (1 if p.momentum == "down" else 2)
        return (bucket, _PRIORITY_RANK.get(p.priority, 9), -p.this_week_hours)

    results.sort(key=_sort_key)
    return results


def momentum_arrow(momentum: str, stalled: bool = False) -> str:
    if stalled:
        return "🛑"
    return {"up": "📈 升温", "down": "📉 降温", "flat": "➡️ 平稳", "new": "🆕 新启动"}.get(momentum, "")


def summarize(progress: List[ProjectProgress]) -> dict:
    """顶部一行摘要用。"""
    return {
        "active": len([p for p in progress if not p.stalled]),
        "up": len([p for p in progress if p.momentum == "up" and not p.stalled]),
        "down": len([p for p in progress if p.momentum == "down" and not p.stalled]),
        "stalled": len([p for p in progress if p.stalled]),
        "new": len([p for p in progress if p.momentum == "new"]),
    }


def review_candidates(progress: List[ProjectProgress]) -> List[ProjectProgress]:
    """建议本周和下属过一遍的：停滞 + 降温里优先级高的（其次中）。"""
    cand = [p for p in progress if p.stalled or p.momentum == "down"]
    cand.sort(key=lambda p: (_PRIORITY_RANK.get(p.priority, 9), 0 if p.stalled else 1))
    return [p for p in cand if p.priority in ("高", "中")]

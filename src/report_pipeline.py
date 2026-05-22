"""
报告产物流水线: 把分析结果落盘成 Markdown / 图表 / Gamma PPT / sidecar JSON / PDF。

被 auto_weekly_report.py (CI) 和 app.py (Streamlit 手动重生) 共享调用,
避免逻辑漂移。
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd


def render_report_artifacts(
    *,
    df: pd.DataFrame,
    summary: dict,
    member_results: list,
    project_results: list,
    insights: list,
    next_week_summary: Optional[dict],
    next_week_members: Optional[list],
    next_week_projects: Optional[list],
    ai_insights,
    reference_date: date,
    output_dir: str,
    call_gamma: bool = True,
    source: str = "ci",
) -> dict:
    """生成本周的全套报告产物,覆盖 reports/report_YYYYMMDD.{md,png,json,pdf}。

    Parameters
    ----------
    df : pd.DataFrame
        已预处理的完整 DataFrame (含本周/下周等周期标记)。
    summary, member_results, project_results, insights : 本周分析结果。
    next_week_* : 下周分析结果, 可为 None。
    ai_insights : AIInsightResult | None
        AI 深度分析结果, None 则不附加。
    reference_date : date
        参考日期, 决定文件名日期。
    output_dir : str
        产物目录 (通常是 reports/)。
    call_gamma : bool
        是否调 Gamma 生成在线 PPT。Streamlit 手动重生固定 True;
        测试场景可置 False。
    source : str
        sidecar JSON 里的 source 字段, "ci" 或 "streamlit_manual"。

    Returns
    -------
    dict
        {
          "report_path": str,
          "chart_path": str,
          "sidecar_path": str,
          "gamma_url": str | None,
          "export_url": str | None,
          "pdf_path": str | None,
          "generated_at": str,  # ISO 8601
        }
    """
    from src.report_generator import generate_markdown_report, save_report
    from src.visualizer import create_visualizations
    from src.preprocessor import filter_by_period

    os.makedirs(output_dir, exist_ok=True)
    date_str = reference_date.strftime("%Y%m%d")
    report_path = os.path.join(output_dir, f"report_{date_str}.md")
    chart_path = os.path.join(output_dir, f"chart_{date_str}.png")
    sidecar_path = os.path.join(output_dir, f"report_{date_str}.json")

    report_content = generate_markdown_report(
        summary=summary,
        member_results=member_results,
        project_results=project_results,
        insights=insights,
        next_week_summary=next_week_summary,
        next_week_members=next_week_members,
        next_week_projects=next_week_projects,
        ai_insights=ai_insights,
        df=df,
    )
    save_report(report_content, Path(report_path))

    df_current = filter_by_period(df, "本周")
    if len(df_current) > 0:
        create_visualizations(
            df=df_current,
            member_results=member_results,
            project_results=project_results,
            output_path=Path(chart_path),
        )

    gamma_url: Optional[str] = None
    export_url: Optional[str] = None
    pdf_path: Optional[str] = None
    generation_id: Optional[str] = None

    if call_gamma:
        from src.gamma_client import generate_presentation, download_export

        gamma_result = generate_presentation(report_content)
        if gamma_result:
            gamma_url = gamma_result.get("gammaUrl")
            export_url = gamma_result.get("exportUrl")
            generation_id = gamma_result.get("generationId")
            if export_url:
                pdf_candidate = os.path.join(output_dir, f"report_{date_str}.pdf")
                if download_export(export_url, pdf_candidate):
                    pdf_path = pdf_candidate

    generated_at = datetime.now().isoformat(timespec="seconds")

    ai_payload = None
    if ai_insights is not None:
        from src.ai_analyzer import serialize_ai_insights
        try:
            ai_payload = serialize_ai_insights(ai_insights)
        except Exception:
            ai_payload = None

    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "gammaUrl": gamma_url,
                "exportUrl": export_url,
                "generationId": generation_id,
                "generatedAt": generated_at,
                "source": source,
                "aiInsights": ai_payload,
                "aiInsightsGeneratedAt": generated_at if ai_payload else None,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return {
        "report_path": report_path,
        "chart_path": chart_path,
        "sidecar_path": sidecar_path,
        "gamma_url": gamma_url,
        "export_url": export_url,
        "pdf_path": pdf_path,
        "generated_at": generated_at,
    }

#!/usr/bin/env python3
"""
钉钉周报推送分支选择测试（不发网络请求）。

覆盖：
  - sidecar 完整 → 完整周报 + @所有人
  - sidecar 缺失 → 兜底提示，不 @所有人
  - gate 崩溃（--gate-failed）→ 门控告警；即便本周 sidecar 已存在也绝不重发完整周报

使用方法：
  python test_dingtalk_report_push.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dingtalk_report_push import build_message, is_payload_valid

REF = datetime(2026, 9, 25)
VALID_SIDECAR = json.loads((ROOT / "reports" / "report_20260925.json").read_text(encoding="utf-8"))


def test_valid_sidecar_sends_full_report():
    assert is_payload_valid(VALID_SIDECAR)
    title, text, at_all = build_message(VALID_SIDECAR, 39, REF)
    assert title == "工时周报 · 第 39 周" and at_all is True
    print("✅ sidecar 完整 → 完整周报")


def test_missing_sidecar_sends_fallback():
    title, text, at_all = build_message(None, 39, REF)
    assert "推送失败" in title and at_all is False
    print("✅ sidecar 缺失 → 兜底提示")


def test_gate_failed_never_resends_report():
    run_url = "https://github.com/ruomeihu/timesheet_analyzer/actions/runs/1"
    for sidecar in (VALID_SIDECAR, None):
        title, text, at_all = build_message(sidecar, 39, REF, gate_failed=True, run_url=run_url)
        assert "门控" in title and at_all is False
        assert run_url in text
    print("✅ gate 崩溃 → 门控告警（sidecar 已存在也不重发周报）")


if __name__ == "__main__":
    test_valid_sidecar_sends_full_report()
    test_missing_sidecar_sends_fallback()
    test_gate_failed_never_resends_report()
    print("\n全部通过")

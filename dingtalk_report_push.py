# === 周五工时分析周报钉钉推送 ===
# 目标: 周五 14:00 把本周工时分析 PPT 链接 + 关键数据推到群里 (Markdown + @所有人)
# 数据来源: reports/report_YYYYMMDD.json sidecar (由 13:00 cron 生成)

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv


REPORTS_DIR = Path(__file__).parent / "reports"


def get_reference_date() -> datetime:
    """本周参考日期 = 本周周五 (和 auto_weekly_report.get_week_dates 对齐)。"""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday + timedelta(days=4)


def load_sidecar(reference_date: datetime):
    """读 reports/report_YYYYMMDD.json。文件不存在或 JSON 解析失败返回 None。"""
    sidecar_path = REPORTS_DIR / f"report_{reference_date.strftime('%Y%m%d')}.json"
    if not sidecar_path.exists():
        return None
    try:
        with open(sidecar_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def is_payload_valid(sidecar) -> bool:
    """
    判断 sidecar 是否足以走"完整推送"分支。
    任何一项缺失都走兜底:
      - sidecar 整体读不到
      - gammaUrl 缺失或为空字符串
      - weekStats 字段不存在 (老版 sidecar)
      - weekStats 缺必需子字段
    """
    if not sidecar:
        return False
    if not sidecar.get("gammaUrl"):
        return False
    week_stats = sidecar.get("weekStats")
    if not isinstance(week_stats, dict):
        return False
    required = ("totalHours", "projectCount", "top3Projects", "unalignedHours", "unalignedPct")
    return all(k in week_stats for k in required)


def build_success_markdown(sidecar: dict, week_num: int) -> str:
    stats = sidecar["weekStats"]
    gamma_url = sidecar["gammaUrl"]
    total_hours = stats["totalHours"]
    project_count = stats["projectCount"]
    top3 = stats["top3Projects"]
    unaligned_hours = stats["unalignedHours"]
    unaligned_pct = stats["unalignedPct"]

    if top3:
        top3_lines = "\n".join(
            f"{i + 1}. {p['name']} · {p['hours']} 小时"
            for i, p in enumerate(top3)
        )
    else:
        top3_lines = "_本周暂无项目工时数据_"

    return f"""## 📊 工时周报 · 第 {week_num} 周

@所有人

各位伙伴周五下午好 ☕

本周工时分析已就位 。**📌 这周大家把时间花在哪了**

本周共投入 **{total_hours} 小时**, 涉及 **{project_count}** 个项目。

**项目工时 Top 3** (看资源去向, 不是比谁忙):
{top3_lines}

**🔍 一个值得关注的信号**

本周"未立项/临时指派" 共 **{unaligned_hours} 小时**, 占总工时 **{unaligned_pct}%**。

建议大家对照一下: 这里面有没有可以补立项的日常运营 / 售前工作? 临时事项是真的临时, 还是默认项?

**📈 完整周报 PPT**

👉 [点这里在 Gamma 里看完整分析]({gamma_url})

包含个人工时、项目趋势、下周预估、AI 深度洞察等。

周末愉快, 记得 work-life balance 🌿
工时数据是给我们参考的, 不是给我们卷的。
有任何疑问或想法, 周末 @胡若玫 即可。

下周一见 ✨
"""


def build_fallback_markdown(week_num: int, reference_date: datetime) -> str:
    date_str = reference_date.strftime("%Y%m%d")
    return f"""## ⚠️ 工时周报推送失败 · 第 {week_num} 周

@胡若玫

本周 PPT 生成出现问题, 钉钉机器人无法获取 Gamma 链接。

请人工排查:
1. 检查 GitHub Actions weekly_report.yml 本周运行状态
2. 检查 reports/report_{date_str}.json 是否存在、gammaUrl 字段是否为空
3. 如需团队查看本周工时数据, 可手动分享 Markdown 报告

排查完成后, 可手动触发 dingtalk_report_push workflow 重发本次消息。
"""


def sign_webhook(webhook: str, secret: str) -> str:
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return f"{webhook}&timestamp={timestamp}&sign={sign}"


def main() -> None:
    load_dotenv()
    webhook = os.getenv("DINGTALK_WEBHOOK")
    secret = os.getenv("DINGTALK_SECRET")
    if not webhook or not secret:
        raise ValueError("没读到凭证！检查 DINGTALK_WEBHOOK / DINGTALK_SECRET 环境变量")

    reference_date = get_reference_date()
    week_num = reference_date.isocalendar()[1]

    sidecar = load_sidecar(reference_date)
    valid = is_payload_valid(sidecar)

    if valid:
        text = build_success_markdown(sidecar, week_num)
        title = f"工时周报 · 第 {week_num} 周"
        at_all = True
    else:
        text = build_fallback_markdown(week_num, reference_date)
        title = f"工时周报推送失败 · 第 {week_num} 周"
        at_all = False

    signed_url = sign_webhook(webhook, secret)
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
        "at": {"isAtAll": at_all},
    }

    response = requests.post(signed_url, json=payload, timeout=10)
    print(f"HTTP 状态码: {response.status_code}")
    print(f"钉钉返回: {response.json()}")
    print(f"\n📅 参考日期: {reference_date.strftime('%Y-%m-%d')} (第 {week_num} 周)")
    print(f"📦 推送分支: {'✅ 完整周报' if valid else '⚠️ 兜底提示'}")


if __name__ == "__main__":
    main()

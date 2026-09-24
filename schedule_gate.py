# === 定时任务节假日门控 ===
# 目标: GitHub cron 每天触发, 由本脚本判断「今天该不该跑」, 让周报/提醒跟随
#       「本周最后一个工作日」(考虑法定节假日与调休), 而不是写死周五。
# 用法: python schedule_gate.py reminder|report [--date YYYY-MM-DD]
# 输出: 打印判定原因; 在 GitHub Actions 中写 should_run=true/false 到 $GITHUB_OUTPUT

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.holiday_helper import get_helper

REPORTS_DIR = ROOT / "reports"
BEIJING = ZoneInfo("Asia/Shanghai")


def sidecar_path_for(d: date) -> Path:
    """本周 sidecar 路径 (文件名固定用本周周五, 与 auto_weekly_report.get_week_dates 对齐)"""
    friday = d - timedelta(days=d.weekday()) + timedelta(days=4)
    return REPORTS_DIR / f"report_{friday.strftime('%Y%m%d')}.json"


def should_run(task: str, today: date, reports_dir: Path = REPORTS_DIR) -> tuple:
    """返回 (bool, 原因)。

    reminder: 今天 == 本周最后工作日
    report:   今天 >= 本周最后工作日 (同一 ISO 周内) 且本周 sidecar 尚未生成
              —— cron 延迟跨过午夜也能补跑, 已生成则跳过, 失败则次日自动重试
    """
    last_workday = get_helper().get_last_workday_of_week(today)
    if last_workday is None:
        return False, f"{today} 所在周没有工作日（整周放假），跳过"

    if task == "reminder":
        if today == last_workday:
            return True, f"{today} 是本周最后工作日，发送提醒"
        return False, f"{today} 不是本周最后工作日（{last_workday}），跳过"

    if task == "report":
        if today < last_workday:
            return False, f"{today} 早于本周最后工作日（{last_workday}），跳过"
        sidecar = reports_dir / sidecar_path_for(today).name
        if sidecar.exists():
            return False, f"本周周报已生成（{sidecar.name}），跳过"
        return True, f"{today} 已到本周最后工作日（{last_workday}）且周报未生成，运行"

    raise ValueError(f"未知任务: {task}")


def main() -> None:
    parser = argparse.ArgumentParser(description="定时任务节假日门控")
    parser.add_argument("task", choices=["reminder", "report"])
    parser.add_argument("--date", help="覆盖今天日期（测试用）, YYYY-MM-DD")
    args = parser.parse_args()

    today = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else datetime.now(BEIJING).date()
    )
    run, reason = should_run(args.task, today)
    print(f"{'✅' if run else '⏭️'} [{args.task}] {reason}")

    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"should_run={'true' if run else 'false'}\n")


if __name__ == "__main__":
    main()

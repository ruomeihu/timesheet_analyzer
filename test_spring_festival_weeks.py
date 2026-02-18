#!/usr/bin/env python3
"""
春节假期周测试：Notion 数据拉取 + 节假日判断

测试范围：
  第7周：2026-02-09 ~ 2026-02-15
  第8周：2026-02-16 ~ 2026-02-22

假期安排：
  2.12-2.14  公司额外假期
  2.15-2.23  中国官方法定春节假期
  实际工作日：2.9(周一), 2.10(周二), 2.11(周三) = 3 天

使用方法：
  python test_spring_festival_weeks.py               # 仅测试节假日判断
  NOTION_API_TOKEN=xxx python test_spring_festival_weeks.py  # 同时测试 Notion 拉取
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


# ============================================
# 测试 1：节假日判断
# ============================================
def test_holiday_judgment():
    """逐日验证 2.9-2.22 的工作日/假日判断"""
    from src.holiday_helper import HolidayHelper

    helper = HolidayHelper()

    print("=" * 60)
    print("TEST 1  节假日判断")
    print("=" * 60)

    # 期望的工作日（仅 3 天）
    expected_workdays = {
        date(2026, 2, 9),
        date(2026, 2, 10),
        date(2026, 2, 11),
    }

    start = date(2026, 2, 9)
    end = date(2026, 2, 22)
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    actual_workdays = set()
    errors = []
    current = start

    while current <= end:
        is_work = helper.is_workday(current)
        info = helper.get_holiday_info(current)
        wname = weekday_names[current.weekday()]
        expected_work = current in expected_workdays

        if is_work:
            actual_workdays.add(current)

        icon = "✅" if is_work == expected_work else "❌"
        day_type = "工作日" if is_work else "假日  "
        holiday_label = f" [{info['name']}]" if info else ""
        print(f"  {icon} {current} ({wname})  {day_type}{holiday_label}")

        if is_work != expected_work:
            errors.append(
                f"{current}({wname}): 期望{'工作日' if expected_work else '假日'}，"
                f"实际{'工作日' if is_work else '假日'}"
            )
        current += timedelta(days=1)

    print(f"\n  工作日统计: 实际 {len(actual_workdays)} 天 / 期望 {len(expected_workdays)} 天")

    # ---- 周标准工时 ----
    #   2026-02-09 → ISO 周 7
    #   2026-02-16 → ISO 周 8
    w7 = helper.get_week_standard_hours(2026, 7)
    w8 = helper.get_week_standard_hours(2026, 8)

    w7_ok = w7 == 24.0
    w8_ok = w8 == 0.0

    print(f"\n  第7周(2.9-2.15) 标准工时: {w7}h  期望 24h  {'✅' if w7_ok else '❌'}")
    print(f"  第8周(2.16-2.22) 标准工时: {w8}h  期望 0h   {'✅' if w8_ok else '❌'}")

    if not w7_ok:
        errors.append(f"第7周标准工时: 期望 24h, 实际 {w7}h")
    if not w8_ok:
        errors.append(f"第8周标准工时: 期望 0h, 实际 {w8}h")

    # ---- get_period_summary 验证 ----
    summary = helper.get_period_summary(start, end)
    print(f"\n  期间汇总 ({start}~{end}):")
    print(f"    总天数:   {summary['total_days']}")
    print(f"    工作日:   {summary['workdays']}  期望 3")
    print(f"    假日:     {summary['holidays']}  期望 11")
    print(f"    特殊日:   {len(summary['special_days'])} 条配置")

    if summary["workdays"] != 3:
        errors.append(f"期间工作日: 期望 3, 实际 {summary['workdays']}")

    if errors:
        print(f"\n  ❌ 发现 {len(errors)} 个错误:")
        for e in errors:
            print(f"     - {e}")
    else:
        print("\n  ✅ 节假日判断全部正确")

    return len(errors) == 0


# ============================================
# 测试 2：Notion 数据拉取
# ============================================
def test_notion_fetch():
    """从 Notion 拉取两周数据，验证缓存"""
    token = os.getenv("NOTION_API_TOKEN")
    if not token:
        print("\n⚠️  未设置 NOTION_API_TOKEN，跳过 Notion 测试")
        return None

    from src.notion_connector import NotionConnector

    connector = NotionConnector(token)

    print("\n" + "=" * 60)
    print("TEST 2  Notion 数据拉取")
    print("=" * 60)

    errors = []

    # ---- 第 7 周 ----
    print("\n--- 第7周: 2026-02-09 ~ 2026-02-15 ---")
    df7 = connector.fetch_timesheet("2026-02-09", "2026-02-15")
    print(f"  记录数: {len(df7)} 条")

    if len(df7) > 0:
        print(f"  成员:   {df7['成员'].unique().tolist()}")
        print(f"  总工时: {df7['工时 h'].sum():.1f}h")
        print(f"  日期:   {df7['日期'].min()} ~ {df7['日期'].max()}")

        # 数据应只落在 2.9-2.11（工作日），2.12 之后不应有记录
        late_records = df7[df7["日期"] >= "2026-02-12"]
        if len(late_records) > 0:
            print(f"  ⚠️  2.12 之后有 {len(late_records)} 条记录（假期期间）")
        else:
            print("  ✅ 所有记录均在工作日(2.9-2.11)内")
    else:
        print("  ⚠️  第7周无数据（可能尚未填报）")

    # ---- 第 8 周 ----
    print("\n--- 第8周: 2026-02-16 ~ 2026-02-22 ---")
    df8 = connector.fetch_timesheet("2026-02-16", "2026-02-22")
    print(f"  记录数: {len(df8)} 条")

    if len(df8) == 0:
        print("  ✅ 第8周(春节假期)无记录，符合预期")
    else:
        print(f"  ⚠️  春节假期期间有 {len(df8)} 条记录")

    # ---- 缓存验证 ----
    cache_size = len(connector._page_title_cache)
    print(f"\n--- 缓存验证 ---")
    print(f"  页面标题缓存: {cache_size} 条")
    total_records = len(df7) + len(df8)
    if total_records > 0 and cache_size > 0:
        print(f"  总记录 {total_records} 条, 去重缓存 {cache_size} 条 → 节省 {total_records - cache_size} 次 API 调用")
        print("  ✅ 缓存生效")
    elif total_records > 0:
        print("  ⚠️  有记录但缓存为空，可能无 relation 字段")

    if errors:
        print(f"\n  ❌ 发现 {len(errors)} 个错误")
    else:
        print("\n  ✅ Notion 拉取正常")

    return len(errors) == 0


# ============================================
# 测试 3：完整分析流程
# ============================================
def test_analysis_pipeline():
    """拉取数据后走完预处理 → 分析全流程"""
    token = os.getenv("NOTION_API_TOKEN")
    if not token:
        return None

    from src.notion_connector import NotionConnector
    from src.preprocessor import preprocess_data
    from src.analyzer import TimesheetAnalyzer

    print("\n" + "=" * 60)
    print("TEST 3  完整分析流程 (2.9-2.22)")
    print("=" * 60)

    connector = NotionConnector(token)
    df = connector.fetch_timesheet("2026-02-09", "2026-02-22")

    if len(df) == 0:
        print("  ⚠️  无数据，跳过流程测试")
        return None

    # 参考日期 = 第 7 周的周五（2.13）
    ref_date = date(2026, 2, 13)
    df_processed, meta = preprocess_data(df, ref_date)

    print(f"\n  预处理元信息:")
    print(f"    总记录:   {meta['total_records']} 条")
    print(f"    成员数:   {meta['unique_members']} 人")
    print(f"    项目数:   {meta['unique_projects']} 个")
    print(f"    日期范围: {meta['date_range'][0]} ~ {meta['date_range'][1]}")

    analyzer = TimesheetAnalyzer(df_processed)
    summary = analyzer.get_summary("本周")
    members = analyzer.analyze_members("本周")
    projects = analyzer.analyze_projects("本周")

    print(f"\n  本周汇总:")
    print(f"    总工时:   {summary['total_hours']}h")
    print(f"    工作日:   {summary['working_days']} 天")
    print(f"    项目数:   {summary['project_count']} 个")
    print(f"    成员数:   {summary['member_count']} 人")

    if members:
        print(f"\n  成员分析:")
        for m in members:
            std = f"{m.standard_hours}h" if m.standard_hours else "N/A"
            rate = f"{m.achievement_rate}%" if m.achievement_rate else "N/A"
            print(f"    {m.name}: 实际{m.total_hours}h / 标准{std} / 达成率{rate} / {m.status}")

    if projects:
        print(f"\n  项目 TOP5:")
        for p in projects[:5]:
            print(f"    {p.name}: {p.total_hours}h ({p.percentage}%) [{p.member_count}人]")

    print("\n  ✅ 分析流程完成")
    return True


# ============================================
# 主入口
# ============================================
if __name__ == "__main__":
    print("🧪 春节假期周综合测试")
    print(f"   第7周: 2026-02-09 ~ 2026-02-15")
    print(f"   第8周: 2026-02-16 ~ 2026-02-22")
    print(f"   假期: 2.12-2.14(公司) + 2.15-2.23(春节)")
    print(f"   期望工作日: 2.9, 2.10, 2.11 = 3 天\n")

    r1 = test_holiday_judgment()
    r2 = test_notion_fetch()
    r3 = test_analysis_pipeline()

    print("\n" + "=" * 60)
    print("📋 测试结果汇总")
    print("=" * 60)

    def status(r):
        if r is None:
            return "⏭️  跳过"
        return "✅ 通过" if r else "❌ 失败"

    print(f"  1. 节假日判断:    {status(r1)}")
    print(f"  2. Notion 数据拉取: {status(r2)}")
    print(f"  3. 完整分析流程:    {status(r3)}")
    print("=" * 60)

    # 退出码：任何测试失败则返回 1
    if r1 is False or r2 is False or r3 is False:
        sys.exit(1)

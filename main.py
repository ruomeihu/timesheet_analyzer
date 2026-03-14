#!/usr/bin/env python3
"""
团队工时分析系统 - 命令行入口

用法：
    python main.py --input data/timesheet.csv
    python main.py --input data/timesheet.csv --output output/
"""
import argparse
from pathlib import Path
from datetime import date
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.data_loader import load_timesheet, validate_data
from src.preprocessor import preprocess_data, filter_by_period
from src.analyzer import TimesheetAnalyzer
from src.visualizer import create_visualizations
from src.report_generator import generate_markdown_report, save_report


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='团队工时分析系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例：
  python main.py --input data/timesheet.csv
  python main.py --input data/timesheet.csv --output output/ --date 2025-09-30
        '''
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='输入 CSV 文件路径'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='output/',
        help='输出目录路径 (默认: output/)'
    )
    
    parser.add_argument(
        '--date', '-d',
        type=str,
        default=None,
        help='参考日期，格式 YYYY-MM-DD (默认: 今天)'
    )
    
    parser.add_argument(
        '--no-chart',
        action='store_true',
        help='不生成图表'
    )
    
    args = parser.parse_args()
    
    # 解析参考日期
    reference_date = date.today()
    if args.date:
        try:
            from datetime import datetime
            reference_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print(f"❌ 日期格式错误: {args.date}，请使用 YYYY-MM-DD 格式")
            sys.exit(1)
    
    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🚀 启动团队工时分析系统...")
    print(f"📁 输入文件: {args.input}")
    print(f"📅 参考日期: {reference_date}")
    print()
    
    # 1. 加载数据
    print("📂 加载数据...")
    try:
        df_raw = load_timesheet(args.input)
        validation = validate_data(df_raw)
        
        if not validation['valid']:
            print("⚠️ 数据质量问题:")
            for issue in validation['issues']:
                print(f"   - {issue}")
        
        print(f"✅ 加载成功，共 {validation['row_count']} 条记录")
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        sys.exit(1)
    
    # 2. 预处理
    print("🔧 预处理数据...")
    df, meta = preprocess_data(df_raw, reference_date)
    print(f"✅ 预处理完成")
    print(f"   - 日期范围: {meta['date_range'][0]} 至 {meta['date_range'][1]}")
    print(f"   - 成员数: {meta['unique_members']}")
    print(f"   - 项目数: {meta['unique_projects']}")
    print()
    
    # 3. 分析
    print("📊 开始分析...")
    analyzer = TimesheetAnalyzer(df)
    
    # 本周分析
    df_current = filter_by_period(df, "本周")
    current_summary = analyzer.get_summary("本周")
    current_members = analyzer.analyze_members("本周")
    current_projects = analyzer.analyze_projects("本周")
    insights = analyzer.generate_insights("本周")
    
    print(f"📅 本周数据: {len(df_current)} 条记录")
    
    # 下周分析
    df_next = filter_by_period(df, "下周")
    next_summary = analyzer.get_summary("下周")
    next_members = analyzer.analyze_members("下周")
    next_projects = analyzer.analyze_projects("下周")
    
    print(f"📅 下周数据: {len(df_next)} 条记录")
    print()
    
    # 4. 输出结果
    print("=" * 60)
    print("📊 本周工时分析报告")
    print("=" * 60)
    
    if current_summary['total_hours'] > 0:
        print(f"\n📈 总体概览:")
        print(f"   总工时: {current_summary['total_hours']} 小时")
        print(f"   工作天数: {current_summary['working_days']} 天")
        print(f"   项目数: {current_summary['project_count']} 个")
        
        print(f"\n👥 人员工时:")
        for m in current_members:
            rate_str = f"{m.achievement_rate}%" if m.achievement_rate else "N/A"
            print(f"   {m.name} ({m.type}): {m.total_hours}h | 达成率: {rate_str} | {m.status}")
        
        print(f"\n📁 TOP 5 项目:")
        for i, p in enumerate(current_projects[:5], 1):
            print(f"   {i}. {p.name[:30]}: {p.total_hours}h ({p.percentage}%)")
        
        if insights:
            print(f"\n💡 关键洞察:")
            for insight in insights:
                print(f"   {insight['title']}: {insight['content']}")
    else:
        print("⚠️ 本周无数据")
    
    print()
    
    # 5. 生成报告
    print("📝 生成报告...")
    report_content = generate_markdown_report(
        summary=current_summary,
        member_results=current_members,
        project_results=current_projects,
        insights=insights,
        next_week_summary=next_summary,
        next_week_members=next_members,
        next_week_projects=next_projects
    )
    
    report_path = output_dir / f"report_{reference_date.strftime('%Y%m%d')}.md"
    if save_report(report_content, report_path):
        print(f"✅ 报告已保存: {report_path}")
    
    # 6. 生成图表
    if not args.no_chart and len(df_current) > 0:
        print("📈 生成图表...")
        chart_path = output_dir / f"chart_{reference_date.strftime('%Y%m%d')}.png"
        create_visualizations(
            df=df_current,
            member_results=current_members,
            project_results=current_projects,
            output_path=chart_path
        )
        print(f"✅ 图表已保存: {chart_path}")
    
    print()
    print("=" * 60)
    print("✅ 分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

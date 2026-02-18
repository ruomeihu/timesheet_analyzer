#!/usr/bin/env python3
"""
工时自动化分析脚本

功能：
1. 从 Notion 自动导出本周工时数据
2. 运行分析生成报告
3. 保存到指定目录
4. 可选：发送邮件通知

使用方法：
    python auto_weekly_report.py
    python auto_weekly_report.py --email your@email.com
    python auto_weekly_report.py --week-offset -1  # 分析上周
"""

import os
import sys
import argparse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from pathlib import Path


# ============================================
# 配置区域 - 请根据你的情况修改
# ============================================

CONFIG = {
    # Notion 配置
    "notion_token": os.getenv("NOTION_API_TOKEN", ""),
    
    # 输出目录（报告保存位置）
    "output_dir": os.path.expanduser("~/Documents/MIH_Reports"),
    
    # 邮件配置（如果需要邮件通知）
    "email": {
        "enabled": False,  # 改为 True 启用邮件
        "smtp_server": "smtp.qq.com",  # QQ邮箱
        # "smtp_server": "smtp.163.com",  # 163邮箱
        # "smtp_server": "smtp.gmail.com",  # Gmail
        "smtp_port": 587,
        "sender_email": "",  # 发件人邮箱
        "sender_password": "",  # 邮箱授权码（不是登录密码）
        "recipient_emails": [],  # 收件人列表，如 ["a@test.com", "b@test.com"]
    },
    
    # 飞书/钉钉 Webhook（可选）
    "webhook": {
        "enabled": False,
        "url": "",  # Webhook URL
    }
}


# ============================================
# 核心功能
# ============================================

def get_week_dates(week_offset: int = 0) -> tuple:
    """
    获取指定周的日期范围
    
    Parameters
    ----------
    week_offset : int
        0 = 本周, -1 = 上周, 1 = 下周
    
    Returns
    -------
    tuple
        (start_date, end_date, reference_date) 格式为 YYYY-MM-DD
    """
    today = datetime.now()
    
    # 找到本周一
    monday = today - timedelta(days=today.weekday())
    
    # 应用偏移
    monday = monday + timedelta(weeks=week_offset)
    
    # 周日
    sunday = monday + timedelta(days=6)
    
    # 参考日期（周五）
    friday = monday + timedelta(days=4)
    
    return (
        monday.strftime("%Y-%m-%d"),
        sunday.strftime("%Y-%m-%d"),
        friday.strftime("%Y-%m-%d")
    )


def export_from_notion(start_date: str, end_date: str, output_path: str) -> bool:
    """从 Notion 导出数据"""
    print(f"📥 从 Notion 导出数据: {start_date} 至 {end_date}")
    
    try:
        # 添加项目路径
        script_dir = Path(__file__).parent
        sys.path.insert(0, str(script_dir))
        
        from src.notion_connector import fetch_timesheet, save_to_csv
        
        df = fetch_timesheet(start_date, end_date, CONFIG["notion_token"])
        
        if len(df) == 0:
            print("⚠️ 该时间段没有数据")
            return False
        
        save_to_csv(df, output_path)
        print(f"✅ 导出 {len(df)} 条记录到: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        return False


def run_analysis(input_path: str, reference_date: str, output_dir: str) -> dict:
    """运行分析"""
    print(f"📊 运行分析...")
    
    try:
        script_dir = Path(__file__).parent
        sys.path.insert(0, str(script_dir))
        
        from src.data_loader import load_timesheet
        from src.preprocessor import preprocess_data, filter_by_period
        from src.analyzer import TimesheetAnalyzer
        from src.report_generator import generate_markdown_report, save_report
        from src.visualizer import create_visualizations

        ref_date = datetime.strptime(reference_date, "%Y-%m-%d").date()

        # 加载和预处理（解包元组）
        df_raw = load_timesheet(input_path)
        df, meta = preprocess_data(df_raw, ref_date)

        # 分析（只传 df）
        analyzer = TimesheetAnalyzer(df)
        summary = analyzer.get_summary("本周")
        member_results = analyzer.analyze_members("本周")
        project_results = analyzer.analyze_projects("本周")
        insights = analyzer.generate_insights("本周")

        # 下周分析
        next_summary = analyzer.get_summary("下周")
        next_members = analyzer.analyze_members("下周")
        next_projects = analyzer.analyze_projects("下周")

        # 生成报告（函数式，返回字符串）
        date_str = reference_date.replace("-", "")
        report_path = os.path.join(output_dir, f"report_{date_str}.md")
        chart_path = os.path.join(output_dir, f"chart_{date_str}.png")

        report_content = generate_markdown_report(
            summary=summary,
            member_results=member_results,
            project_results=project_results,
            insights=insights,
            next_week_summary=next_summary,
            next_week_members=next_members,
            next_week_projects=next_projects
        )
        save_report(report_content, Path(report_path))

        # 生成图表（函数式）
        df_current = filter_by_period(df, "本周")
        if len(df_current) > 0:
            create_visualizations(
                df=df_current,
                member_results=member_results,
                project_results=project_results,
                output_path=Path(chart_path)
            )

        print(f"✅ 报告已保存: {report_path}")
        print(f"✅ 图表已保存: {chart_path}")

        return {
            "success": True,
            "report_path": report_path,
            "chart_path": chart_path,
            "summary": {
                "total_hours": summary['total_hours'],
                "member_count": summary['member_count'],
                "project_count": summary['project_count'],
                "record_count": meta['total_records']
            }
        }
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def send_email(subject: str, body: str, attachments: list = None):
    """发送邮件"""
    if not CONFIG["email"]["enabled"]:
        print("📧 邮件功能未启用")
        return
    
    email_config = CONFIG["email"]
    
    if not email_config["sender_email"] or not email_config["recipient_emails"]:
        print("⚠️ 邮件配置不完整，跳过发送")
        return
    
    print(f"📧 发送邮件到: {', '.join(email_config['recipient_emails'])}")
    
    try:
        msg = MIMEMultipart()
        msg["From"] = email_config["sender_email"]
        msg["To"] = ", ".join(email_config["recipient_emails"])
        msg["Subject"] = subject
        
        # 邮件正文
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        # 附件
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    filename = os.path.basename(file_path)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={filename}"
                    )
                    msg.attach(part)
        
        # 发送
        with smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"]) as server:
            server.starttls()
            server.login(email_config["sender_email"], email_config["sender_password"])
            server.send_message(msg)
        
        print("✅ 邮件发送成功")
        
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")


def send_webhook(message: str):
    """发送 Webhook 通知（飞书/钉钉）"""
    if not CONFIG["webhook"]["enabled"]:
        return
    
    import requests
    
    try:
        # 飞书格式
        payload = {
            "msg_type": "text",
            "content": {"text": message}
        }
        
        response = requests.post(CONFIG["webhook"]["url"], json=payload)
        if response.status_code == 200:
            print("✅ Webhook 通知已发送")
        else:
            print(f"⚠️ Webhook 返回: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Webhook 发送失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MIH 工时自动分析")
    parser.add_argument("--week-offset", type=int, default=0,
                        help="周偏移量: 0=本周, -1=上周")
    parser.add_argument("--email", type=str, nargs="*",
                        help="发送邮件到指定地址")
    parser.add_argument("--output-dir", type=str,
                        help="输出目录")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🤖 MIH 工时自动分析系统")
    print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查 Token
    if not CONFIG["notion_token"]:
        print("❌ 错误: 未设置 NOTION_API_TOKEN 环境变量")
        sys.exit(1)
    
    # 获取日期范围（拉取本周+下周两周数据）
    start_date, end_date, ref_date = get_week_dates(args.week_offset)
    _, next_end, _ = get_week_dates(args.week_offset + 1)
    week_num = datetime.strptime(ref_date, "%Y-%m-%d").isocalendar()[1]

    print(f"\n📅 分析周期: 第 {week_num} 周")
    print(f"   日期范围: {start_date} 至 {next_end}（含下周）")
    print(f"   参考日期: {ref_date}")
    
    # 创建输出目录
    output_dir = args.output_dir or CONFIG["output_dir"]
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 输出目录: {output_dir}")
    
    # 数据文件路径（使用日期命名，方便 Streamlit 预生成报告模式识别）
    date_str = ref_date.replace("-", "")
    data_path = os.path.join(output_dir, f"timesheet_{date_str}.csv")
    
    # Step 1: 从 Notion 导出（本周+下周）
    print("\n" + "-" * 40)
    if not export_from_notion(start_date, next_end, data_path):
        print("❌ 导出失败，退出")
        sys.exit(1)
    
    # Step 2: 运行分析
    print("\n" + "-" * 40)
    result = run_analysis(data_path, ref_date, output_dir)
    
    if not result["success"]:
        print("❌ 分析失败，退出")
        sys.exit(1)
    
    # Step 3: 发送通知
    print("\n" + "-" * 40)
    summary = result["summary"]
    
    message = f"""
📊 MIH 工时周报 - 第 {week_num} 周

📅 周期: {start_date} 至 {end_date}
👥 成员数: {summary['member_count']} 人
📋 记录数: {summary['record_count']} 条
⏱️ 总工时: {summary['total_hours']:.1f} 小时
📁 项目数: {summary['project_count']} 个

报告已保存至: {result['report_path']}
"""
    
    print(message)
    
    # 邮件
    if args.email:
        CONFIG["email"]["enabled"] = True
        CONFIG["email"]["recipient_emails"] = args.email
    
    if CONFIG["email"]["enabled"]:
        send_email(
            subject=f"MIH 工时周报 - 第 {week_num} 周",
            body=message,
            attachments=[result["report_path"], result["chart_path"]]
        )
    
    # Webhook
    send_webhook(message)
    
    print("\n" + "=" * 60)
    print("🎉 自动分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

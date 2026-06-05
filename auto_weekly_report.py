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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
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
    
    # 邮件配置（126 邮箱 SSL）
    # enabled 默认 False：仅当命令行显式传 --email 时才发邮件（手动重生不会误发）。
    # CI 定时任务在 weekly_report.yml 里显式传 --email 以保持周报推送。
    "email": {
        "enabled": False,
        "smtp_server": "smtp.126.com",
        "smtp_port": 465,
        "sender_email": "mayhu1024@126.com",
        "sender_password": os.getenv("MAIL_SENDER", ""),  # 126 授权码（不是登录密码）
        "recipient_emails": ["mayhu1024@126.com"],
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
    """运行分析。

    流水线 (Markdown/图表/Gamma/sidecar/PDF) 委托给 src.report_pipeline,
    与 app.py 的「重新生成 PPT」按钮共用同一段逻辑。
    """
    print(f"📊 运行分析...")

    try:
        script_dir = Path(__file__).parent
        sys.path.insert(0, str(script_dir))

        from src.data_loader import load_timesheet
        from src.preprocessor import preprocess_data
        from src.analyzer import TimesheetAnalyzer
        from src.report_pipeline import render_report_artifacts

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

        # AI 深度分析
        from src.ai_analyzer import get_ai_analyzer

        ai_analyzer = get_ai_analyzer()
        ai_insights = None
        if ai_analyzer is not None:
            try:
                print("🤖 调用 AI 分析器...")
                import time
                start = time.time()
                ai_insights = ai_analyzer.analyze(
                    df=df,
                    member_results=member_results,
                    project_results=project_results,
                    summary=summary,
                    period="本周"
                )
                elapsed = time.time() - start
                print(f"✅ AI 分析完成, 耗时 {elapsed:.1f}s")
            except Exception as e:
                print(f"⚠️ AI 分析失败, 跳过此部分: {e}")
                ai_insights = None
        else:
            print("⚠️ AI 分析器不可用 (anthropic 库或 API key 缺失), 跳过此部分")

        # 下周分析
        next_summary = analyzer.get_summary("下周")
        next_members = analyzer.analyze_members("下周")
        next_projects = analyzer.analyze_projects("下周")

        artifacts = render_report_artifacts(
            df=df,
            summary=summary,
            member_results=member_results,
            project_results=project_results,
            insights=insights,
            next_week_summary=next_summary,
            next_week_members=next_members,
            next_week_projects=next_projects,
            ai_insights=ai_insights,
            reference_date=ref_date,
            output_dir=output_dir,
            source="ci",
        )

        print(f"✅ 报告已保存: {artifacts['report_path']}")
        print(f"✅ 图表已保存: {artifacts['chart_path']}")
        print(f"✅ Gamma 元数据已保存: {artifacts['sidecar_path']}")

        return {
            "success": True,
            "report_path": artifacts["report_path"],
            "chart_path": artifacts["chart_path"],
            "gamma_url": artifacts["gamma_url"],
            "pdf_path": artifacts["pdf_path"],
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


def send_email(subject: str, body: str, html_body: str = None, attachments: list = None):
    """发送邮件 (支持 HTML 正文,链接可点)"""
    if not CONFIG["email"]["enabled"]:
        print("📧 邮件功能未启用")
        return

    email_config = CONFIG["email"]

    if not email_config["sender_email"] or not email_config["recipient_emails"]:
        print("⚠️ 邮件配置不完整，跳过发送")
        return
    if not email_config["sender_password"]:
        print("⚠️ 未设置 MAIL_SENDER 环境变量（126 授权码），跳过发送")
        return

    print(f"📧 发送邮件到: {', '.join(email_config['recipient_emails'])}")

    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = email_config["sender_email"]
        msg["To"] = ", ".join(email_config["recipient_emails"])
        msg["Subject"] = subject

        # 正文: multipart/alternative 同时提供 plain + html, 客户端按能力挑
        if html_body:
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(body, "plain", "utf-8"))
            alt.attach(MIMEText(html_body, "html", "utf-8"))
            msg.attach(alt)
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))
        
        # 附件: 支持 str 或 (path, display_name) 元组,后者用于自定义下载名
        if attachments:
            for item in attachments:
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    file_path, display_name = item[0], item[1]
                else:
                    file_path, display_name = item, os.path.basename(item)
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    # RFC 2231 编码以支持中文文件名
                    part.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=("utf-8", "", display_name),
                    )
                    msg.attach(part)
        
        # 发送（126 使用 SSL，不是 STARTTLS）
        with smtplib.SMTP_SSL(email_config["smtp_server"], email_config["smtp_port"]) as server:
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
    
    gamma_url = result.get("gamma_url")
    gamma_line = f"🎬 在线 PPT: {gamma_url}" if gamma_url else "🎬 在线 PPT: (本周生成失败, 请查看 Markdown)"
    gamma_line_html = (
        f'🎬 在线 PPT: <a href="{gamma_url}">{gamma_url}</a>'
        if gamma_url
        else "🎬 在线 PPT: (本周生成失败, 请查看 Markdown)"
    )

    message = f"""
📊 MIH 工时周报 - 第 {week_num} 周

📅 周期: {start_date} 至 {end_date}
👥 成员数: {summary['member_count']} 人
📋 记录数: {summary['record_count']} 条
⏱️ 总工时: {summary['total_hours']:.1f} 小时
📁 项目数: {summary['project_count']} 个

{gamma_line}

报告已保存至: {result['report_path']}
"""

    html_message = f"""<html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.7; color: #1f2937;">
<h2 style="margin-bottom: 12px;">📊 MIH 工时周报 - 第 {week_num} 周</h2>
<p style="margin: 0 0 16px;">
📅 周期: {start_date} 至 {end_date}<br>
👥 成员数: {summary['member_count']} 人<br>
📋 记录数: {summary['record_count']} 条<br>
⏱️ 总工时: {summary['total_hours']:.1f} 小时<br>
📁 项目数: {summary['project_count']} 个
</p>
<p style="margin: 0 0 16px;">{gamma_line_html}</p>
<p style="margin: 0; color: #6b7280; font-size: 13px;">报告已保存至: {result['report_path']}</p>
</body></html>"""

    print(message)

    # 邮件：仅当显式传 --email 才发（args.email is None 表示未传该参数）。
    # --email 后跟地址 → 覆盖收件人；--email 单独出现（空列表）→ 用默认收件人。
    if args.email is not None:
        CONFIG["email"]["enabled"] = True
        if args.email:
            CONFIG["email"]["recipient_emails"] = args.email

    if CONFIG["email"]["enabled"]:
        attachments = [result["report_path"], result["chart_path"]]
        if result.get("pdf_path"):
            attachments.append(
                (result["pdf_path"], f"工时分析周报_数据平台部_{date_str}.pdf")
            )
        send_email(
            subject=f"MIH 工时周报 - 第 {week_num} 周",
            body=message,
            html_body=html_message,
            attachments=attachments,
        )
    
    # Webhook
    send_webhook(message)
    
    print("\n" + "=" * 60)
    print("🎉 自动分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

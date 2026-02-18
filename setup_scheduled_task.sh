#!/bin/bash
# ============================================
# MIH 工时自动化一键设置脚本
# ============================================

echo "========================================"
echo "🤖 MIH 工时自动化设置向导"
echo "========================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "📁 项目目录: $SCRIPT_DIR"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装"
    exit 1
fi
echo "✅ Python3: $(python3 --version)"

# 获取用户输入
echo ""
echo "请输入以下信息："
echo ""

read -p "1. Notion API Token: " NOTION_TOKEN
if [ -z "$NOTION_TOKEN" ]; then
    echo "❌ Token 不能为空"
    exit 1
fi

read -p "2. 报告保存目录 [默认: ~/Documents/MIH_Reports]: " OUTPUT_DIR
OUTPUT_DIR=${OUTPUT_DIR:-"$HOME/Documents/MIH_Reports"}

read -p "3. 是否配置邮件通知? (y/n) [n]: " SETUP_EMAIL
SETUP_EMAIL=${SETUP_EMAIL:-"n"}

if [ "$SETUP_EMAIL" = "y" ]; then
    read -p "   发件人邮箱: " SENDER_EMAIL
    read -sp "   邮箱授权码: " SENDER_PASSWORD
    echo ""
    read -p "   收件人邮箱 (多个用逗号分隔): " RECIPIENT_EMAILS
fi

# 创建目录
echo ""
echo "📁 创建目录..."
mkdir -p "$OUTPUT_DIR"
mkdir -p ~/Scripts
mkdir -p ~/Library/LaunchAgents

# 创建启动脚本
echo "📝 创建启动脚本..."
cat > ~/Scripts/run_weekly_report.sh << EOF
#!/bin/bash

# MIH 工时自动分析启动脚本
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')

# 环境变量
export NOTION_API_TOKEN="$NOTION_TOKEN"
export PATH="/usr/local/bin:/usr/bin:/bin:\$PATH"

# 项目目录
PROJECT_DIR="$SCRIPT_DIR"

# 输出目录
OUTPUT_DIR="$OUTPUT_DIR"

# 日志
LOG_FILE="\$OUTPUT_DIR/auto_run.log"
mkdir -p "\$(dirname "\$LOG_FILE")"

echo "========================================" >> "\$LOG_FILE"
echo "运行时间: \$(date '+%Y-%m-%d %H:%M:%S')" >> "\$LOG_FILE"

# 运行
cd "\$PROJECT_DIR"
/usr/bin/python3 auto_weekly_report.py --output-dir "\$OUTPUT_DIR" >> "\$LOG_FILE" 2>&1

echo "完成时间: \$(date '+%Y-%m-%d %H:%M:%S')" >> "\$LOG_FILE"
echo "" >> "\$LOG_FILE"
EOF

chmod +x ~/Scripts/run_weekly_report.sh
echo "✅ 启动脚本: ~/Scripts/run_weekly_report.sh"

# 更新 Python 配置
if [ "$SETUP_EMAIL" = "y" ]; then
    echo "📝 配置邮件..."
    # 这里简化处理，实际应该用 sed 或 Python 修改配置
    echo ""
    echo "⚠️ 请手动编辑 auto_weekly_report.py 中的邮件配置："
    echo "   sender_email: $SENDER_EMAIL"
    echo "   recipient_emails: [$RECIPIENT_EMAILS]"
fi

# 创建 launchd 配置
echo "📝 创建定时任务..."
cat > ~/Library/LaunchAgents/com.mih.weekly-report.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mih.weekly-report</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$HOME/Scripts/run_weekly_report.sh</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>5</integer>
        <key>Hour</key>
        <integer>13</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>$OUTPUT_DIR/launchd_stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>$OUTPUT_DIR/launchd_stderr.log</string>
    
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

echo "✅ launchd 配置: ~/Library/LaunchAgents/com.mih.weekly-report.plist"

# 加载任务
echo ""
echo "📥 加载定时任务..."

# 先卸载（如果存在）
launchctl unload ~/Library/LaunchAgents/com.mih.weekly-report.plist 2>/dev/null

# 加载
launchctl load ~/Library/LaunchAgents/com.mih.weekly-report.plist

if launchctl list | grep -q "com.mih.weekly-report"; then
    echo "✅ 定时任务已加载"
else
    echo "⚠️ 定时任务加载可能失败，请检查日志"
fi

# 测试
echo ""
read -p "是否立即运行一次测试? (y/n) [y]: " RUN_TEST
RUN_TEST=${RUN_TEST:-"y"}

if [ "$RUN_TEST" = "y" ]; then
    echo ""
    echo "🧪 运行测试..."
    echo ""
    bash ~/Scripts/run_weekly_report.sh
    
    echo ""
    echo "📋 查看日志..."
    tail -30 "$OUTPUT_DIR/auto_run.log"
fi

# 完成
echo ""
echo "========================================"
echo "🎉 设置完成！"
echo "========================================"
echo ""
echo "📅 定时任务: 每周五 13:00 自动运行"
echo "📁 报告目录: $OUTPUT_DIR"
echo "📋 日志文件: $OUTPUT_DIR/auto_run.log"
echo ""
echo "常用命令："
echo "  手动运行: bash ~/Scripts/run_weekly_report.sh"
echo "  查看日志: cat $OUTPUT_DIR/auto_run.log"
echo "  停止任务: launchctl unload ~/Library/LaunchAgents/com.mih.weekly-report.plist"
echo ""

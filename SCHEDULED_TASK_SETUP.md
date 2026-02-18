# 🕐 Mac 定时任务设置指南

本指南帮你设置每周五下午 1 点自动运行工时分析。

---

## 📋 方案选择

| 方案 | 难度 | 特点 |
|------|------|------|
| **方案 A: launchd** | ⭐⭐ | Mac 原生，推荐，电脑睡眠唤醒后会补执行 |
| **方案 B: cron** | ⭐ | 简单，但电脑必须在运行状态 |
| **方案 C: 快捷指令** | ⭐ | 可视化，适合不熟悉命令行的用户 |

---

## 🍎 方案 A: launchd（推荐）

### 步骤 1: 创建启动脚本

打开终端，运行：

```bash
# 创建脚本目录
mkdir -p ~/Scripts

# 创建启动脚本
cat > ~/Scripts/run_weekly_report.sh << 'EOF'
#!/bin/bash

# 设置环境变量
export NOTION_API_TOKEN="你的token"
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# 项目目录（请修改为你的实际路径）
PROJECT_DIR="$HOME/Projects/timesheet_analyzer"

# 日志
LOG_FILE="$HOME/Documents/MIH_Reports/auto_run.log"
mkdir -p "$(dirname "$LOG_FILE")"

echo "========================================" >> "$LOG_FILE"
echo "运行时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"

# 运行
cd "$PROJECT_DIR"
/usr/bin/python3 auto_weekly_report.py >> "$LOG_FILE" 2>&1

echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
EOF

# 添加执行权限
chmod +x ~/Scripts/run_weekly_report.sh
```

### 步骤 2: 修改脚本中的配置

```bash
nano ~/Scripts/run_weekly_report.sh
```

修改以下内容：
- `NOTION_API_TOKEN="你的token"` → 替换为你的实际 token
- `PROJECT_DIR="$HOME/Projects/timesheet_analyzer"` → 替换为你的项目实际路径

保存：`Ctrl+O` → 回车 → `Ctrl+X`

### 步骤 3: 创建 launchd 配置

```bash
cat > ~/Library/LaunchAgents/com.mih.weekly-report.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mih.weekly-report</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>$HOME/Scripts/run_weekly_report.sh</string>
    </array>
    
    <!-- 每周五 13:00 运行 -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>5</integer>
        <key>Hour</key>
        <integer>13</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <!-- 错过的任务在唤醒后执行 -->
    <key>StartCalendarIntervalAllowsOnBattery</key>
    <true/>
    
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF
```

### 步骤 4: 加载定时任务

```bash
# 加载
launchctl load ~/Library/LaunchAgents/com.mih.weekly-report.plist

# 验证
launchctl list | grep mih
```

看到 `com.mih.weekly-report` 就成功了！

### 步骤 5: 测试运行

```bash
# 手动触发一次测试
launchctl start com.mih.weekly-report

# 查看日志
cat ~/Documents/MIH_Reports/auto_run.log
```

### 常用命令

```bash
# 停止任务
launchctl unload ~/Library/LaunchAgents/com.mih.weekly-report.plist

# 重新加载（修改配置后）
launchctl unload ~/Library/LaunchAgents/com.mih.weekly-report.plist
launchctl load ~/Library/LaunchAgents/com.mih.weekly-report.plist

# 查看状态
launchctl list | grep mih

# 删除任务
launchctl unload ~/Library/LaunchAgents/com.mih.weekly-report.plist
rm ~/Library/LaunchAgents/com.mih.weekly-report.plist
```

---

## 🕐 方案 B: cron（简单版）

```bash
# 编辑 crontab
crontab -e

# 添加这行（每周五 13:00）
0 13 * * 5 cd ~/Projects/timesheet_analyzer && /usr/bin/python3 auto_weekly_report.py >> ~/Documents/MIH_Reports/cron.log 2>&1

# 保存退出
# vim: 按 ESC, 输入 :wq, 回车
# nano: Ctrl+O, 回车, Ctrl+X
```

⚠️ **注意**：cron 需要电脑在运行状态，睡眠时不会执行。

---

## 📱 方案 C: Mac 快捷指令

1. 打开「快捷指令」App
2. 创建新快捷指令
3. 添加「运行 Shell 脚本」动作
4. 输入：
```bash
cd ~/Projects/timesheet_analyzer
/usr/bin/python3 auto_weekly_report.py
```
5. 点击右侧 ℹ️ → 添加到「自动化」
6. 选择「特定时间」→ 每周五 13:00

---

## 📧 配置邮件通知（可选）

### 方法 1: 在脚本中配置

编辑 `auto_weekly_report.py`，找到 `CONFIG` 部分：

```python
CONFIG = {
    # ...
    "email": {
        "enabled": True,  # 改为 True
        "smtp_server": "smtp.qq.com",  # QQ邮箱
        "smtp_port": 587,
        "sender_email": "your_qq@qq.com",  # 你的QQ邮箱
        "sender_password": "xxxxxxxx",  # QQ邮箱授权码
        "recipient_emails": ["iris@example.com"],  # 收件人
    },
}
```

### 获取 QQ 邮箱授权码

1. 登录 mail.qq.com
2. 设置 → 账户 → POP3/SMTP服务 → 开启
3. 生成授权码（不是QQ密码）

### 方法 2: 命令行指定收件人

```bash
python3 auto_weekly_report.py --email your@email.com colleague@email.com
```

---

## 💬 配置飞书/钉钉通知（可选）

### 飞书机器人

1. 在飞书群里添加「自定义机器人」
2. 复制 Webhook URL
3. 编辑 `auto_weekly_report.py`：

```python
CONFIG = {
    # ...
    "webhook": {
        "enabled": True,
        "url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx",
    }
}
```

### 钉钉机器人

同样方式，只需修改 Webhook URL。

---

## 📁 报告保存位置

默认保存在：`~/Documents/MIH_Reports/`

每次运行会生成：
- `timesheet_week{周数}.csv` - 原始数据
- `report_{日期}.md` - 分析报告
- `chart_{日期}.png` - 可视化图表
- `auto_run.log` - 运行日志

---

## 🔧 故障排除

### Q1: launchd 任务没有运行

```bash
# 检查任务是否加载
launchctl list | grep mih

# 查看系统日志
log show --predicate 'subsystem == "com.apple.xpc.launchd"' --last 1h | grep mih
```

### Q2: Python 找不到模块

确保脚本中的 Python 路径正确：
```bash
which python3  # 查看 Python 路径
```

### Q3: 权限问题

```bash
# 给脚本执行权限
chmod +x ~/Scripts/run_weekly_report.sh

# 允许终端完全磁盘访问
# 系统偏好设置 → 安全性与隐私 → 隐私 → 完全磁盘访问权限 → 添加终端
```

### Q4: 网络问题

如果公司有 VPN 要求：
```bash
# 在脚本开头添加 VPN 连接命令
# 或者确保定时任务运行时 VPN 已连接
```

---

## ✅ 验证清单

- [ ] Token 已设置并测试通过
- [ ] 项目路径正确
- [ ] 脚本有执行权限
- [ ] launchd 任务已加载
- [ ] 手动测试运行成功
- [ ] 日志文件正常生成
- [ ] （可选）邮件发送测试成功

---

## 🎉 完成！

设置完成后，每周五下午 1 点，系统会自动：

1. 📥 从 Notion 导出本周工时数据
2. 📊 运行分析生成报告
3. 💾 保存到 `~/Documents/MIH_Reports/`
4. 📧 发送邮件通知（如果配置了）

你只需要坐等报告送达！🎊

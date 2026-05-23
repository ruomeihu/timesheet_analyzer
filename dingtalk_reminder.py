# === 周五工时填写提醒 ===
# 目标: 周五 9:00 在群里发本周工时提醒 (Markdown + @所有人)

import os
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime
import requests
from dotenv import load_dotenv

# --- Step 1: 从 .env 读凭证 ---
load_dotenv()
WEBHOOK = os.getenv("DINGTALK_WEBHOOK")
SECRET = os.getenv("DINGTALK_SECRET")

if not WEBHOOK or not SECRET:
    raise ValueError("没读到凭证！检查 .env")

# --- Step 2: 加签 ---
timestamp = str(round(time.time() * 1000))
string_to_sign = f"{timestamp}\n{SECRET}"
hmac_code = hmac.new(
    SECRET.encode("utf-8"),
    string_to_sign.encode("utf-8"),
    digestmod=hashlib.sha256
).digest()
sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
url = f"{WEBHOOK}&timestamp={timestamp}&sign={sign}"

# --- Step 3: 当前周次 ---
week_num = datetime.now().isocalendar()[1]

# --- Step 4: Markdown 消息正文 ---
# 【请按你团队真实规则修改下面文案】
markdown_text = f"""## 📋 工时填写提醒 · 第 {week_num} 周

@所有人

各位伙伴周五好 👋

请在 **今天中午 12:00 前** 完成本周工时登记。

⏰ **为什么是 12:00**: 13:00 周报会自动生成统计, **12:00 后填写不会被纳入本周报**。

**📌 填写要求**
- 📍 位置: [MIH Timesheet 工时库](https://www.notion.so/ihealthwork/27860a7d47d280ab9529e599217f6730?v=27860a7d47d28086bb5b000c57a970ad)
- ⏱️ 颗粒度: 以"日"为单位, 最小 0.5 小时
- 🔗 每条记录关联到 **MIH Projects 项目库** 里的具体项目
- 📅 建议把**下周重要工作的工时预估**也提前登记, 会纳入下周工作计划

**💡 项目归类提醒**
日常岗位工作请关联到对应的运营项目, 售前工作请提前立项。"未立项/临时指派"仅用于**真正临时**的事项, 不是默认项 🙂

**🤖 关于审核**
AI 会做初审, 主管对下属团队成员工时进行 2 次审核。

**📊 预告**
下午 14:00 会把本周工时分析 PPT 发到群里 ☕

如有疑问群里 @胡若玫 即可
"""

payload = {
    "msgtype": "markdown",
    "markdown": {
        "title": f"工时填写提醒 · 第 {week_num} 周",
        "text": markdown_text
    },
    "at": {
        "isAtAll": True
    }
}

# --- Step 5: 发送 ---
response = requests.post(url, json=payload)
print(f"HTTP 状态码: {response.status_code}")
print(f"钉钉返回: {response.json()}")
print(f"\n📅 当前周次: 第 {week_num} 周")
print(f"⏰ 发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

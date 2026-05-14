"""
Gamma API 客户端

封装 Gamma Generate API (https://public-api.gamma.app/v1.0/generations),
把 Markdown 字符串转成在线 PPT。异步生成 + 轮询。

环境变量:
    GAMMA_API_KEY: Gamma Pro+ API Key (在 https://gamma.app/settings/api 获取)

失败时返回 None 而非抛异常,调用方自行优雅降级。
"""

import os
import time
from typing import Optional

import requests

GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"

GENERATION_PARAMS = {
    "textMode": "condense",
    "format": "presentation",
    "themeId": "gamma",
    "numCards": 14,
    "folderIds": ["ucaeyffxew7c6a1"],
    "exportAs": "pdf",
    "textOptions": {"amount": "detailed", "language": "zh-cn"},
    "imageOptions": {"stylePreset": "illustration", "source": "aiGenerated"},
}


def generate_presentation(
    input_text: str,
    *,
    api_key: Optional[str] = None,
    poll_interval: int = 5,
    timeout: int = 600,
) -> Optional[dict]:
    """从 Markdown 生成 Gamma 在线 PPT。

    Returns
    -------
    dict | None
        成功: {"gammaUrl": str, "exportUrl": str | None, "generationId": str}
        失败 (缺 key / 网络 / 超时 / Gamma 返回错误): None
    """
    key = api_key or os.getenv("GAMMA_API_KEY")
    if not key:
        print("⚠️ 未设置 GAMMA_API_KEY 环境变量, 跳过 PPT 生成")
        return None

    headers = {"X-API-KEY": key, "Content-Type": "application/json"}
    body = {"inputText": input_text, **GENERATION_PARAMS}

    try:
        print(f"🎬 调用 Gamma API 生成 PPT (numCards={GENERATION_PARAMS['numCards']})...")
        resp = requests.post(
            f"{GAMMA_API_BASE}/generations",
            headers=headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        generation_id = resp.json().get("generationId")
        if not generation_id:
            print(f"⚠️ Gamma 响应缺少 generationId: {resp.text[:200]}")
            return None
    except requests.RequestException as e:
        print(f"❌ Gamma 创建任务失败: {e}")
        return None

    return _poll_until_done(generation_id, headers, poll_interval, timeout)


def _poll_until_done(
    generation_id: str,
    headers: dict,
    poll_interval: int,
    timeout: int,
) -> Optional[dict]:
    deadline = time.time() + timeout
    poll_url = f"{GAMMA_API_BASE}/generations/{generation_id}"

    while time.time() < deadline:
        try:
            resp = requests.get(poll_url, headers=headers, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as e:
            print(f"⚠️ 轮询失败, 重试中: {e}")
            time.sleep(poll_interval)
            continue

        status = payload.get("status")
        if status == "completed":
            gamma_url = payload.get("gammaUrl")
            export_url = payload.get("exportUrl")
            print(f"✅ Gamma PPT 已生成: {gamma_url}")
            return {
                "gammaUrl": gamma_url,
                "exportUrl": export_url,
                "generationId": generation_id,
            }
        if status in {"failed", "error"}:
            print(f"❌ Gamma 生成失败: {payload}")
            return None

        time.sleep(poll_interval)

    print(f"❌ Gamma 生成超时 ({timeout}s)")
    return None


def download_export(export_url: str, output_path: str) -> bool:
    """下载 Gamma 导出文件 (PDF/PPTX) 到本地。失败返回 False。"""
    try:
        resp = requests.get(export_url, timeout=60)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
        print(f"✅ Gamma 导出文件已下载: {output_path}")
        return True
    except (requests.RequestException, OSError) as e:
        print(f"⚠️ 下载 Gamma 导出文件失败: {e}")
        return False

"""
测试 Gamma 客户端（mock requests，不发网络请求）：
1. 请求体用单值 folderId（fo_ 前缀），不含已被 Gamma 拒绝的 folderIds
2. 创建任务 400 → 返回 None，且日志打印 Gamma 响应正文（便于定位被拒字段）
3. 缺 GAMMA_API_KEY → 返回 None，不发请求
4. happy path：创建 + 轮询 completed → 返回 gammaUrl/exportUrl

运行：python test_gamma_client.py
"""
import contextlib
import io
import os
from unittest import mock

import requests

from src import gamma_client
from src.gamma_client import GENERATION_PARAMS, generate_presentation


def _resp(status, payload=None, text=""):
    r = requests.Response()
    r.status_code = status
    r._content = (text or (__import__("json").dumps(payload) if payload is not None else "")).encode()
    r.url = f"{gamma_client.GAMMA_API_BASE}/generations"
    return r


def test_params_use_folder_id():
    assert "folderIds" not in GENERATION_PARAMS, "folderIds 已被 Gamma 拒绝 (400)"
    assert GENERATION_PARAMS["folderId"].startswith("fo_")
    print("✓ 请求参数使用 folderId（fo_ 前缀）")


def test_400_returns_none_and_logs_body():
    body = '{"message":"Input validation errors: 1. property folderIds should not exist","statusCode":400}'
    buf = io.StringIO()
    with mock.patch.object(gamma_client.requests, "post", return_value=_resp(400, text=body)), \
         contextlib.redirect_stdout(buf):
        assert generate_presentation("x", api_key="k") is None
    out = buf.getvalue()
    assert "should not exist" in out, out
    print("✓ 400 返回 None 并打印 Gamma 响应正文")


def test_missing_key_skips():
    with mock.patch.dict(os.environ, {}, clear=True), \
         mock.patch.object(gamma_client.requests, "post") as post, \
         contextlib.redirect_stdout(io.StringIO()):
        assert generate_presentation("x") is None
        post.assert_not_called()
    print("✓ 缺 key 优雅跳过")


def test_happy_path():
    done = {"status": "completed", "gammaUrl": "https://gamma.app/docs/abc", "exportUrl": "https://e/x.pdf"}
    with mock.patch.object(gamma_client.requests, "post", return_value=_resp(201, {"generationId": "g1"})) as post, \
         mock.patch.object(gamma_client.requests, "get", return_value=_resp(200, done)), \
         contextlib.redirect_stdout(io.StringIO()):
        result = generate_presentation("x", api_key="k", poll_interval=0)
    sent = post.call_args.kwargs["json"]
    assert sent["folderId"] == GENERATION_PARAMS["folderId"] and "folderIds" not in sent
    assert result == {"gammaUrl": done["gammaUrl"], "exportUrl": done["exportUrl"], "generationId": "g1"}
    print("✓ 创建 + 轮询成功路径")


if __name__ == "__main__":
    test_params_use_folder_id()
    test_400_returns_none_and_logs_body()
    test_missing_key_skips()
    test_happy_path()
    print("\n全部通过")

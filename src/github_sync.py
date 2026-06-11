"""
GitHub 同步模块

把请假登记产生的 config/employees.yaml 变更通过 GitHub Contents API
直接提交到仓库 main 分支，解决 Streamlit Cloud 文件系统易失、
周五 CI（从 git checkout 读配置）看不到前端录入请假的问题。

设计要点：
- 不 import streamlit，token 由调用方（app.py）传入
- 安全写路径：先 GET 仓库最新内容 → 对最新内容做变换 → 带 sha PUT 回写，
  绝不以本地（可能过期的）文件为变换基准
- sha 冲突（并发提交）自动重拉重试一次
- employees.yaml 仅几 KB，远低于 Contents API 1MB GET 上限
"""
import base64
import os
from pathlib import Path
from typing import Optional, Tuple

import requests

from config import add_leave_to_yaml_text, EMPLOYEES_FILE

GITHUB_API = "https://api.github.com"
DEFAULT_REPO = "ruomeihu/timesheet_analyzer"
EMPLOYEES_REPO_PATH = "config/employees.yaml"
DEFAULT_BRANCH = "main"
_TIMEOUT = 15
_MAX_ATTEMPTS = 2  # 首次 + sha 冲突重试一次


class GitHubSyncError(Exception):
    """GitHub 同步失败，message 为可直接展示给用户的中文说明"""


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _contents_url(repo: str, path: str) -> str:
    return f"{GITHUB_API}/repos/{repo}/contents/{path}"


def fetch_repo_file(token: str, repo: str, path: str = EMPLOYEES_REPO_PATH,
                    ref: str = DEFAULT_BRANCH) -> Tuple[str, str]:
    """获取仓库文件最新内容与 blob sha。返回 (text, sha)。"""
    try:
        resp = requests.get(
            _contents_url(repo, path),
            headers=_headers(token),
            params={"ref": ref},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        raise GitHubSyncError(f"网络错误，无法连接 GitHub：{e}") from e

    if resp.status_code in (401, 403):
        raise GitHubSyncError("GitHub Token 无效或权限不足（需要该仓库 Contents 读写权限）")
    if resp.status_code == 404:
        raise GitHubSyncError(f"仓库或文件未找到：{repo}/{path}")
    if resp.status_code != 200:
        raise GitHubSyncError(f"GitHub API 错误 {resp.status_code}：{resp.text[:200]}")

    data = resp.json()
    text = base64.b64decode(data["content"]).decode("utf-8")
    return text, data["sha"]


def put_repo_file(token: str, repo: str, path: str, new_text: str, sha: str,
                  message: str, branch: str = DEFAULT_BRANCH) -> requests.Response:
    """带 sha 回写仓库文件。返回原始 Response，由调用方判读状态码（含冲突重试）。"""
    body = {
        "message": message,
        "content": base64.b64encode(new_text.encode("utf-8")).decode("ascii"),
        "sha": sha,
        "branch": branch,
    }
    try:
        return requests.put(
            _contents_url(repo, path),
            headers=_headers(token),
            json=body,
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        raise GitHubSyncError(f"网络错误，提交失败：{e}") from e


def _is_sha_conflict(resp: requests.Response) -> bool:
    if resp.status_code == 409:
        return True
    if resp.status_code == 422 and "sha" in resp.text.lower():
        return True
    return False


def push_leave_to_github(token: str, name_cn: str, start: str, end: str,
                         leave_type: str, note: str = "",
                         repo: Optional[str] = None,
                         local_path: Optional[Path] = None) -> dict:
    """
    把一条请假记录提交到 GitHub 仓库的 config/employees.yaml（main 分支）。

    流程：GET 最新内容+sha → add_leave_to_yaml_text 变换 → PUT 回写；
    sha 冲突自动重拉重试一次。成功后同步回写本地文件，让当前会话立即可见。

    Raises
    ------
    GitHubSyncError
        API/网络/权限/冲突重试失败
    ValueError
        name_cn 在仓库版 employees.yaml 中不存在（原样上抛，与同步错误区分）
    """
    repo = repo or os.getenv("GITHUB_REPO") or DEFAULT_REPO

    last_resp = None
    for _attempt in range(_MAX_ATTEMPTS):
        text, sha = fetch_repo_file(token, repo)
        new_text = add_leave_to_yaml_text(text, name_cn, start, end, leave_type, note)
        message = f"chore: 请假登记 {name_cn} {leave_type} {start}~{end} (via Streamlit)"

        resp = put_repo_file(token, repo, EMPLOYEES_REPO_PATH, new_text, sha, message)
        if resp.status_code in (200, 201):
            target = Path(local_path) if local_path else EMPLOYEES_FILE
            target.write_text(new_text, encoding="utf-8")
            commit = resp.json().get("commit", {})
            return {
                "ok": True,
                "commit_sha": commit.get("sha", ""),
                "html_url": commit.get("html_url", ""),
            }
        if _is_sha_conflict(resp):
            last_resp = resp
            continue
        raise GitHubSyncError(f"GitHub API 错误 {resp.status_code}：{resp.text[:200]}")

    raise GitHubSyncError(
        f"提交冲突且重试失败（{last_resp.status_code if last_resp else '未知'}），请稍后重试"
    )

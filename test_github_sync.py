"""
测试 GitHub 同步链路：
1. config.add_leave_to_yaml_text 纯变换（注释保留 / 追加不丢旧记录 / 未知员工报错）
2. src.github_sync.push_leave_to_github（mock requests）：
   happy path / sha 冲突重试 / 持续冲突 / 401

运行：python test_github_sync.py
"""
import base64
import tempfile
from pathlib import Path
from unittest import mock

import yaml as pyyaml

from config import add_leave_to_yaml_text
from src import github_sync
from src.github_sync import push_leave_to_github, GitHubSyncError

SAMPLE_YAML = '''# ============================================
# 员工配置文件（测试样例）
# ============================================
employees:
  # === 全职员工 ===
  - name_cn: "张三"
    name_en: "Zhang San"
    type: "全职"
    standard_hours: 40
    # 请假示例注释
  - name_cn: "李四"
    name_en: "Li Si"
    type: "全职"
    leaves:
      - start: "2026-01-05"
        end: "2026-01-06"
        type: "病假"
'''


def test_mutation_preserves_comments_and_appends():
    out = add_leave_to_yaml_text(SAMPLE_YAML, "张三", "2026-06-10", "2026-06-11", "年假", "陪家人就医")
    assert "# 员工配置文件（测试样例）" in out, "顶部注释丢失"
    assert "# === 全职员工 ===" in out, "行间注释丢失"
    assert "# 请假示例注释" in out, "员工内注释丢失"
    assert '- start: "2026-06-10"' in out, "新请假未按双引号格式写入"

    data = pyyaml.safe_load(out)
    zhang = next(e for e in data["employees"] if e["name_cn"] == "张三")
    assert zhang["leaves"] == [
        {"start": "2026-06-10", "end": "2026-06-11", "type": "年假", "note": "陪家人就医"}
    ]
    print("✅ test_mutation_preserves_comments_and_appends")


def test_mutation_appends_to_existing_leaves():
    out = add_leave_to_yaml_text(SAMPLE_YAML, "李四", "2026-06-12", "2026-06-12", "调休")
    data = pyyaml.safe_load(out)
    li = next(e for e in data["employees"] if e["name_cn"] == "李四")
    assert len(li["leaves"]) == 2, "追加后应有 2 条请假"
    assert li["leaves"][0]["type"] == "病假", "旧请假记录丢失"
    assert li["leaves"][1] == {"start": "2026-06-12", "end": "2026-06-12", "type": "调休"}
    assert "note" not in li["leaves"][1], "空备注不应写入 note 字段"
    print("✅ test_mutation_appends_to_existing_leaves")


def test_mutation_unknown_employee_raises():
    try:
        add_leave_to_yaml_text(SAMPLE_YAML, "王五", "2026-06-10", "2026-06-10", "事假")
        raise AssertionError("未知员工应抛 ValueError")
    except ValueError as e:
        assert "王五" in str(e)
    print("✅ test_mutation_unknown_employee_raises")


def _fake_get_response(text: str, sha: str):
    resp = mock.Mock()
    resp.status_code = 200
    resp.json.return_value = {
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "sha": sha,
    }
    return resp


def _fake_put_response(status: int, body_text: str = "", commit_sha: str = "abc123"):
    resp = mock.Mock()
    resp.status_code = status
    resp.text = body_text
    resp.json.return_value = {
        "commit": {"sha": commit_sha, "html_url": f"https://github.com/x/commit/{commit_sha}"}
    }
    return resp


def test_push_happy_path():
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        local_path = Path(f.name)
    try:
        with mock.patch.object(github_sync, "requests") as m_req:
            m_req.RequestException = Exception
            m_req.get.return_value = _fake_get_response(SAMPLE_YAML, "sha-001")
            m_req.put.return_value = _fake_put_response(201)

            result = push_leave_to_github(
                "tok", "张三", "2026-06-10", "2026-06-11", "年假",
                repo="owner/repo", local_path=local_path,
            )

            assert result["ok"] and result["commit_sha"] == "abc123"
            assert m_req.get.call_count == 1 and m_req.put.call_count == 1

            put_kwargs = m_req.put.call_args.kwargs
            body = put_kwargs["json"]
            assert body["sha"] == "sha-001", "PUT 必须带 GET 拿到的 sha"
            assert body["branch"] == "main"
            assert body["message"] == "chore: 请假登记 张三 年假 2026-06-10~2026-06-11 (via Streamlit)"

            pushed_text = base64.b64decode(body["content"]).decode("utf-8")
            data = pyyaml.safe_load(pushed_text)
            zhang = next(e for e in data["employees"] if e["name_cn"] == "张三")
            assert zhang["leaves"][0]["start"] == "2026-06-10", "提交内容应含新请假"

            assert local_path.read_text(encoding="utf-8") == pushed_text, "成功后应回写本地文件"
    finally:
        local_path.unlink(missing_ok=True)
    print("✅ test_push_happy_path")


def test_push_conflict_retry_succeeds():
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        local_path = Path(f.name)
    try:
        with mock.patch.object(github_sync, "requests") as m_req:
            m_req.RequestException = Exception
            m_req.get.side_effect = [
                _fake_get_response(SAMPLE_YAML, "sha-001"),
                _fake_get_response(SAMPLE_YAML, "sha-002"),
            ]
            m_req.put.side_effect = [
                _fake_put_response(409, "conflict"),
                _fake_put_response(200, commit_sha="def456"),
            ]

            result = push_leave_to_github(
                "tok", "张三", "2026-06-10", "2026-06-11", "年假",
                repo="owner/repo", local_path=local_path,
            )
            assert result["ok"] and result["commit_sha"] == "def456"
            assert m_req.get.call_count == 2, "冲突后应重新 GET"
            assert m_req.put.call_count == 2
            assert m_req.put.call_args.kwargs["json"]["sha"] == "sha-002", "重试应使用新 sha"
    finally:
        local_path.unlink(missing_ok=True)
    print("✅ test_push_conflict_retry_succeeds")


def test_push_persistent_conflict_raises():
    with mock.patch.object(github_sync, "requests") as m_req:
        m_req.RequestException = Exception
        m_req.get.return_value = _fake_get_response(SAMPLE_YAML, "sha-001")
        m_req.put.return_value = _fake_put_response(409, "conflict")
        try:
            push_leave_to_github("tok", "张三", "2026-06-10", "2026-06-11", "年假", repo="o/r")
            raise AssertionError("持续冲突应抛 GitHubSyncError")
        except GitHubSyncError as e:
            assert "冲突" in str(e)
        assert m_req.put.call_count == 2, "应恰好尝试 2 次"
    print("✅ test_push_persistent_conflict_raises")


def test_push_bad_token_raises():
    with mock.patch.object(github_sync, "requests") as m_req:
        m_req.RequestException = Exception
        bad = mock.Mock()
        bad.status_code = 401
        m_req.get.return_value = bad
        try:
            push_leave_to_github("bad-tok", "张三", "2026-06-10", "2026-06-11", "年假", repo="o/r")
            raise AssertionError("401 应抛 GitHubSyncError")
        except GitHubSyncError as e:
            assert "Token" in str(e)
    print("✅ test_push_bad_token_raises")


if __name__ == "__main__":
    test_mutation_preserves_comments_and_appends()
    test_mutation_appends_to_existing_leaves()
    test_mutation_unknown_employee_raises()
    test_push_happy_path()
    test_push_conflict_retry_succeeds()
    test_push_persistent_conflict_raises()
    test_push_bad_token_raises()
    print("\n🎉 全部测试通过")

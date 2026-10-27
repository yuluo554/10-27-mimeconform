"""布局门 / 脱敏门的常驻测试。

**只测"门的运行时形态"，不断言"当前仓库 0 FAIL"以外的未来态**：
发布里程碑未完成时 `LAYOUT.RELEASE` 本来就报 PASS 并写"不适用"，
所以此处可以断言"当前全绿"——它测的是"这道门在当前树上是可跑的、且逐条都给出了结论"。

判据：
1. 门能起来并给出**每一条**结论（`id` 集合固定）；
2. 非空跑自证：扫到的计数全部 > 0；
3. 当前仓库全绿（红 = 布局真的缺件，不是测试该跳过）；
4. 门永不崩：被检查对象缺失时报 FAIL 而不是异常逃逸（由 `run_gate` 的 try/except 保证，
   这里用一个临时根目录构造缺件态验证）。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def load_tool(name: str):
    """按文件路径装载 `tools/*.py`（不经包导入，避免 `tools` 不是包的问题）。

    **必须注册进 `sys.modules`**：`@dataclass(slots=True)` 在创建类时按
    ``cls.__module__`` 回查模块，未注册会得到 ``None`` → ``AttributeError``。
    """
    module_name = f"_tool_{name}"
    spec = importlib.util.spec_from_file_location(module_name, TOOLS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _token(*parts: str) -> str:
    """运行时拼接被测词面。

    **为什么拼接**：本文件要注入"本机路径 / 用户名 / 回环端口"的样本，
    但本文件自己也在脱敏门的扫描面内 —— 直接写完整字面量会让门常驻报红。
    拼接让"源码零词面"成立，同时样本在运行时仍是完整形态（判据不变）。
    """
    return "".join(parts)


@pytest.fixture(scope="module")
def layout():
    return load_tool("check_sprint_layout")


def test_layout_gate_is_green(layout) -> None:
    checks, scanned = layout.run_gate()
    failed = [(cid, detail) for cid, ok, detail in checks if not ok]
    assert not failed, f"布局门 FAIL: {failed}"
    assert checks, "布局门一条判据都没产出"


def test_layout_gate_reports_every_check(layout) -> None:
    """判据的 id 集合固定 —— 新增判据必须同时更新此清单（防"判据悄悄消失"）。"""
    checks, _ = layout.run_gate()
    ids = {cid for cid, _ok, _detail in checks}
    expected = {
        "LAYOUT.FILES",
        "LAYOUT.BINDING_HEAD",
        "LAYOUT.SECTIONS",
        "LAYOUT.STATUS",
        "LAYOUT.HANDOFFS",
        "LAYOUT.GAPS",
        "LAYOUT.LEDGER",
        "LAYOUT.RELEASE",
        "LAYOUT.DOC_TOOLS",
    }
    assert ids == expected, f"判据集合变了: 多 {ids - expected}，少 {expected - ids}"


def test_layout_gate_scanned_counts_are_visible(layout) -> None:
    """非空跑自证：0 命中与"没扫到"必须在输出里可区分。"""
    _checks, scanned = layout.run_gate()
    assert scanned.get("files", 0) >= 10, f"只扫到 {scanned.get('files')} 份必备文件"
    assert scanned.get("sections", 0) >= 7, f"只扫到 {scanned.get('sections')} 份含小节文档"
    assert scanned.get("ledger", 0) == 1, "台账未参与判定"
    assert scanned.get("doc_tools", 0) >= 2, "文档点名的 tools/ 脚本为 0 —— 判据是空的"


def test_layout_gate_status_copies_all_contribute_rows(layout) -> None:
    """每份状态副本都必须真的被读到行（假门族 ⑪：配了 3 处、实际判 2 处）。"""
    checks, scanned = layout.run_gate()
    detail = next(d for cid, _ok, d in checks if cid == "LAYOUT.STATUS")
    rows_text = detail.split("行数 ", 1)[1].rstrip("）")
    rows_by_copy = dict(item.rsplit(":", 1) for item in rows_text.split())
    for rel, _kind in layout.STATUS_COPIES:
        name = rel.split("/")[-1]
        assert name in rows_by_copy, f"结论行里看不到副本 {rel} 的命中行数: {detail}"
        assert int(rows_by_copy[name]) > 0, (
            f"状态副本 {rel} 贡献 0 行（它不参与判定，但被报成已核对）"
        )
    assert scanned.get("files", 0) > 0


def test_layout_gate_survives_missing_files(tmp_path: Path, layout) -> None:
    """永不崩：必备件全缺时要报 FAIL 并继续，不是异常逃逸。"""
    original = layout.ROOT
    try:
        layout.ROOT = tmp_path
        checks, _scanned = layout.run_gate()
    finally:
        layout.ROOT = original
    assert checks, "缺件态下一条结论都没有 —— 门崩了"
    failed = [cid for cid, ok, _detail in checks if not ok]
    assert "LAYOUT.FILES" in failed
    assert "LAYOUT.BINDING_HEAD" in failed


def test_layout_gate_cli_exit_codes(layout) -> None:
    """CLI 形态：当前树 rc=0；`--json` 也可被机器消费。"""
    result = subprocess.run(
        [sys.executable, str(TOOLS / "check_sprint_layout.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "结论: 全绿" in result.stdout

    as_json = subprocess.run(
        [sys.executable, str(TOOLS / "check_sprint_layout.py"), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert as_json.returncode == 0
    import json

    payload = json.loads(as_json.stdout)
    assert payload["failed"] == 0
    assert payload["scanned"]["doc_tools"] >= 2


def test_unknown_argument_is_usage_error() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "check_sprint_layout.py"), "--bogus"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 2, "用法错误必须是 2（门的契约：0 绿 / 1 FAIL / 2 用法）"


# ── 脱敏门 ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def desens():
    return load_tool("check_desensitized")


def test_desensitized_gate_is_green(desens) -> None:
    hits, scanned = desens.scan(ROOT)
    assert not hits, "脱敏门命中:\n" + "\n".join(hits)
    assert scanned > 0, "扫描面为 0 —— 门是空转的"


def test_desensitized_patterns_are_shape_independent(desens, tmp_path: Path) -> None:
    """四条规则各注入一次，必须逐条命中（阳性对照）。"""
    samples = {
        "absolute-session-path": _token("path = ", "C:", "/Users/", "realperson/x\n"),
        "msys-user-path": _token("p=", "/c/", "Users/", "realperson/x\n"),
        "host-username": _token("runner: ", "AS", "US", "\n"),
        "loopback-proxy": _token("proxy=http://127.0.0.", "1:", "7897\n"),
    }
    for rule_id, line in samples.items():
        target = tmp_path / f"{rule_id}.txt"
        target.write_text(line, encoding="utf-8")
        hits, _scanned = desens.scan(tmp_path)
        assert any(f"[{rule_id}]" in hit for hit in hits), f"规则 {rule_id} 未命中: {hits}"
        target.unlink()


def test_desensitized_placeholders_are_allowed(desens, tmp_path: Path) -> None:
    """阴性对照：占位符是脱敏后的**正确**写法，必须放行。"""
    (tmp_path / "ok.md").write_text(
        "go-sdk 在 C:/Users/<user>/go-sdk 下；仓库 <repo>；代理 127.0.0.1:<port>\n",
        encoding="utf-8",
    )
    hits, _scanned = desens.scan(tmp_path)
    assert not hits, f"占位符被误判: {hits}"


def test_desensitized_skips_local_artifacts(desens, tmp_path: Path) -> None:
    """`.gitignore` 声明的本地产物目录不得被扫（否则 CI 里永远是假红）。"""
    venv = tmp_path / ".venv-readme" / "Scripts"
    venv.mkdir(parents=True)
    venv.joinpath("Activate.ps1").write_text(
        _token("Example: ", "C:", "/Users/", "someone/Common/.venv\n"), encoding="utf-8"
    )
    hits, _scanned = desens.scan(tmp_path)
    assert not hits, f"本地环境目录未被收编: {hits}"


def test_desensitized_cli_exit_codes(desens) -> None:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "check_desensitized.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 命中" in result.stdout

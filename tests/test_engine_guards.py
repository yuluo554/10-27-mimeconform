"""引擎守门：AST 静态断言（不 import email / 零网络 / 不读时钟 / 依赖方向）。

**为什么用 AST 而不是 `grep`**：字符串搜索会被注释、docstring、字符串字面量误伤，
也会漏掉 `from .. import X`（相对导入时 `node.module is None`）与 `import a.b` 两种形态
（skill「探针自证只覆盖一种写法」形态）。本模块**逐形态**检测，并有 `test_probe_self_check`
证明探针真的能命中每种写法。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "mimeconform"

#: 报告路径（引擎 + 台账 + 渲染 + CLI）。devtools 是唯一允许 import email 的地方。
ENGINE_MODULES = (
    "scan.py",
    "headers.py",
    "transfer.py",
    "attribution.py",
    "container.py",
    "ledger.py",
    "report.py",
    "cli.py",
    "model.py",
    "errors.py",
    "exit_codes.py",
    "constants.py",
    "_pending.py",
    "rules/__init__.py",
)

FORBIDDEN_NETWORK = frozenset({"socket", "urllib", "http", "ftplib", "smtplib", "ssl", "telnetlib", "xmlrpc"})
FORBIDDEN_CLOCK = frozenset({"time", "datetime"})


def _module_files() -> list[Path]:
    return [PKG / name for name in ENGINE_MODULES]


def _imported_names(tree: ast.AST) -> set[str]:
    """收集一个模块里出现的全部被导入名（**逐形态**）。

    * ``import a.b``          → {"a", "a.b"}
    * ``from a.b import c``   → {"a", "a.b", "a.b.c"}
    * ``from . import x``     → {"x"}（相对导入 module 为 None，名字在 names 里）
    * ``from .. import x``    → {"x"}
    * ``importlib.import_module("a")`` → {"a"}（动态导入也算）
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                head = alias.name.split(".")[0]
                names.add(head)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
                names.add(node.module.split(".")[0])
                for alias in node.names:
                    names.add(f"{node.module}.{alias.name}")
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.Call):
            func = node.func
            fname = None
            if isinstance(func, ast.Attribute):
                fname = func.attr
            elif isinstance(func, ast.Name):
                fname = func.id
            if fname in {"import_module", "__import__"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names.add(first.value)
                    names.add(first.value.split(".")[0])
    return names


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_all_engine_modules_exist() -> None:
    missing = [path.name for path in _module_files() if not path.is_file()]
    assert not missing, f"引擎模块缺失: {missing}"


@pytest.mark.parametrize("name", ENGINE_MODULES)
def test_no_email_import(name: str) -> None:
    """审计引擎**不得** import `email`（plan/00 D6：被审计对象）。"""
    names = _imported_names(_parse(PKG / name))
    offenders = {n for n in names if n == "email" or n.startswith("email.")}
    assert not offenders, (
        f"{name} 导入了 email（{sorted(offenders)}）：标准库的宽松行为正是被审计对象，"
        "用它会把结论变成照抄（plan/00 D6）。唯一例外是 devtools/stdlib_compare.py。"
    )


@pytest.mark.parametrize("name", ENGINE_MODULES)
def test_no_network_import(name: str) -> None:
    """零网络：不得 import 任何网络栈（README 的零网络声明是硬约束）。"""
    names = _imported_names(_parse(PKG / name))
    offenders = {n for n in names if n.split(".")[0] in FORBIDDEN_NETWORK}
    assert not offenders, f"{name} 导入了网络栈（{sorted(offenders)}）：本项目零网络。"


@pytest.mark.parametrize("name", ENGINE_MODULES)
def test_no_clock(name: str) -> None:
    """不读时钟：输出确定性（plan/02 §九）。"""
    tree = _parse(PKG / name)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_CLOCK:
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in FORBIDDEN_CLOCK:
                offenders.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Attribute):
            if node.attr in {"now", "utcnow", "today", "time", "monotonic", "perf_counter"}:
                value = node.value
                if isinstance(value, ast.Name) and value.id in {"datetime", "time", "date"}:
                    offenders.append(f"{value.id}.{node.attr}")
    assert not offenders, f"{name} 读时钟（{offenders}）：输出必须确定性。"


def test_devtools_isolation() -> None:
    """`report.py` / `cli.py` 不得 import devtools（stdlib_compare 只在测试/证据里用）。"""
    for name in ("report.py", "cli.py"):
        names = _imported_names(_parse(PKG / name))
        offenders = {n for n in names if "devtools" in n}
        assert not offenders, f"{name} 导入了 devtools（{sorted(offenders)}）：它不在报告路径上。"


def test_report_has_no_engine_imports() -> None:
    """渲染层零判定：`report.py` 不 import 任何业务判定模块（plan/03 §七）。"""
    names = _imported_names(_parse(PKG / "report.py"))
    forbidden = {"scan", "headers", "transfer", "attribution", "container", "exit_codes"}
    offenders = {
        n
        for n in names
        if n in forbidden or n.split(".")[-1] in forbidden or n.startswith("mimeconform.") and n.split(".")[-1] in forbidden
    }
    # 允许 import 的自家模块只有 __init__ / constants / ledger（后者只为了 dumps 序列化入口）
    assert not offenders, f"report.py 导入了判定模块（{sorted(offenders)}）：渲染层只做格式化。"


def test_scan_does_not_import_higher_layers() -> None:
    """依赖方向：`scan.py` 只可 import 基础设施（plan/02 §一 R-B）。"""
    names = _imported_names(_parse(PKG / "scan.py"))
    self_modules = {"headers", "transfer", "attribution", "container", "report", "cli"}
    offenders = {n for n in names if n.split(".")[-1] in self_modules}
    assert not offenders, f"scan.py 导入了上层模块（{sorted(offenders)}）：反向依赖会让分层失效。"


def test_attribution_does_not_import_higher_layers() -> None:
    """依赖方向：`attribution.py` 可 import `headers`（取 filename），**不得**上行。

    `HANDOFF-M5` §二.11：分层纪律同样适用于 `attribution` / `container` —— 只查 `scan` 会漏掉
    "新模块悄悄反向依赖"这条最可能的漂移。
    """
    names = _imported_names(_parse(PKG / "attribution.py"))
    forbidden = {"scan", "transfer", "container", "report", "cli"}
    offenders = {n for n in names if n.split(".")[-1] in forbidden}
    assert not offenders, f"attribution.py 导入了不该 import 的模块（{sorted(offenders)}）。"


def test_container_does_not_import_higher_layers() -> None:
    """依赖方向：`container.py` 在最底层 —— 不得 import 任何业务模块（只看容器字节）。"""
    names = _imported_names(_parse(PKG / "container.py"))
    forbidden = {"scan", "headers", "transfer", "attribution", "report", "cli"}
    offenders = {n for n in names if n.split(".")[-1] in forbidden}
    assert not offenders, f"container.py 导入了上层模块（{sorted(offenders)}）。"


def test_transfer_and_attribution_do_not_import_each_other() -> None:
    """`transfer` 与 `attribution` 是同层，互不依赖（同层互相 import 会把分层变成一张网）。"""
    for name, other in (("transfer.py", "attribution"), ("attribution.py", "transfer")):
        names = _imported_names(_parse(PKG / name))
        offenders = {n for n in names if n.split(".")[-1] == other}
        assert not offenders, f"{name} import 了同层的 {other}（{sorted(offenders)}）。"


def test_probe_self_check(tmp_path: Path) -> None:
    """**探针自证**：每个被禁形态都必须能被检出，否则守门是假门。"""
    samples = {
        "absolute": "import email\n",
        "abs_sub": "import email.parser\n",
        "from_abs": "from email import policy\n",
        "from_abs_sub": "from email.mime.text import MIMEText\n",
        "relative_names": "from . import email\n",
        "relative_deep": "from .. import email\n",
        "dynamic": "import importlib\nimportlib.import_module('email')\n",
    }
    for label, source in samples.items():
        path = tmp_path / f"{label}.py"
        path.write_text(source, encoding="utf-8")
        names = _imported_names(_parse(path))
        assert "email" in names or any(n.startswith("email.") for n in names), (
            f"探针漏检出形态 {label!r}：{source!r} → {sorted(names)}"
        )

    # 阴性对照：只是提到 'email' 这个词（注释 / 字符串）不得算导入
    clean = tmp_path / "clean.py"
    clean.write_text(
        '# 这里解释为什么不用 email\nDOC = "email 是最容易被误用的模块"\nimport json\n',
        encoding="utf-8",
    )
    names = _imported_names(_parse(clean))
    assert not any(n == "email" or n.startswith("email.") for n in names), (
        f"探针假阳性：注释/字符串里的 email 被当成导入 → {sorted(names)}"
    )

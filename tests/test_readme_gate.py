"""三面对账：README 指令面 ↔ CLI 参数面 ↔ 安装面（skill 阶段 6「安装面」）。

M0 落地的三面：
1. **README 命令 → parser 反射**：README 里出现的 `mimeconform ...` 命令行，逐个 `parse_args`
   不得抛用法错误（否则用户照抄即 exit 1）；
2. **README 提到的 tools 脚本 → 实物存在**；
3. **README 的 extras ↔ pyproject 的 optional-dependencies 双向**。
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from mimeconform.cli import build_parser
from mimeconform.errors import UsageError

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


def _command_lines() -> list[str]:
    """抽出 README 代码块里以 `mimeconform` 开头的命令行。"""
    lines: list[str] = []
    in_block = False
    for raw in _readme_text().split("\n"):
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            continue
        if not in_block or not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("mimeconform "):
            lines.append(stripped)
    return lines


def test_readme_commands_are_parseable() -> None:
    """每条 README 命令都必须能被 parser 接受（不是"看起来像"）。

    用 ``shlex`` 切分并把它当 shell 用：``#`` 后的行内注释是合法 shell 语法，
    不是参数 —— 用户照抄不会带注释进去。
    """
    commands = _command_lines()
    assert commands, "README 里一条 mimeconform 命令行都没抽到 —— 探针失效"
    parser = build_parser()
    for command in commands:
        tokens = shlex.split(command, comments=True)
        assert tokens and tokens[0] == "mimeconform", f"命令行形态异常: {command!r}"
        argv = [
            token.replace("sample.eml", "x.eml").replace("sample.mbox", "x.mbox")
            for token in tokens[1:]
        ]
        try:
            parser.parse_args(argv)
        except UsageError as exc:
            pytest.fail(f"README 命令 parser 不认: {command!r} → {exc}")
        except SystemExit as exc:  # `--version` 会抛 SystemExit(0)
            assert exc.code == 0, f"README 命令解析异常退出: {command!r} → {exc.code}"


def test_readme_commands_cover_all_subcommands() -> None:
    """反向覆盖：每个子命令至少被 README 提到一次。"""
    text = _readme_text()
    for subcommand in ("audit", "selftest"):
        assert f"mimeconform {subcommand}" in text, f"README 没有演示子命令 {subcommand}"


def test_readme_tool_paths_exist() -> None:
    """README 里写的 `tools/*.py` 必须真有实物。"""
    paths = set(re.findall(r"(?<![\w/])tools/[\w.-]+\.py", _readme_text()))
    assert paths, "README 没提任何 tools/ 脚本 —— 探针失效"
    missing = [rel for rel in paths if not (ROOT / rel).is_file()]
    assert not missing, f"README 点名但实物不存在: {missing}"


def test_readme_install_extras_match_pyproject() -> None:
    """README 的 extras 与 pyproject 双向一致（`[dev]` 写了就必须真存在）。"""
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = set(pyproject["project"].get("optional-dependencies", {}))
    referenced = set(re.findall(r"\[([a-zA-Z0-9_,-]+)\]", _readme_text()))
    extras_in_readme = set()
    for group in referenced:
        extras_in_readme.update(part.strip() for part in group.split(",") if part.strip())
    # 只关心形如 `.[dev]` / `.[dev,report]` 的 extras 引用
    referenced_dot = set(re.findall(r"\.\[([a-zA-Z0-9_,-]+)\]", _readme_text()))
    extras_in_readme = set()
    for group in referenced_dot:
        extras_in_readme.update(part.strip() for part in group.split(",") if part.strip())

    assert extras_in_readme, "README 没写任何 `.[extras]` 安装形态 —— 探针失效"
    unknown = extras_in_readme - declared
    assert not unknown, f"README 引用了 pyproject 未声明的 extras: {sorted(unknown)}"
    assert declared <= extras_in_readme | {"dev"}, f"pyproject 声明了 README 从未提及的 extras: {declared}"


def test_readme_states_python_floor() -> None:
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    floor = pyproject["project"]["requires-python"]
    major_minor = floor.replace(">=", "").strip()
    assert major_minor in _readme_text(), f"README 未写 Python 下限 {major_minor}"


def test_readme_exit_code_table_matches_constants() -> None:
    """README 的退出码表必须与 constants 的四档一致（文档不能各写一套）。"""
    from mimeconform import constants as C

    text = _readme_text()
    for code in (C.EXIT_OK, C.EXIT_USAGE, C.EXIT_MINOR, C.EXIT_MAJOR):
        assert f"`{code}`" in text, f"README 退出码表缺 {code}"

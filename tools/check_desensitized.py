#!/usr/bin/env python3
"""脱敏门：仓库内文本不得含本机路径 / 用户名 / 回环代理端口。

**为什么是常驻门而不是发布前 grep 一次**：每次续接对话都会往 AGENTS.md 与 HANDOFF
的「环境坑」区追加内容，这类内容天然带本机痕迹；一次性 grep 没有 CI 接线。

四条规则（每条一句判据，逐条可变异验证）：

1. `absolute-session-path` —— 盘符绝对路径（`<user>` 这类占位符放行）；
2. `msys-user-path` —— Git Bash 形态 `/c/Users/<name>/…`；
3. `host-username` —— 本机用户名；
4. `loopback-proxy` —— 回环地址带端口。

退出码：0 零命中 / 1 有命中 / 2 用法错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 自豁免面 = **文件集合**（本项目同时存在 .py 与 .mjs 两版门时逐条列全）。
SELF = frozenset({"tools/check_desensitized.py", "tools/check-desensitized.mjs"})

#: 不扫的目录。**凡 .gitignore 声明的本地产物/环境目录都必须在这里有对应项**。
SKIP_DIRS = frozenset(
    {
        ".git",
        ".mimosa",
        ".tmp",
        "tmp",
        "scratch",
        "dist",
        "dist-release",
        "release",
        "build",
        ".venv",
        "venv",
        "env",
        ".venv-readme",
        ".venv-ci",
        "node_modules",
        ".cache",
        ".pytest_cache",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
        "coverage",
        ".hypothesis",
    }
)

#: 名字随包名变的本地安装产物（`pip install -e .` 现生成）
SKIP_SUFFIXES = (".egg-info", ".dist-info")

#: 二进制/归档扩展名（不按文本扫）。
SKIP_EXTS = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".zip", ".gz", ".tgz",
        ".exe", ".dll", ".so", ".dylib", ".pyc", ".pyo", ".woff", ".woff2", ".ttf",
        ".eml", ".mbox", ".mbx",
    }
)

RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "absolute-session-path",
        # 盘符绝对路径；`<user>` / `<repo>` 这类占位符用负向前瞻放行。
        re.compile(r"\b[A-Za-z]:[\\/](?:ProgramData|Users|zcode|repos?|projects?)[\\/](?!<)"),
    ),
    (
        "msys-user-path",
        re.compile(r"/[a-z]/Users/(?!<)[A-Za-z0-9._-]+/"),
    ),
    (
        "host-username",
        # 本机用户名（实测值；换机器要改这一行——不要用环境实算，runner 上叫 runner）
        re.compile(r"\bASUS\b"),
    ),
    (
        "loopback-proxy",
        re.compile(r"\b127\.0\.0\.1:\d{2,5}\b"),
    ),
)


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        name = path.name
        if name == ".git":
            continue  # worktree 里 .git 是文件
        relative_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in relative_parts[:-1]):
            continue
        if any(part.endswith(SKIP_SUFFIXES) for part in relative_parts[:-1]):
            continue
        if path.suffix.lower() in SKIP_EXTS:
            continue
        rel = "/".join(relative_parts)
        if rel in SELF:
            continue
        yield path, rel


def scan(root: Path) -> tuple[list[str], int]:
    hits: list[str] = []
    scanned = 0
    for path, rel in iter_text_files(root):
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw:
            continue  # 二进制
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        for lineno, line in enumerate(text.split("\n"), start=1):
            for rule_id, pattern in RULES:
                if pattern.search(line):
                    hits.append(f"{rel}:{lineno}: [{rule_id}] {line.strip()[:160]}")
    return hits, scanned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="脱敏门：仓库内不得含本机痕迹")
    parser.add_argument("--root", default=str(ROOT), help="扫描根（默认仓库根）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write(f"check_desensitized: 根目录不存在: {root}\n")
        return 2

    hits, scanned = scan(root)
    if hits:
        sys.stdout.write(
            f"脱敏门：{len(hits)} 处命中（扫了 {scanned} 个文本文件，豁免 {len(SELF)} 份）\n"
        )
        for hit in hits:
            sys.stdout.write(f"FAIL  {hit}\n")
        return 1
    sys.stdout.write(f"脱敏门：扫了 {scanned} 个文本文件，0 命中（豁免 {len(SELF)} 份）\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

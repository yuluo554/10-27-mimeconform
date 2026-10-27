"""语料卫生门：`data/golden/**` 只允许合成样本（隐私红线）。

判据（`data/README.md` §六）：
* 域名必须是 `example.invalid`（RFC 2606 保留域）；不得出现其他真实 TLD；
* 地址只用 `alice@` / `bob@` 这类假名；
* `Message-ID` / `Content-ID` 用固定假串；
* 生成器 `--check` 逐字节核对（M1 落地后启用；此处先锁"扫描面非空"的探针）。

M0 阶段语料尚未落地，故本文件的判据分两段：
1. **探针自证**（现在就跑）：合成的"坏样本"必须被检出、好样本必须放行；
2. **仓库扫描**（M1 起有意义）：`data/golden` 不存在时显式 skip 并写明原因，不假装通过。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"

#: 允许的保留域（RFC 2606）。`example.com/.net/.org` 保留但**本仓不合规**——
#: 只认 `.invalid`（永不解析，语义最明确）。
ALLOWED_DOMAIN = "example.invalid"

#: 两级以上域名的通用形态；用于找"非保留域"。
_DOMAIN_RE = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+([a-z]{2,24})\b", re.IGNORECASE)

#: 结构性前缀（不是域名）：RFC 引用、文件名、MIME 类型。
#: 注意：**邮件地址只剥本地部分**（`alice@`），域名留下照旧被扫 ——
#: 否则 `alice@mail.google.com` 会被整串剥掉，真实域名漏检（阳性对照会红）。
_STRIP_PATTERNS = (
    re.compile(r"`[^`]*`"),
    re.compile(r"[\w./-]+\.(?:md|py|mjs|js|json|toml|txt|eml|mbox|png|pdf)"),
    re.compile(r"(?:text|multipart|message|application|image|audio|video)/[\w.+-]+"),
    re.compile(r"RFC\s?\d+(?:\.[\w]+)?"),
    re.compile(r"[\w.+-]+@"),
)


def find_foreign_domains(text: str) -> list[str]:
    """返回文本里出现的**非保留域**。"""
    stripped = text
    for pattern in _STRIP_PATTERNS:
        stripped = pattern.sub(" ", stripped)
    found: list[str] = []
    for match in _DOMAIN_RE.finditer(stripped):
        whole = match.group(0).lower()
        if whole.endswith(ALLOWED_DOMAIN):
            continue
        tld = match.group(1).lower()
        if tld in {"invalid", "local", "test"}:
            continue
        found.append(whole)
    return found


# ── 1. 探针自证（现在就跑）───────────────────────────────────────────────


def test_probe_detects_real_domains() -> None:
    """阳性对照：真实域名必须被检出（否则整个门是空的）。"""
    assert find_foreign_domains("发件人 alice@mail.google.com")
    assert find_foreign_domains("见 https://github.com/yuluo554/x")
    assert find_foreign_domains("Host: smtp.mail.yahoo.co.uk")


def test_probe_allows_reserved_domains() -> None:
    """阴性对照：保留域必须放行。"""
    assert not find_foreign_domains("from alice@example.invalid to bob@example.invalid")
    assert not find_foreign_domains("Message-ID: <fixed-0001@example.invalid>")


def test_probe_strips_structural_prefixes() -> None:
    """剥离规则要精准：剥掉结构前缀，剩下的真域名照旧被扫。"""
    # 行内代码 / 文件名 / MIME 类型 / RFC 引用不该被当成域名
    assert not find_foreign_domains("见 `README.md` 与 `data/README.md`；类型 text/plain；RFC 2046 §5.1.1")
    # 但同一段自由文本里的真域名仍要报
    assert find_foreign_domains("见 `README.md`，另见 mail.google.com")


# ── 2. 仓库扫描（M1 起才有对象）─────────────────────────────────────────


def _golden_files() -> list[Path]:
    if not GOLDEN.is_dir():
        return []
    return sorted(path for path in GOLDEN.rglob("*") if path.is_file())


def test_golden_dir_state_is_explicit() -> None:
    """语料未落地时必须"可见地缺席"，不能静默当通过（空分母 ≠ 通过）。"""
    files = _golden_files()
    if not files:
        pytest.skip("data/golden 尚无文件（里程碑 M1 落地）；本判据当前不适用，不是通过")


def test_golden_files_use_reserved_domains_only() -> None:
    files = _golden_files()
    if not files:
        pytest.skip("data/golden 尚无文件（里程碑 M1 落地）")
    offenders: list[str] = []
    for path in files:
        if path.suffix.lower() in {".png", ".pdf", ".jpg", ".gif", ".zip"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for domain in find_foreign_domains(text):
            offenders.append(f"{path.relative_to(ROOT)}: {domain}")
    assert not offenders, "语料里出现非保留域（隐私红线）：\n" + "\n".join(offenders)


def test_golden_files_are_committed_only_under_golden() -> None:
    """`.gitignore` 允许 `data/golden/**` 例外；其他位置的 `*.eml` 一律禁止入库。"""
    import subprocess

    if not (ROOT / ".git").exists():
        pytest.skip("不在 git 工作树里（发布包形态）——该判据只在开发树有意义")
    result = subprocess.run(
        ["git", "ls-files", "*.eml", "*.mbox"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    paths = [line.strip() for line in result.stdout.split("\n") if line.strip()]
    offenders = [p for p in paths if not p.startswith("data/golden/")]
    assert not offenders, f"真实邮件可能在入库: {offenders}"

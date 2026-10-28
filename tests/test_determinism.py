"""确定性：同一对象/同一输入两次产出必须逐字节一致。

M0 可测的部分（渲染层与序列化）：
* 同一台账对象 `dumps` 两次 → 相同；
* `render_json` / `render_markdown` 两次 → 相同；
* 不含时钟 / 绝对路径 / 主机名（AST 守门另有专测，此处验**产物字节**）。

M2 起补的**引擎层**双跑：`data/golden/**/*.eml` 逐个跑两遍 `scan_message` → `ledger.build`
→ `dumps`，两份字节必须逐字节一致（这是"结构指纹可作回归基线"的前提）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mimeconform import constants as C
from mimeconform.ledger import build, dumps
from mimeconform.model import Defect
from mimeconform.report import render_json, render_markdown

ROOT = Path(__file__).resolve().parents[1]
#: 单封邮件输入（容器输入另有一组，见下文 `CONTAINER_INPUTS`）。
EML_INPUTS = sorted((ROOT / "data" / "golden").glob("*/*.eml"))
#: 容器输入（M5 起）：`.mbox` 文件 + Maildir 目录（目录取 `cur/` / `new/` / `tmp/` 下的条目）。
MBOX_INPUTS = sorted((ROOT / "data" / "golden").glob("*/*.mbox"))
MAILDIR_INPUTS = sorted(path for path in (ROOT / "data" / "golden").glob("*/maildir") if path.is_dir())


def sample_ledger() -> dict[str, object]:
    defects = [
        Defect(
            rule_id="MC-B06",
            klass="hard",
            severity="major",
            path="0.1",
            offset=106,
            offset_kind="absolute",
            rfc="RFC 2046 §5.1.1",
            detail="nested multipart reuses outer boundary 'X'",
        ),
        Defect(
            rule_id="MC-T01",
            klass="diff",
            severity="note",
            path="0.2",
            offset=2048,
            offset_kind="absolute",
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="declared base64, observed plain text",
        ),
    ]
    return build(defects)


def test_dumps_is_byte_identical_across_calls() -> None:
    ledger = sample_ledger()
    assert dumps(ledger) == dumps(ledger)


def test_render_json_is_byte_identical_across_calls() -> None:
    ledger = sample_ledger()
    kwargs = dict(
        input_name="sample.eml",
        input_bytes=4096,
        input_sha256="f" * 64,
        exit_code=C.EXIT_MAJOR,
    )
    first = render_json(ledger, **kwargs)
    second = render_json(ledger, **kwargs)
    assert first == second
    json.loads(first)  # 必须是合法 JSON


def test_render_markdown_is_byte_identical_across_calls() -> None:
    ledger = sample_ledger()
    kwargs = dict(
        input_name="sample.eml",
        input_bytes=4096,
        input_sha256="f" * 64,
        exit_code=C.EXIT_MAJOR,
    )
    assert render_markdown(ledger, **kwargs) == render_markdown(ledger, **kwargs)


def test_json_and_markdown_share_the_same_numbers() -> None:
    """JSON/MD 同源：两份产物的计数与指纹必须一致（不是两套代码各算一次）。"""
    ledger = sample_ledger()
    kwargs = dict(
        input_name="sample.eml",
        input_bytes=4096,
        input_sha256="f" * 64,
        exit_code=C.EXIT_MAJOR,
    )
    payload = json.loads(render_json(ledger, **kwargs))
    markdown = render_markdown(ledger, **kwargs)
    assert payload["summary"]["count"] == ledger["count"]
    assert payload["fingerprint"] in markdown
    assert f"缺陷总数: {ledger['count']}" in markdown
    for rule_id in ("MC-B06", "MC-T01"):
        assert rule_id in markdown


def test_output_has_no_environment_fingerprints() -> None:
    """产物不得出现时间戳 / 主机名 / 绝对路径（确定性设计，plan/02 §九）。"""
    ledger = sample_ledger()
    kwargs = dict(
        input_name="sample.eml",
        input_bytes=4096,
        input_sha256="f" * 64,
        exit_code=C.EXIT_MAJOR,
    )
    for text in (render_json(ledger, **kwargs), render_markdown(ledger, **kwargs)):
        assert not re.search(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}", text), "产物里出现了时间戳"
        assert not re.search(r"\b[A-Za-z]:[\\/]", text), "产物里出现了盘符绝对路径"
        assert "Users" not in text


def test_json_uses_ascii_escapes_for_non_ascii() -> None:
    """`ensure_ascii=True`：跨平台 stdout 编码差异不影响字节。"""
    ledger = build(
        [
            Defect(
                rule_id="MC-H09",
                klass="diff",
                severity="note",
                path="0",
                offset=0,
                offset_kind="absolute",
                rfc=C.RFC_NONE_BY_DESIGN,
                detail="附件名缺 *0 序号",
            )
        ]
    )
    text = dumps(ledger)
    assert "\\u" in text
    assert "附件名" not in text


# ── 引擎层双跑（M2 起）───────────────────────────────────────────────────


def _engine_ledger_bytes(path: Path) -> bytes:
    """跑完整单封链路（扫描 + 头编码 + 传输编码 + 归属 → 台账 → 序列化）并返回产物字节。"""
    from mimeconform.attribution import audit_attribution
    from mimeconform.headers import audit_headers
    from mimeconform.scan import scan_message
    from mimeconform.transfer import audit_transfer

    data = path.read_bytes()
    result = scan_message(data)
    defects = (
        tuple(result.defects)
        + audit_headers(result.root, data)
        + audit_transfer(result.root, data)
        + audit_attribution(result.root, data).defects
    )
    ledger = build(defects, result.root)
    return dumps(ledger).encode("utf-8")


def _container_ledger_bytes(path: Path) -> bytes:
    """跑完整容器链路（切分/变体表 → 台账 → 序列化）并返回产物字节。"""
    from mimeconform.container import audit_maildir, split_container

    if path.is_dir():
        result = audit_maildir(path)
    else:
        result = split_container(path.read_bytes(), variant=C.MBOX_VARIANT_DEFAULT)
    ledger = build(result.defects)
    payload = {
        "ledger": ledger,
        "primary_variant": result.primary_variant,
        "variant_counts": {name: len(spans) for name, spans in result.split_variants.items()},
        "entries": list(result.entries),
    }
    return dumps(payload).encode("utf-8")


def test_eml_corpus_exposes_a_nonempty_denominator() -> None:
    """非空跑自证：没有 `.eml` 输入时下面的判据是空转的。"""
    assert len(EML_INPUTS) >= 40, f"只扫到 {len(EML_INPUTS)} 个 .eml 输入"


@pytest.mark.parametrize("path", EML_INPUTS, ids=lambda p: p.parent.name)
def test_engine_double_run_is_byte_identical(path: Path) -> None:
    """同一输入双跑 → 账本字节逐字节一致（plan/05 §二 M2 DoD）。"""
    assert _engine_ledger_bytes(path) == _engine_ledger_bytes(path)


def test_container_corpus_exposes_a_nonempty_denominator() -> None:
    """非空跑自证：没有容器输入时下面的判据是空转的。"""
    assert len(MBOX_INPUTS) >= 5, f"只扫到 {len(MBOX_INPUTS)} 个 .mbox 输入"
    assert len(MAILDIR_INPUTS) >= 1, f"只扫到 {len(MAILDIR_INPUTS)} 个 Maildir 目录"


@pytest.mark.parametrize("path", MBOX_INPUTS + MAILDIR_INPUTS, ids=lambda p: p.parent.name)
def test_container_double_run_is_byte_identical(path: Path) -> None:
    """容器路径（切分表 + 变体条数 + 台账）双跑逐字节一致（M5 DoD）。"""
    assert _container_ledger_bytes(path) == _container_ledger_bytes(path)


def test_engine_output_has_no_environment_fingerprints() -> None:
    """引擎产物同样不得出现时间戳 / 盘符路径 / 主机名（确定性设计）。"""
    text = _engine_ledger_bytes(ROOT / "data" / "golden" / "b-inner-dup" / "msg.eml").decode("utf-8")
    assert not re.search(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}", text), "产物里出现了时间戳"
    assert not re.search(r"\b[A-Za-z]:[\\/]", text), "产物里出现了盘符绝对路径"
    assert "Users" not in text

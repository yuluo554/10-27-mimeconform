"""确定性：同一对象/同一输入两次产出必须逐字节一致。

M0 可测的部分（渲染层与序列化）：
* 同一台账对象 `dumps` 两次 → 相同；
* `render_json` / `render_markdown` 两次 → 相同；
* 不含时钟 / 绝对路径 / 主机名（AST 守门另有专测，此处验**产物字节**）。

M2 起补"同一 `.eml` 双跑账本 `cmp` 一致"（届时追加到本文件）。
"""

from __future__ import annotations

import json
import re

from mimeconform import constants as C
from mimeconform.ledger import build, dumps
from mimeconform.model import Defect
from mimeconform.report import render_json, render_markdown


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

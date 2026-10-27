"""golden 语料生成器（里程碑 M1 落地）。

**设计要点（`plan/04` §三）**：

* 每个 case 是**纯函数**，返回 ``(files, expect)``；生成器只做拼装，**不解析、不判定**。
  期望缺陷是手写常量 + 构造期的结构性断言（锚点必须存在、正例文件必须真含声称的字节），
  不是"跑一遍工具看输出"（避免真值 = 被测实现）。
* 写盘一律 ``write_bytes()``（不用文本模式：Windows 会把 ``\\n`` 翻成 ``\\r\\n``，
  而 golden 的字节本身就是被测对象）。
* ``_self_check()`` 必须挂在 :func:`build` 里（不是 ``__main__``）——``--check`` 走
  ``build()``，写错位置等于自检在门下从没跑过。
* ``--check`` 在**系统临时目录**里重建再逐字节比对，不在仓库内留产物。

**构造纪律**：

1. ``offset`` 一律用**构造期锚点**（:func:`_off` / :func:`_line_start`）解析 —— 手写数字
   一定会在某次拼接调整后悄悄错位；锚点不存在时**构造期断言**直接失败。
2. ``defect_count`` / ``exit_code`` / ``fingerprint`` **由构造算出**
   （``len(defects)`` / ``decide_exit_code`` / ``ledger.fingerprint``），不手写魔数。
3. ``tree_digest`` 在 M1 为 ``null`` —— 树由引擎在 M2 产出后回填（数据级自检允许 null）。
4. README 一律用 **issue / SO 编号** 指来源，**不写 URL、不写真实域名**（隐私红线与
   扫描门 `tests/test_fixture_hygiene.py` 的要求；`example.invalid` 是唯一允许的域）。

**两处口径修正（M1 实测，写在 `plan/HANDOFF-M2.md`）**：

* ``b-wrapped-header``（cpython #56141）：3.12.10 实测标准库**已修复**（解析正常、0 defect），
  故本 case 是**负例**（折叠头必须被正确读成 multipart）；它仍钉住"折行头曾破坏边界检测"这一历史形态。
* ``b-inner-dup``（cpython #69914）：3.12.10 实测标准库**报 1 条 ``StartBoundaryNotFoundDefect``
  且把内层 multipart 当非 multipart**（即"忽略内层 boundary"）——它不报告复用本身。
  原计划的"标准库未报缺陷"措辞据此修正为实测事实（`stdlib_compare` 字段留证）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable

from .. import constants as C
from ..exit_codes import decide_exit_code
from ..ledger import dumps, fingerprint
from ..model import Defect

CRLF = b"\r\n"
RFC_B_R6 = "RFC 2046 §5.1.1"
RFC_B_R7 = "RFC 2046 §5.1.1/§5.1.2"

#: 合成白名单（`data/README.md` §六）：唯一允许的域名后缀。
_ALLOWED_DOMAIN = "example.invalid"
#: 生成器自检时禁止出现的真实 TLD（防御性冗余；常驻门在 `tests/test_fixture_hygiene.py`）。
_FORBIDDEN_TLDS = (".com", ".net", ".org", ".io", ".dev")

#: 每 case 的证据锚点（"文件必须真含这些字节"），由 _case 在构造期登记、_self_check 复查。
_NEEDLES: dict[str, tuple[bytes, ...]] = {}


# ── 构造辅助 ──────────────────────────────────────────────────────────────


def _message(headers: list[bytes], body: bytes = b"", *, eol: bytes = CRLF) -> bytes:
    """拼一封最小邮件：头块 + 空行 + body。头条目内部可自带 eol（折叠行形态）。"""
    return eol.join(headers) + eol + eol + body


def _off(data: bytes, needle: bytes, start: int = 0) -> int:
    """锚点 → 绝对偏移；锚点必须存在（**构造期**断言，不是写数字）。"""
    idx = data.find(needle, start)
    if idx < 0:
        raise AssertionError(f"构造期锚点不存在: {needle!r}")
    return idx


def _line_start(data: bytes, needle: bytes, start: int = 0) -> int:
    """锚点所在**行首**的绝对偏移。"""
    idx = _off(data, needle, start)
    return data.rfind(b"\n", 0, idx) + 1


def _line_no(data: bytes, offset: int) -> int:
    """物理行号（从 1 起，按 ``\\n`` 计）——用于行宽类规则的 ``offset_kind="line"``。"""
    return data.count(b"\n", 0, offset) + 1


def _defect(
    rule_id: str,
    klass: str,
    severity: str,
    path: str,
    *,
    offset: int,
    rfc: str,
    detail: str,
    offset_kind: str = C.OFFSET_ABSOLUTE,
) -> dict[str, object]:
    """一条期望缺陷（手写常量）。``class`` 是序列化键（模型内部叫 ``klass``）。"""
    return {
        "rule_id": rule_id,
        "class": klass,
        "severity": severity,
        "path": path,
        "offset": offset,
        "offset_kind": offset_kind,
        "rfc": rfc,
        "detail": detail,
    }


def _assert_no_foreign_domains(blob: bytes, label: str) -> None:
    """构造期隐私红线：除 `example.invalid` 外不得出现真实 TLD 形态。

    （常驻门在 `tests/test_fixture_hygiene.py`；这里是生成期冗余 —— 写错的样本
    **根本不落地**，而不是等门事后报红。）
    """
    lowered = blob.lower()
    for tld in _FORBIDDEN_TLDS:
        if tld.encode() in lowered:
            raise AssertionError(f"{label}: 出现禁止的真实 TLD {tld!r}（隐私红线）")


def _case(
    name: str,
    *,
    expectation: str,
    source: str,
    infile: str,
    data: bytes,
    defects: list[dict[str, object]],
    needles: tuple[bytes, ...] = (),
    note: str = "",
    extra: dict[str, object] | None = None,
    stdlib: dict[str, object] | None = None,
) -> tuple[dict[str, bytes], dict[str, object]]:
    """把输入字节 + 手写缺陷集装配成 ``(files, expect)``。

    ``expectation`` 取 ``"positive"``（缺陷集非空）或 ``"negative"``（零缺陷基线）。
    ``needles`` 是"文件必须真含这些字节"的证据锚点 —— **在构造期断言**（存在性 +
    隐私红线两条），不是等 ``_self_check`` 事后补网。
    """
    if expectation not in {"positive", "negative"}:
        raise AssertionError(f"expectation 非法: {expectation!r}")
    if not source.strip():
        raise AssertionError(f"{name}: source 不得为空（每 case 必须标来源）")

    for needle in needles:
        if needle not in data:
            raise AssertionError(f"{name}: 证据锚点不在输入字节里: {needle!r}")
    _assert_no_foreign_domains(data, name)

    parsed: list[Defect] = []
    for row in defects:
        defect = Defect(
            rule_id=str(row["rule_id"]),
            klass=str(row["class"]),
            severity=str(row["severity"]),
            path=str(row["path"]),
            offset=int(row["offset"]),
            offset_kind=str(row["offset_kind"]),
            rfc=str(row["rfc"]),
            detail=str(row["detail"]),
        )
        defect.validate()  # 六元组不变量（模型是唯一判据）
        parsed.append(defect)
    ordered = sorted(parsed, key=lambda d: d.sort_key)  # §7.8 排序，落盘即有序

    expect: dict[str, object] = {
        "case": name,
        "expectation": expectation,
        "source": source,
        "input": {
            "file": infile,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        },
        "exit_code": decide_exit_code(ordered, fail_on=C.FAIL_ON_DEFAULT),
        "defect_count": len(ordered),
        "defects": [d.as_json() for d in ordered],
    }
    if extra is not None:
        expect["expect_extra"] = extra
    expect["fingerprint"] = fingerprint(ordered)
    expect["tree_digest"] = None  # M2 起由引擎产出后回填；数据级自检允许 null
    if stdlib is not None:
        expect["stdlib_compare"] = stdlib
    if note:
        expect["note"] = note
    _NEEDLES[name] = tuple(needles)
    return ({infile: data}, expect)


# ── README 渲染（每 case 三件之一）─────────────────────────────────────────


def _render_readme(name: str, expect: dict[str, object]) -> bytes:
    input_info = expect["input"]
    assert isinstance(input_info, dict)
    defects = expect["defects"]
    assert isinstance(defects, list)
    expectation = str(expect["expectation"])
    expectation_text = "正例（缺陷集非空）" if expectation == "positive" else "负例（零缺陷）"

    lines = [
        f"# golden case: {name}",
        "",
        f"- 期望：{expectation_text}；缺陷数 {len(defects)}；退出码 {expect['exit_code']}",
        f"- 来源：{expect['source']}",
        f"- 输入：`{input_info['file']}`（{input_info['bytes']} bytes；sha256 `{input_info['sha256']}`）",
        f"- 期望指纹：`{expect['fingerprint']}`",
        "- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）",
        "- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`",
        f"- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/{name}/{input_info['file']}`",
        "",
    ]

    note = expect.get("note")
    if note:
        lines += ["## 说明", "", str(note), ""]

    lines += ["## 期望缺陷", ""]
    if not defects:
        lines += ["无缺陷（负例）。", ""]
    else:
        lines += [
            "| rule_id | class | severity | path | offset | offset_kind | rfc | detail |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in defects:
            assert isinstance(row, dict)
            lines.append(
                "| {rule_id} | {class} | {severity} | {path} | {offset} | {offset_kind} | {rfc} | {detail} |".format(
                    **row
                )
            )
        lines.append("")

    extra = expect.get("expect_extra")
    if extra:
        lines += ["## 附加期望", "", _fenced_json(extra), ""]
    stdlib = expect.get("stdlib_compare")
    if stdlib:
        lines += ["## 标准库对照（实测留证）", "", _fenced_json(stdlib), ""]

    lines += [
        "## 数据级自检",
        "",
        "`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /",
        "`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。",
        "",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _fenced_json(payload: dict[str, object]) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return "```json\n" + text + "\n```"


# ── b 簇：树与边界（模块 M1 ↔ 里程碑 M2）───────────────────────────────────


def b_no_boundary() -> tuple[dict[str, bytes], dict[str, object]]:
    """`multipart/*` 缺 `boundary` 参数（MC-B01，blocker）。"""
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: multipart without boundary parameter",
            b"Message-ID: <fixed-0001@example.invalid>",
            b"MIME-Version: 1.0",
            b"Content-Type: multipart/mixed",
        ],
        b"plain text body, no delimiter anywhere\r\n",
    )
    line = _line_start(data, b"Content-Type: multipart/mixed")
    defects = [
        _defect(
            "MC-B01",
            "hard",
            "blocker",
            "0",
            offset=line,
            rfc=RFC_B_R6,
            detail="multipart/mixed 缺 boundary 参数（RFC 2046 §5.1.1 要求多部件实体必须有一个 boundary 参数）",
        )
    ]
    return _case(
        "b-no-boundary",
        expectation="positive",
        source="自造边界样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"Content-Type: multipart/mixed",),
        note="结构无法建立（无任何可用 delimiter）→ `blocker`，退出码 3。",
    )


def b_boundary_long() -> tuple[dict[str, bytes], dict[str, object]]:
    """`boundary` 超 70 字符（MC-B02，minor → 退出码 2）。"""
    boundary = b"A" * 71
    close = b"--" + boundary + b"--"
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: boundary longer than 70 characters",
            b"Message-ID: <fixed-0002@example.invalid>",
            b"MIME-Version: 1.0",
            b'Content-Type: multipart/mixed; boundary="' + boundary + b'"',
        ],
        b"--"
        + boundary
        + b"\r\nContent-Type: text/plain; charset=us-ascii\r\n\r\npart one\r\n"
        + close
        + b"\r\n",
    )
    line = _line_start(data, b"boundary=")
    defects = [
        _defect(
            "MC-B02",
            "hard",
            "minor",
            "0",
            offset=line,
            rfc=RFC_B_R6,
            detail="boundary 长度 71 > 70（不含前导两个连字符）",
        )
    ]
    return _case(
        "b-boundary-long",
        expectation="positive",
        source="自造边界样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(boundary, close),
        note="`minor` → 退出码 2（无 blocker/major）。",
    )


def b_delim_not_bol() -> tuple[dict[str, bytes], dict[str, object]]:
    """delimiter 未出现在行首（MC-B03 → 原句未录，只出 `note`）。"""
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: delimiter with leading whitespace",
            b"Message-ID: <fixed-0003@example.invalid>",
            b"MIME-Version: 1.0",
            b'Content-Type: multipart/mixed; boundary="S"',
        ],
        b"--S\r\n"
        b"Content-Type: text/plain; charset=us-ascii\r\n\r\n"
        b"first part body\r\n"
        b"  --S\r\n"
        b"still inside the first part\r\n"
        b"--S--\r\n",
    )
    line = _line_start(data, b"  --S")
    defects = [
        _defect(
            "MC-B03",
            "diff",
            "note",
            "0",
            offset=line,
            rfc=RFC_B_R6,
            detail="疑似 delimiter `--S` 未出现在行首（前导空白）——R7 的 delimiter 形态子项原句未留档，只登记",
        )
    ]
    return _case(
        "b-delim-not-bol",
        expectation="positive",
        source="自造边界样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"  --S",),
        note="该行按字节是首部件正文内容（前导空白使其不构成 delimiter）；登记用于解释下游切分差异。",
    )


def b_close_malformed() -> tuple[dict[str, bytes], dict[str, object]]:
    """close-delimiter 形态错误（MC-B04 → 只出 `note`）。"""
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: close delimiter with trailing content",
            b"Message-ID: <fixed-0004@example.invalid>",
            b"MIME-Version: 1.0",
            b'Content-Type: multipart/mixed; boundary="C"',
        ],
        b"--C\r\n"
        b"Content-Type: text/plain; charset=us-ascii\r\n\r\n"
        b"part one\r\n"
        b"--C--junk\r\n"
        b"still part one (the --C--junk line is not a valid close)\r\n"
        b"--C--\r\n",
    )
    line = _line_start(data, b"--C--junk")
    defects = [
        _defect(
            "MC-B04",
            "diff",
            "note",
            "0",
            offset=line,
            rfc=RFC_B_R6,
            detail="close-delimiter 形态错误：`--C--` 之后还有 `junk`（只允许可忽略的空白与行尾）",
        )
    ]
    return _case(
        "b-close-malformed",
        expectation="positive",
        source="自造边界样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"--C--junk",),
        note="文件里同时存在一个**合法**的 `--C--` 收尾 → 不记 MC-B05（缺 final boundary）。",
    )


def b_inner_dup() -> tuple[dict[str, bytes], dict[str, object]]:
    """嵌套复用同一 boundary（MC-B06，hard/major；复现 cpython #69914）。"""
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: inner multipart duplicates the outer boundary",
            b"Message-ID: <fixed-0005@example.invalid>",
            b"MIME-Version: 1.0",
            b'Content-Type: multipart/mixed; boundary="X"',
        ],
        b'--X\r\nContent-Type: multipart/alternative; boundary="X"\r\n\r\n'
        b"--X\r\nContent-Type: text/plain; charset=us-ascii\r\n\r\ninner body\r\n\r\n--X--\r\n",
    )
    inner = _line_start(data, b'Content-Type: multipart/alternative; boundary="X"')
    defects = [
        _defect(
            "MC-B06",
            "hard",
            "major",
            "0.1",
            offset=inner,
            rfc=RFC_B_R7,
            detail="内层 multipart/alternative 复用了外层 boundary \"X\"（RFC 2046 §5.1.1/§5.1.2 要求每层用不同 boundary）",
        )
    ]
    return _case(
        "b-inner-dup",
        expectation="positive",
        source="cpython #69914（open）—— issue 原话：email parser ignores inner multipart boundary when outer message duplicates it",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b'boundary="X"',),
        extra={"tree_alternatives": 2, "divergence_path": "0.1"},
        stdlib={
            "defects": 1,
            "types": ["StartBoundaryNotFoundDefect"],
            "note": (
                "3.12.10 实测：标准库把内层 multipart/alternative 当作**非 multipart**"
                "（is_multipart=False）并记 StartBoundaryNotFoundDefect —— 即 #69914 的"
                "「忽略内层 boundary」；它**不报告 boundary 复用本身**，也不给两棵候选树。"
            ),
        },
        note=(
            "字节层无法唯一确定 close-delimiter 归属（外层先闭合 / 内层先闭合都成立）→ "
            "本工具必须输出**两棵候选树**（`tree_alternatives` 长度 2 + `divergence` 指向 "
            "`0.1`），不替用户选一个（`plan/00` D9）。"
        ),
    )


def b_no_final() -> tuple[dict[str, bytes], dict[str, object]]:
    """缺 final boundary（MC-B05 → `diff/note`，不影响退出码）。"""
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: multipart missing its final boundary",
            b"Message-ID: <fixed-0006@example.invalid>",
            b"MIME-Version: 1.0",
            b'Content-Type: multipart/mixed; boundary="F"',
        ],
        b"--F\r\nContent-Type: text/plain; charset=us-ascii\r\n\r\ntruncated entity, no --F-- line\r\n",
    )
    end = len(data)
    defects = [
        _defect(
            "MC-B05",
            "diff",
            "note",
            "0",
            offset=end,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail=f"缺 final boundary：树在第 {end} 字节被迫闭合（RFC 只描述 truncated entity，无恢复规程）",
        )
    ]
    return _case(
        "b-no-final",
        expectation="positive",
        source="自造边界样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"--F",),
        note="`diff/note` 不影响退出码（退出码 0）——证明没把它硬判成错误（难度格：§四.1）。",
    )


def b_preamble_epilogue() -> tuple[dict[str, bytes], dict[str, object]]:
    """preamble / epilogue 存在（MC-B07/B08 → 只登记）。"""
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: multipart with preamble and epilogue",
            b"Message-ID: <fixed-0007@example.invalid>",
            b"MIME-Version: 1.0",
            b'Content-Type: multipart/mixed; boundary="P"',
        ],
        b"This is the preamble (ignored per RFC 2046).\r\n"
        b"--P\r\nContent-Type: text/plain; charset=us-ascii\r\n\r\npart one\r\n"
        b"--P--\r\nThis is the epilogue (ignored per RFC 2046).\r\n",
    )
    preamble = _line_start(data, b"This is the preamble")
    epilogue = _line_start(data, b"This is the epilogue")
    defects = [
        _defect(
            "MC-B07",
            "diff",
            "note",
            "0",
            offset=preamble,
            rfc=RFC_B_R6,
            detail="存在 preamble 字节区间（RFC 2046 §5.1.1 要求忽略；存在本身不是违规）",
        ),
        _defect(
            "MC-B08",
            "diff",
            "note",
            "0",
            offset=epilogue,
            rfc=RFC_B_R6,
            detail="存在 epilogue 字节区间（RFC 2046 §5.1.1 要求忽略；存在本身不是违规）",
        ),
    ]
    return _case(
        "b-preamble-epilogue",
        expectation="positive",
        source="自造边界样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"This is the preamble", b"This is the epilogue"),
        note="两条都是 `note`（登记字节区间，用于解释「多出来的内容去哪了」）；preamble/epilogue **不计入** `body_sha256`。",
    )


def b_empty_multipart() -> tuple[dict[str, bytes], dict[str, object]]:
    """multipart 无任何 body part（MC-B10 → 无明文条款，只出 `note`）。"""
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: multipart with no body parts",
            b"Message-ID: <fixed-0008@example.invalid>",
            b"MIME-Version: 1.0",
            b'Content-Type: multipart/mixed; boundary="E"',
        ],
        b"--E--\r\n",
    )
    line = _line_start(data, b"--E--")
    defects = [
        _defect(
            "MC-B10",
            "diff",
            "note",
            "0",
            offset=line,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="multipart/mixed 无任何 body part（RFC 无明文条款；依据 stdlib MultipartInvariantViolationDefect 的实现事实，只登记）",
        )
    ]
    return _case(
        "b-empty-multipart",
        expectation="positive",
        source="自造边界样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"--E--",),
        note="「multipart 至少有子部件」是不变量但**无明文原句** → 补齐摘录前只能出 `note`（原句门禁，§7.1）。",
    )


def b_deep_nest() -> tuple[dict[str, bytes], dict[str, object]]:
    """嵌套深度超 `--max-depth` 32（MC-B09，gray/note；不改退出码）。"""
    depth = 35
    lines = [
        b"From: alice@example.invalid",
        b"To: bob@example.invalid",
        b"Subject: deeply nested multipart",
        b"Message-ID: <fixed-0009@example.invalid>",
        b"MIME-Version: 1.0",
        b'Content-Type: multipart/mixed; boundary="d01"',
    ]
    data = CRLF.join(lines) + CRLF + CRLF
    for level in range(1, depth + 1):
        data += b"--" + f"d{level:02d}".encode() + CRLF
        if level < depth:
            data += b'Content-Type: multipart/mixed; boundary="d%02d"' % (level + 1) + CRLF + CRLF
        else:
            data += b"Content-Type: text/plain; charset=us-ascii\r\n\r\n"
            data += b"deep leaf\r\n"
    for level in reversed(range(1, depth + 1)):
        data += b"--" + f"d{level:02d}".encode() + b"--" + CRLF

    offending = _line_start(data, b'boundary="d33"')
    path = "0" + ".1" * 32  # d33 所在节点：根 0 往下 32 层
    defects = [
        _defect(
            "MC-B09",
            "gray",
            "note",
            path,
            offset=offending,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail=f"嵌套深度 33 > --max-depth {C.MAX_DEPTH_DEFAULT}（RFC 未规定深度上限；策略项，默认不影响退出码）",
        )
    ]
    return _case(
        "b-deep-nest",
        expectation="positive",
        source="自造边界样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b'boundary="d33"', b"deep leaf"),
        extra={
            "max_depth": C.MAX_DEPTH_DEFAULT,
            "depth_convention": "节点深度 = 路径段数（根部件 `0` 为第 1 层；`0.1` 为第 2 层）",
            "first_over_depth_path": path,
            "truncated": True,
        },
        note=(
            "`--strict-depth` 才把超深度计入退出码（届时 severity 提为 minor）；默认下本文件退出码 0。"
            "引擎超限**停止下钻**并登记 `truncated`，不是崩溃、不是静默截断。"
        ),
    )


def b_clean_nested() -> tuple[dict[str, bytes], dict[str, object]]:
    """负例：完好的 `multipart/mixed` + `multipart/alternative` 嵌套。"""
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: well-formed nested multipart",
            b"Message-ID: <fixed-0010@example.invalid>",
            b"MIME-Version: 1.0",
            b'Content-Type: multipart/mixed; boundary="outer"',
        ],
        b"--outer\r\n"
        b'Content-Type: multipart/alternative; boundary="inner"\r\n\r\n'
        b"--inner\r\nContent-Type: text/plain; charset=us-ascii\r\n\r\nplain version\r\n"
        b"--inner\r\nContent-Type: text/html; charset=us-ascii\r\n\r\n<p>html version</p>\r\n"
        b"--inner--\r\n"
        b"--outer\r\n"
        b"Content-Type: application/pdf; name=\"a.pdf\"\r\n"
        b"Content-Transfer-Encoding: base64\r\n"
        b"Content-Disposition: attachment; filename=\"a.pdf\"\r\n\r\n"
        b"JVBERi0xLjQKJcOkw7zDtsOfCg==\r\n"
        b"--outer--\r\n",
    )
    return _case(
        "b-clean-nested",
        expectation="negative",
        source="自造边界样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=[],
        needles=(b'boundary="outer"', b'boundary="inner"'),
        note="零缺陷基线：合法嵌套 + 合法 base64 附件；任何 B 簇误报都会打挂本 case。",
    )


def b_wrapped_header() -> tuple[dict[str, bytes], dict[str, object]]:
    """负例：折行头里的 boundary 参数（历史形态：cpython #56141）。"""
    data = _message(
        [
            b"From: alice@example.invalid",
            b"To: bob@example.invalid",
            b"Subject: boundary parameter on a folded header line",
            b"Message-ID: <fixed-0011@example.invalid>",
            b"MIME-Version: 1.0",
            b"Content-Type: multipart/mixed;\r\n boundary=\"wrapped\"",
        ],
        b"--wrapped\r\nContent-Type: text/plain; charset=us-ascii\r\n\r\none\r\n"
        b"--wrapped\r\nContent-Type: text/html; charset=us-ascii\r\n\r\n<p>two</p>\r\n"
        b"--wrapped--\r\n",
    )
    return _case(
        "b-wrapped-header",
        expectation="negative",
        source="cpython #56141（closed）—— issue 原话：Email multipart boundary detection fails on a wrapped header",
        infile="msg.eml",
        data=data,
        defects=[],
        needles=(b'boundary="wrapped"', b"--wrapped--"),
        stdlib={
            "defects": 0,
            "types": [],
            "note": "3.12.10 实测标准库已修复（解析正常、0 defect）——本 case 现钉住「折叠头必须被正确读成 multipart」这一回归面。",
        },
        note=(
            "头折叠（RFC 5322 §2.2.3 的 FWS）是**合法**形态：boundary 参数被折到续行上，"
            "本工具必须照常切出两棵子部件、零缺陷。历史 bug（#56141）正是折行头破坏边界检测。"
        ),
    )


# ── h 簇：头编码（RFC 2047 / 2231，模块 M2 ↔ 里程碑 M3）────────────────────

#: 门禁降级的 rfc 文案（原句未录的子项：只登记，不判合规 —— `data/README` §7.1）。
RFC_H_DEGRADED_41 = "RFC 2047 §4.1（R4 该子项未录原句 → 门禁降级，只登记）"
RFC_H_DEGRADED_42 = "RFC 2047 §4.2（R4 该子项未录原句 → 门禁降级，只登记）"
RFC_H_DEGRADED_R10 = "RFC 2231 §3/§4/§4.1（R10 整行未录原句 → 门禁降级，只登记）"

_H_FROM = b"From: alice@example.invalid"
_H_TO = b"To: bob@example.invalid"
_H_CT_TEXT = b"Content-Type: text/plain; charset=us-ascii"
_H_MIME = b"MIME-Version: 1.0"


def _plain_headers(subject: bytes, message_id: int) -> list[bytes]:
    """最小干净头块（From/To/Subject/Message-ID/MIME-Version/Content-Type）。"""
    return [
        _H_FROM,
        _H_TO,
        b"Subject: " + subject,
        f"Message-ID: <fixed-{message_id:04d}@example.invalid>".encode(),
        _H_MIME,
        _H_CT_TEXT,
    ]


def _mixed_with_attachment(message_id: int, subject: bytes, part2_headers: list[bytes], part2_body: bytes) -> bytes:
    """`multipart/mixed`（0.1 正文 + 0.2 附件）—— h/t 簇复用同一骨架，避免无关差异。"""
    body = (
        b"--mix1\r\n"
        + _H_CT_TEXT
        + b"\r\n\r\n"
        + b"body text of part one\r\n"
        + b"--mix1\r\n"
        + CRLF.join(part2_headers)
        + b"\r\n\r\n"
        + part2_body
        + b"--mix1--\r\n"
    )
    headers = [
        _H_FROM,
        _H_TO,
        b"Subject: " + subject,
        f"Message-ID: <fixed-{message_id:04d}@example.invalid>".encode(),
        _H_MIME,
        b'Content-Type: multipart/mixed; boundary="mix1"',
    ]
    return _message(headers, body)


def h_ew_long() -> tuple[dict[str, bytes], dict[str, object]]:
    """encoded-word > 75 字符（MC-H01，hard/minor → 退出码 2）。"""
    encoded = b"=?UTF-8?B?" + b"QUJD" * 20 + b"?="  # 10 + 80 + 2 = 92 字节 → 超 75
    data = _message(_plain_headers(encoded, 20), b"body\r\n")
    at = _off(data, b"=?UTF-8?B?")
    line = _line_no(data, at)
    defects = [
        _defect(
            "MC-H01",
            "hard",
            "minor",
            "0",
            offset=at,
            rfc="RFC 2047 §2",
            detail=f"encoded-word 长度 {len(encoded)} > 75（按编码后 ASCII 字节计）",
        ),
        _defect(
            "MC-H02",
            "hard",
            "minor",
            "0",
            offset=line,
            rfc="RFC 2047 §2",
            detail=f"含 encoded-word 的头行 {9 + len(encoded)} > 76 字符（H01 的必然连带：encoded-word 自身超长时其所在行必超行宽）",
            offset_kind=C.OFFSET_LINE,
        ),
    ]
    return _case(
        "h-ew-long",
        expectation="positive",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(encoded,),
        note=(
            "R1 全录原句；长度按编码后 ASCII 字节计（本题保守口径）。"
            "**H01 与 H02 各自成账**：encoded-word 超 75 时其所在行必超 76 —— 不算双记（§7.5 的互斥只约束 H12/H03）。"
        ),
    )


def h_ew_line_long() -> tuple[dict[str, bytes], dict[str, object]]:
    """含 encoded-word 的头行 > 76 字符（MC-H02，hard/minor）。"""
    encoded = b"=?UTF-8?B?" + b"QUJD" * 6 + b"?="  # 总长 27 < 75，不触发 MC-H01
    padding = b"x" * 60
    data = _message(_plain_headers(encoded + b" " + padding, 21), b"body\r\n")
    line_start = _line_start(data, b"=?UTF-8?B?")
    header_line = data[line_start : data.find(b"\n", line_start)].rstrip(b"\r")
    defects = [
        _defect(
            "MC-H02",
            "hard",
            "minor",
            "0",
            offset=_line_no(data, line_start),
            rfc="RFC 2047 §2",
            detail=f"含 encoded-word 的头行 {len(header_line)} > 76 字符（encoded-word 本身 {len(encoded)} ≤ 75）",
            offset_kind=C.OFFSET_LINE,
        )
    ]
    return _case(
        "h-ew-line-long",
        expectation="positive",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(encoded, padding),
        note="R2 全录原句；本 case 只超行宽（不超 encoded-word 长度），与 MC-H01 正交。",
    )


def h_ew_space() -> tuple[dict[str, bytes], dict[str, object]]:
    """encoded-word 内部出现空白（MC-H03，hard/minor）。"""
    encoded = b"=?UTF-8?Q?foo bar?="
    data = _message(_plain_headers(encoded, 22), b"body\r\n")
    at = _off(data, b"=?UTF-8?Q?")
    defects = [
        _defect(
            "MC-H03",
            "hard",
            "minor",
            "0",
            offset=at,
            rfc="RFC 2047 §2",
            detail="encoded-word 内部出现空白（形态定义排除 LWSP；本样本无折行，不与 MC-H12 互斥）",
        )
    ]
    return _case(
        "h-ew-space",
        expectation="positive",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(encoded,),
        note="与 MC-H12 互斥（§7.5 第 2 条）：无折行时只报本规则。",
    )


def h_q_invalid() -> tuple[dict[str, bytes], dict[str, object]]:
    """Q 编码语法非法（MC-H04 → 原句未录，只出 `note`）。"""
    encoded = b"=?UTF-8?Q?=zz_ok?="
    data = _message(_plain_headers(encoded, 23), b"body\r\n")
    at = _off(data, b"=?UTF-8?Q?")
    defects = [
        _defect(
            "MC-H04",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=RFC_H_DEGRADED_41,
            detail="Q 编码里 `=zz` 不是合法的 =HH 转义",
        )
    ]
    return _case(
        "h-q-invalid",
        expectation="positive",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(encoded,),
        note="R4 §4.1 子项原句未录 → 只登记（§7.1 门禁降级）。",
    )


def h_b_length() -> tuple[dict[str, bytes], dict[str, object]]:
    """B 编码长度非 4 的倍数（MC-H05 → 原句未录，只出 `note`）。"""
    encoded = b"=?UTF-8?B?QUJDREVGR0g?="  # 11 个 base64 字符
    data = _message(_plain_headers(encoded, 24), b"body\r\n")
    at = _off(data, b"=?UTF-8?B?")
    defects = [
        _defect(
            "MC-H05",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=RFC_H_DEGRADED_42,
            detail="B 编码 base64 长度 11 不是 4 的倍数",
        )
    ]
    return _case(
        "h-b-length",
        expectation="positive",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(encoded,),
        note="R4 §4.2 子项原句未录 → 只登记（§7.1）。",
    )


def h_2231_seq() -> tuple[dict[str, bytes], dict[str, object]]:
    """RFC 2231 续行缺 `*0` 序号（MC-H09；复现 SO 44154520）。"""
    data = _mixed_with_attachment(
        25,
        b"attachment filename arrives in gibberish",
        [
            b"Content-Type: application/pdf;",
            b' name="a.pdf"',
            b'Content-Disposition: attachment; filename*="UTF-8\'\'%D7%A2.pdf"',
            b"Content-Transfer-Encoding: base64",
        ],
        b"JVBERi0xLjQK\r\n",
    )
    at = _off(data, b"filename*=")
    defects = [
        _defect(
            "MC-H09",
            "diff",
            "note",
            "0.2",
            offset=at,
            rfc=RFC_H_DEGRADED_R10,
            detail="RFC 2231 参数缺 `*0` 序号：`filename*=` 应写成 `filename*0*=`（SO 44154520 的形状；修正提示是文本，不自动改文件）",
        )
    ]
    return _case(
        "h-2231-seq",
        expectation="positive",
        source="SO 44154520——原话：attachment file names arrive are in gibberish；实样含 name*=\"UTF-8''%D7%A2...（缺 *0 序号）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b'name="a.pdf"', b"filename*="),
        note=(
            "验收不依赖 severity：只断言「报了 MC-H09 且路径 `0.2` 精确」。"
            "R10 整行原句未录 → 补齐摘录前只能出 `note`。"
            "SO 实样里 `name*=\"UTF-8''…\"`（带引号的扩展值）与 `filename*=UTF-8''…` 都缺 `*0`；"
            "本样本只保留 `filename*` 一处（同一 case 出两条账会稀释定位精度），另一处形状在本说明里记述。"
        ),
    )


def h_2231_quote() -> tuple[dict[str, bytes], dict[str, object]]:
    """`charset'language'value` 单引号不全（MC-H10 → 原句未录，只出 `note`）。"""
    data = _mixed_with_attachment(
        26,
        b"2231 encoded parameter without complete quotes",
        [
            b"Content-Type: application/pdf",
            b"Content-Disposition: attachment; filename*0*=UTF-8'sample.pdf",
        ],
        b"JVBERi0xLjQK\r\n",
    )
    at = _off(data, b"filename*0*=")
    defects = [
        _defect(
            "MC-H10",
            "diff",
            "note",
            "0.2",
            offset=at,
            rfc=RFC_H_DEGRADED_R10,
            detail="`charset'language'value` 的单引号不完整（`UTF-8'sample.pdf` 只有一个 `'`；应为 `UTF-8''sample.pdf`）",
        )
    ]
    return _case(
        "h-2231-quote",
        expectation="positive",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"filename*0*=",),
        note="R10 未录 → 只登记。判定顺序按 §7.5 第 3 条（合并续行 → 三段解析 → %HH → 2047）。",
    )


def h_2231_pct() -> tuple[dict[str, bytes], dict[str, object]]:
    """`%HH` 转义非法（MC-H11 → 原句未录，只出 `note`）。"""
    data = _mixed_with_attachment(
        27,
        b"2231 percent escape malformed",
        [
            b"Content-Type: application/pdf",
            b"Content-Disposition: attachment; filename*0*=UTF-8''%ZZ%41.pdf",
        ],
        b"JVBERi0xLjQK\r\n",
    )
    at = _off(data, b"%ZZ")
    defects = [
        _defect(
            "MC-H11",
            "diff",
            "note",
            "0.2",
            offset=at,
            rfc=RFC_H_DEGRADED_R10,
            detail="`%ZZ` 不是合法的 %HH 转义（H 必须是两位十六进制）",
        )
    ]
    return _case(
        "h-2231-pct",
        expectation="positive",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"%ZZ",),
        note="R10 未录 → 只登记（§7.1）。",
    )


def h_8bit_header() -> tuple[dict[str, bytes], dict[str, object]]:
    """头值含未编码非 ASCII 字节（MC-H08，diff/note）。"""
    raw_bytes = "na\u00efve".encode("utf-8")
    data = _message(_plain_headers(raw_bytes, 28), b"body\r\n")
    at = _off(data, b"\xc3\xaf")  # 第一个非 ASCII 八位组（ï 的 UTF-8 首字节）
    defects = [
        _defect(
            "MC-H08",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="Subject 头值含未编码的非 ASCII 字节（RFC 2047 是编码机制，不是禁令；现实实现常直传 8bit）",
        )
    ]
    return _case(
        "h-8bit-header",
        expectation="positive",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(raw_bytes,),
        note="`diff`：不硬判，只登记偏移与所在头名。",
    )


def h_ew_newline() -> tuple[dict[str, bytes], dict[str, object]]:
    """encoded-word 内部含折行（MC-H12；复现 SO 52442469；与 MC-H03 互斥）。"""
    data = _message(
        [
            _H_FROM,
            _H_TO,
            b"Subject: =?UTF-8?Q?=C3=A5\r\n =C3=A4?=",
            b"Message-ID: <fixed-0029@example.invalid>",
            _H_MIME,
            _H_CT_TEXT,
        ],
        b"body\r\n",
    )
    line = _line_no(data, _line_start(data, b"=?UTF-8?Q?"))
    at = _off(data, b"=?UTF-8?Q?")
    defects = [
        _defect(
            "MC-H12",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="encoded-word 跨折行：`=?UTF-8?Q?=C3=A5` 与 `=C3=A4?=` 被 FWS 折在一个 encoded-word 内（先折叠还是先解码，RFC 未定）",
        )
    ]
    return _case(
        "h-ew-newline",
        expectation="positive",
        source="SO 52442469——实样 `=?UTF-8?Q?=C3=A5 =C3=A4?=`；原话：Are newlines in MIME headers using encoded-words legal?",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"=?UTF-8?Q?=C3=A5", b"=C3=A4?="),
        extra={"related": ["MC-H03"], "no_double_record": True},
        note="命中 MC-H12 后**不得**同时报 MC-H03（§7.5 第 2 条）；`related` 记录被压掉的规则号。",
    )


def h_line_998() -> tuple[dict[str, bytes], dict[str, object]]:
    """头行 > 998 octets（MC-H07，hard/major → 退出码 3）。"""
    long_value = b"x" * 1000
    data = _message(_plain_headers(long_value, 30), b"body\r\n")
    line_start = _line_start(data, long_value)
    header_line = data[line_start : data.find(b"\n", line_start)].rstrip(b"\r")
    defects = [
        _defect(
            "MC-H07",
            "hard",
            "major",
            "0",
            offset=_line_no(data, line_start),
            rfc="RFC 5322 §2.1.1",
            detail=f"头行 {len(header_line)} > 998 octets（不含 CRLF）",
            offset_kind=C.OFFSET_LINE,
        )
    ]
    return _case(
        "h-line-998",
        expectation="positive",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(long_value,),
        note="R5 全录；头行 > 998 先于 encoded-word 检查（§7.5 第 1 条）。",
    )


def h_clean_folded() -> tuple[dict[str, bytes], dict[str, object]]:
    """负例：合法折叠的多 encoded-word（每个 ≤75、行 ≤76）。"""
    data = _message(
        [
            _H_FROM,
            _H_TO,
            b"Subject: =?UTF-8?Q?=E4=BD=A0=E5=A5=BD?=\r\n =?UTF-8?B?5LiA5Liq56S65L6L?=",
            b"Message-ID: <fixed-0031@example.invalid>",
            _H_MIME,
            _H_CT_TEXT,
        ],
        b"body\r\n",
    )
    return _case(
        "h-clean-folded",
        expectation="negative",
        source="自造头编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=[],
        needles=(b"=?UTF-8?Q?=E4=BD=A0=E5=A5=BD?=", b"=?UTF-8?B?5LiA5Liq56S65L6L?="),
        note="零缺陷基线：两个 encoded-word 各自 ≤75、行 ≤76、之间有 FWS，且**每个 encoded-word 自身完整**（不跨行）→ 不构成 MC-H12。",
    )


# ── t 簇：传输编码（CTE，模块 M3 ↔ 里程碑 M4）─────────────────────────────

_T_CT_B64 = b"Content-Transfer-Encoding: base64"
_T_CT_QP = b"Content-Transfer-Encoding: quoted-printable"
_T_CT_7BIT = b"Content-Transfer-Encoding: 7bit"
#: R9 的「填充 / 长度」子项本轮未录原句 → 只登记（`data/README` §7.1 未录清单）。
RFC_T_DEGRADED_R9 = "RFC 2045 §6.8（R9 的填充/长度子项未录原句 → 门禁降级，只登记）"
#: R11 整行未录 → 只登记。
RFC_T_DEGRADED_R11 = "RFC 2045 §2.7/§2.8/§6.1（R11 整行未录原句 → 门禁降级，只登记）"


def _leaf(subject: bytes, msgid: int, cte: bytes | None = None) -> list[bytes]:
    """单部件邮件的头块（可选 CTE 行）—— t 簇用，避免重复骨架。"""
    headers = _plain_headers(subject, msgid)
    return headers + [cte] if cte is not None else headers


def t_cte_mismatch() -> tuple[dict[str, bytes], dict[str, object]]:
    """声明 CTE 与实际形态不符（MC-T01，diff/note；**永不出 hard**）。"""
    body = b"this body is plainly readable text, not base64\r\n"
    data = _message(_leaf(b"declared base64 but the body is plain text", 40, _T_CT_B64), body)
    at = _off(data, body)
    defects = [
        _defect(
            "MC-T01",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="声明 base64、实际形态为明文（语义层判定，不是条款判定；不硬判 → 退出码不受影响）",
        )
    ]
    return _case(
        "t-cte-mismatch",
        expectation="positive",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(body,),
        extra={
            "suppressed": ["MC-T02", "MC-T03", "MC-T04"],
            "suppression_note": "observed 完全不是 base64 形态时不逐条登记字母表外字符/长度子项（否则同一段字节会出几十条 note 账）—— M4 以此为准",
        },
        note="D2 / §四.3：MC-T01 永远 `diff`，`rfc` 写 none-by-design —— 本题最需要克制的一格；退出码不变（note）。",
    )


def t_b64_pad() -> tuple[dict[str, bytes], dict[str, object]]:
    """base64 填充非法（MC-T02 → 原句未录，只出 `note`）。"""
    body = b"QQ==QQ==\r\n"
    data = _message(_leaf(b"base64 with misplaced padding", 41, _T_CT_B64), body)
    at = _off(data, body) + 2  # 第一处 `=`：填充出现之后仍有数据字符
    defects = [
        _defect(
            "MC-T02",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=RFC_T_DEGRADED_R9,
            detail="base64 填充非法：`=` 之后仍有数据字符（填充只允许出现在末尾，且最多两个）",
        )
    ]
    return _case(
        "t-b64-pad",
        expectation="positive",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"QQ==QQ==",),
        note="R9 的填充子项原句未录 → 只登记（§7.1 门禁降级）。",
    )


def t_b64_len() -> tuple[dict[str, bytes], dict[str, object]]:
    """base64 长度非 4 的倍数（MC-T03；复现 SO 6029218）。"""
    body = b"QUJDRQ\r\n"
    data = _message(_leaf(b"base64 attachment with truncated length", 42, _T_CT_B64), body)
    at = _off(data, body)
    defects = [
        _defect(
            "MC-T03",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=RFC_T_DEGRADED_R9,
            detail="base64 数据字符数 6 不是 4 的倍数（末组被截断，解码会丢字节）",
        )
    ]
    return _case(
        "t-b64-len",
        expectation="positive",
        source="SO 6029218——原话：sending zip as base64-encoded attachment corrupts archive",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"QUJDRQ",),
        note=(
            "R9 的长度子项原句未录 → 现在只出 `note`；**补齐 §6.8 原句后提为 hard/major**"
            "（`plan/01` §M3 验收）——届时须同轮改 golden 与 catalog，不得只改一处。"
            "验收不依赖 severity：只断言「报了 MC-T03 且偏移精确」。"
        ),
    )


def t_b64_foreign() -> tuple[dict[str, bytes], dict[str, object]]:
    """base64 出现字母表外字符（MC-T04，hard/note —— 出现本身不是违规）。"""
    body = b"QUJD*QUJD\r\n"
    data = _message(_leaf(b"base64 with characters outside the alphabet", 43, _T_CT_B64), body)
    at = _off(data, b"*")
    defects = [
        _defect(
            "MC-T04",
            "hard",
            "note",
            "0",
            offset=at,
            rfc="RFC 2045 §6.8",
            detail="base64 出现字母表外字符 `*`（RFC 2045 §6.8 原句要求忽略它 → 出现本身不是违规，只登记并计入 foreign_chars）",
        )
    ]
    return _case(
        "t-b64-foreign",
        expectation="positive",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"QUJD*QUJD",),
        note="§7.1：本条子项原句**全录** → 证据强度是 hard；但现象不构成违规 → severity 只能是 `note`。",
    )


def t_qp_long() -> tuple[dict[str, bytes], dict[str, object]]:
    """QP 编码行 > 76（MC-T05，hard/minor → 退出码 2）。"""
    line = b"a" * 80
    data = _message(_leaf(b"quoted-printable line longer than 76", 44, _T_CT_QP), line + b"\r\n")
    at = _off(data, line)
    defects = [
        _defect(
            "MC-T05",
            "hard",
            "minor",
            "0",
            offset=at,
            rfc="RFC 2045 §6.7",
            detail=f"QP 编码行 {len(line)} > 76 octets（不含 CRLF）",
        )
    ]
    return _case(
        "t-qp-long",
        expectation="positive",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(line,),
        note="R8 全录原句：encoded lines be no more than 76 characters long。行宽按 octets、不含 CRLF。",
    )


def t_qp_soft() -> tuple[dict[str, bytes], dict[str, object]]:
    """QP 软换行无法接续（MC-T06，hard/minor）。"""
    body = b"the soft break at the very end cannot continue=\r\n"
    data = _message(_leaf(b"quoted-printable soft break at end of part", 45, _T_CT_QP), body)
    at = _off(data, b"=\r\n")
    defects = [
        _defect(
            "MC-T06",
            "hard",
            "minor",
            "0",
            offset=at,
            rfc="RFC 2045 §6.7",
            detail="行末 `=` 之后已无下一行（部件在此结束）：软换行无法接续，`=` 成了悬空转义",
        )
    ]
    return _case(
        "t-qp-soft",
        expectation="positive",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"cannot continue=\r\n",),
        note=(
            "R8 全录原句：An equal sign as the last character on an encoded line indicates such a "
            "non-significant (soft) line break。判定按字节：行末 `=` 紧邻线性空白的情形按 §M3 纪律"
            "视为 `diff` 而非 `hard`，本 case 只钉「软换行之后无内容」这一硬形态。"
        ),
    )


def t_qp_artifact() -> tuple[dict[str, bytes], dict[str, object]]:
    """QP 非法转义（MC-T07，hard/major；复现 SO 79133579）。"""
    body = (
        b"We request all our =ustomers to read the notice, "
        b"then =o:p> shows up in the markup, and please make =ure it works.\r\n"
    )
    data = _message(_leaf(b"quoted-printable artifacts swallow characters", 46, _T_CT_QP), body)
    defects = [
        _defect(
            "MC-T07",
            "hard",
            "major",
            "0",
            offset=_off(data, b"=ustomers"),
            rfc="RFC 2045 §6.7",
            detail="QP 非法转义 `=us`：`=` 后不是两位十六进制（原帖实样 =ustomers）",
        ),
        _defect(
            "MC-T07",
            "hard",
            "major",
            "0",
            offset=_off(data, b"=o:p>"),
            rfc="RFC 2045 §6.7",
            detail="QP 非法转义 `=o:`：`=` 后不是两位十六进制（原帖实样 =o:p>）",
        ),
        _defect(
            "MC-T07",
            "hard",
            "major",
            "0",
            offset=_off(data, b"=ure"),
            rfc="RFC 2045 §6.7",
            detail="QP 非法转义 `=ur`：`=` 后不是两位十六进制（原帖实样 =ure）",
        ),
    ]
    return _case(
        "t-qp-artifact",
        expectation="positive",
        source="SO 79133579——实样 We request all our =ustomers … =o:p> … please make =ure",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"=ustomers", b"=o:p>", b"=ure"),
        note=(
            "**每处非法转义各记一条**（精确到字节偏移），不是合并成一条 —— M4 落地时引擎与 golden 取同一口径。"
            "条款论证：R8 把行末 `=` 的唯一合法语义限定为软换行，故 `=` 后非 `HH` 即违反 §6.7；"
            "推导链写进 `docs/defect-catalog.md`（`plan/06` Q1 留了「降为 diff」的开关）。"
        ),
    )


def t_qp_double() -> tuple[dict[str, bytes], dict[str, object]]:
    """QP 二次编码残留（MC-T11，diff/note）。"""
    body = b"double-encoded residue: =3D3D stays visible after one pass\r\n"
    data = _message(_leaf(b"quoted-printable encoded twice", 47, _T_CT_QP), body)
    at = _off(data, b"=3D3D")
    defects = [
        _defect(
            "MC-T11",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="QP 解码一遍之后正文里仍出现字面 `=3D`：上游疑似被编码了两次（只登记，不猜责任方）",
        )
    ]
    return _case(
        "t-qp-double",
        expectation="positive",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"=3D3D",),
        note="`=3D` 在**编码态**正文里合法；本规则只在**解码后**仍见字面 `=3D` 时触发。",
    )


def t_cte_unknown() -> tuple[dict[str, bytes], dict[str, object]]:
    """未知 CTE 取值（MC-T08，diff/note）。"""
    cte = b"Content-Transfer-Encoding: x-mystery-enc"
    data = _message(_leaf(b"unknown content-transfer-encoding token", 48, cte), b"body\r\n")
    at = _line_start(data, cte)
    defects = [
        _defect(
            "MC-T08",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="未知 CTE 取值 `x-mystery-enc`（既不是 7bit/8bit/binary/quoted-printable/base64，也不是已知扩展 token）",
        )
    ]
    return _case(
        "t-cte-unknown",
        expectation="positive",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(cte,),
        note="§7.5 第 5 条：先判声明值是否已知（T08）→ 再判声明形态合法性 → 最后才判 declared vs observed；CTE 未知时无法交叉校验。",
    )


def t_7bit_long() -> tuple[dict[str, bytes], dict[str, object]]:
    """7bit 行 > 998 octets（MC-T09 → 原句未录，只出 `note`）。"""
    line = b"a" * 1000
    data = _message(_leaf(b"7bit body line longer than 998 octets", 49, _T_CT_7BIT), line + b"\r\n")
    at = _off(data, line)
    defects = [
        _defect(
            "MC-T09",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=RFC_T_DEGRADED_R11,
            detail=f"7bit 正文行 {len(line)} > 998 octets（R11 整行未录 → 只登记）",
        )
    ]
    return _case(
        "t-7bit-long",
        expectation="positive",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(line,),
        note="正文行宽与头行宽是两条账：头行超 998 走 MC-H07（R5 已录），正文行超 998 走本条（R11 未录 → note）。",
    )


def t_undeclared_8bit() -> tuple[dict[str, bytes], dict[str, object]]:
    """未声明 CTE 但正文含 8bit 字节（MC-T10 → 原句未录，只出 `note`）。"""
    body = b"caf\xc3\xa9 latte\r\n"
    data = _message(
        [
            _H_FROM,
            _H_TO,
            b"Subject: 8bit body with no CTE header",
            b"Message-ID: <fixed-0050@example.invalid>",
            _H_MIME,
            b"Content-Type: text/plain; charset=utf-8",
        ],
        body,
    )
    at = _off(data, b"\xc3")
    defects = [
        _defect(
            "MC-T10",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=RFC_T_DEGRADED_R11,
            detail="未声明 Content-Transfer-Encoding（缺省为 7bit），但正文含 8bit 字节（R11 整行未录 → 只登记）",
        )
    ]
    return _case(
        "t-undeclared-8bit",
        expectation="positive",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(body,),
        note="缺省 7bit 的口径来自 R11 的 §6.1 子项（未录原句）→ 本条也只能出 `note`；补齐后提为 hard。",
    )


def t_clean_b64() -> tuple[dict[str, bytes], dict[str, object]]:
    """负例：合法 base64（76 列折行 + 正确填充）。"""
    line1 = b"QUJD" * 19  # 76 字符，恰好整行
    line2 = b"AA=="  # 末组带正确填充
    body = line1 + CRLF + line2 + CRLF
    data = _message(_leaf(b"legal base64 with 76-column folding", 51, _T_CT_B64), body)
    return _case(
        "t-clean-b64",
        expectation="negative",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=[],
        needles=(line1, line2),
        note=(
            "零缺陷基线：数据字符数 80（4 的倍数）、填充只在末尾且数量正确、无字母表外字符、行宽 ≤76。"
            "这条正是「合法 base64 折行」负例 —— 任何 T 簇误报都会打挂它。"
        ),
    )


def t_clean_qp() -> tuple[dict[str, bytes], dict[str, object]]:
    """负例：合法 QP（含真实软换行与合法 =HH）。"""
    body = (
        b"This line ends with a legitimate soft break =\r\n"
        b"and the next line carries an escape =3D plus ordinary text.\r\n"
    )
    data = _message(_leaf(b"legal quoted-printable with a real soft break", 52, _T_CT_QP), body)
    return _case(
        "t-clean-qp",
        expectation="negative",
        source="自造传输编码样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=[],
        needles=(b"soft break =\r\n", b"=3D"),
        note="零缺陷基线：软换行**后面确有下一行**、所有 `=HH` 合法、行宽 ≤76、解码一遍后不再出现字面 `=HH`。",
    )


# ── a 簇：归属与引用（模块 M4 ↔ 里程碑 M5；全部 diff/note，无 hard）────────
#
# **severity 口径（M1 裁决，写进 HANDOFF-M2）**：§7.1 的原句门禁规定「台账无原句 ⇒
# 只能 diff/gray 且 severity=note」。M4 的规则不在五部核对 RFC 之内（D11）→ golden 一律
# `diff/note`；`plan/03` §四 给 A03/A04/A05/A07 写的 `minor` 与 §7.1 冲突 —— M1 以 §7.1
# 为准，并在同一提交内修正 `plan/03` 的摘录。


def _part(headers: list[bytes], body: bytes) -> bytes:
    """一个部件的完整字节（头块 + 空行 + body）。body 需自带行尾。"""
    return CRLF.join(headers) + b"\r\n\r\n" + body


def _mixed_parts(message_id: int, subject: bytes, parts: list[bytes]) -> bytes:
    """`multipart/mixed`（任意个部件）—— a 簇用。"""
    body = b"".join(b"--mix1\r\n" + part for part in parts) + b"--mix1--\r\n"
    headers = [
        _H_FROM,
        _H_TO,
        b"Subject: " + subject,
        f"Message-ID: <fixed-{message_id:04d}@example.invalid>".encode(),
        _H_MIME,
        b'Content-Type: multipart/mixed; boundary="mix1"',
    ]
    return _message(headers, body)


def a_body_attach() -> tuple[dict[str, bytes], dict[str, object]]:
    """文本附件被当正文（MC-A01；复现 SO 6255202）。"""
    data = _mixed_parts(
        60,
        b"text attachment arrives as the body variable",
        [
            _part([_H_CT_TEXT], b"this is the real message body\r\n"),
            _part(
                [
                    b'Content-Type: text/plain; name="notes.txt"',
                    b"Content-Transfer-Encoding: 7bit",
                ],
                b"its contents show up for the body variable instead\r\n",
            ),
        ],
    )
    at = _line_start(data, b'Content-Type: text/plain; name="notes.txt"')
    defects = [
        _defect(
            "MC-A01",
            "diff",
            "note",
            "0.2",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="text/* 叶节点缺可判定 disposition，且 0.1 是兄弟 text/plain 正文候选：下游会把这个文本附件当成正文（SO 6255202 的形状）",
        )
    ]
    return _case(
        "a-body-attach",
        expectation="positive",
        source="SO 6255202——原话：when someone sends an email with a text attachment, the contents of the text file shows up for the body variable",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b'name="notes.txt"',),
        note="M4 全部规则无 hard（D11）：`Content-Disposition` 的正式规范不在本题核对的五部 RFC 内 → `rfc` 写 none-by-design。",
    )


def a_name_mismatch() -> tuple[dict[str, bytes], dict[str, object]]:
    """`name` 与 `filename` 不一致（MC-A02）。"""
    data = _mixed_parts(
        61,
        b"name parameter disagrees with the filename parameter",
        [
            _part([_H_CT_TEXT], b"body\r\n"),
            _part(
                [
                    b'Content-Type: application/pdf; name="a.pdf"',
                    b'Content-Disposition: attachment; filename="report.pdf"',
                    b"Content-Transfer-Encoding: base64",
                ],
                b"JVBERi0xLjQK\r\n",
            ),
        ],
    )
    at = _line_start(data, b"Content-Disposition: attachment; filename=")
    defects = [
        _defect(
            "MC-A02",
            "diff",
            "note",
            "0.2",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail='Content-Type 的 name="a.pdf" 与 Content-Disposition 的 filename="report.pdf" 不一致（下游按不同字段取名会得到两个名字）',
        )
    ]
    return _case(
        "a-name-mismatch",
        expectation="positive",
        source="自造归属样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b'name="a.pdf"', b'filename="report.pdf"'),
        note="filename 取值顺序（先 2231 后 2047）与多字段弥合的记录口径见 `data/README.md` §7.5。",
    )


def a_noname() -> tuple[dict[str, bytes], dict[str, object]]:
    """`filename` 缺失 → 下游显示 Noname（MC-A03；复现 SO 12816042）。"""
    data = _mixed_parts(
        62,
        b"attachment without any filename parameter",
        [
            _part([_H_CT_TEXT], b"body\r\n"),
            _part(
                [
                    b"Content-Type: application/pdf",
                    b"Content-Disposition: attachment",
                    b"Content-Transfer-Encoding: base64",
                ],
                b"JVBERi0xLjQK\r\n",
            ),
        ],
    )
    at = _line_start(data, b"Content-Disposition: attachment")
    defects = [
        _defect(
            "MC-A03",
            "diff",
            "note",
            "0.2",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="attachment 没有任何 filename / name 参数：下游把附件显示成 Noname（SO 12816042 的形状）",
        )
    ]
    return _case(
        "a-noname",
        expectation="positive",
        source="SO 12816042——原话：PDF attachment is called Noname（缺 filename 参数）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"Content-Disposition: attachment",),
        note="`plan/03` §四 原写 minor，与 §7.1 原句门禁冲突 → M1 落 note（同轮修正摘录）。",
    )


def a_cid_open() -> tuple[dict[str, bytes], dict[str, object]]:
    """`cid:` 引用无对应 Content-ID（MC-A04；复现 SO 10107788）。"""
    html = b'<p>logo: <img src="cid:img002@example.invalid"></p>\r\n'
    data = _message(
        [
            _H_FROM,
            _H_TO,
            b"Subject: cid reference without a matching Content-ID",
            b"Message-ID: <fixed-0063@example.invalid>",
            _H_MIME,
            b'Content-Type: multipart/related; boundary="rel1"',
        ],
        b"--rel1\r\n"
        + _part([b"Content-Type: text/html; charset=us-ascii"], html)
        + b"--rel1\r\n"
        + _part(
            [
                b'Content-Type: image/png; name="img001.png"',
                b"Content-ID: <img001@example.invalid>",
                b'Content-Disposition: inline; filename="img001.png"',
                b"Content-Transfer-Encoding: base64",
            ],
            b"iVBORw0KGgo=\r\n",
        )
        + b"--rel1--\r\n",
    )
    at = _off(data, b"cid:img002@example.invalid")
    defects = [
        _defect(
            "MC-A04",
            "diff",
            "note",
            "0.1",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="正文引用 `cid:img002@example.invalid`，但没有任何部件的 Content-ID 与之对应（img001 存在但没人引用）——比较按尖括号内字面值、不 URL 解码",
        )
    ]
    return _case(
        "a-cid-open",
        expectation="positive",
        source="SO 10107788——原话：how to set a name of the embedded image（related / cid 归属）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"cid:img002@example.invalid",),
        note="偏移锚在正文里的 cid: 引用本身（绝对字节偏移），报告能一眼回答「引用了谁、谁没到」。",
    )


def a_related_start() -> tuple[dict[str, bytes], dict[str, object]]:
    """`multipart/related` 的 start 与实际首部件不一致（MC-A05；复现 SO 39328935）。"""
    data = _message(
        [
            _H_FROM,
            _H_TO,
            b"Subject: related start parameter disagrees with the first part",
            b"Message-ID: <fixed-0064@example.invalid>",
            _H_MIME,
            b'Content-Type: multipart/related; boundary="rel1"; '
            b'start="<img001@example.invalid>"; type="text/html"',
        ],
        b"--rel1\r\n"
        + _part(
            [b"Content-Type: text/html; charset=us-ascii", b"Content-ID: <body-root@example.invalid>"],
            b"<p>hello</p>\r\n",
        )
        + b"--rel1\r\n"
        + _part(
            [
                b'Content-Type: image/png; name="img001.png"',
                b"Content-ID: <img001@example.invalid>",
                b'Content-Disposition: inline; filename="img001.png"',
                b"Content-Transfer-Encoding: base64",
            ],
            b"iVBORw0KGgo=\r\n",
        )
        + b"--rel1--\r\n",
    )
    at = _line_start(data, b'start="<img001@example.invalid>"')
    defects = [
        _defect(
            "MC-A05",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail='start 指向 0.2（<img001@example.invalid>），而实际首部件是 0.1（<body-root@example.invalid>）：start 与实际首部件不一致（type="text/html" 与首部件一致，只记 start 这一项）',
        )
    ]
    return _case(
        "a-related-start",
        expectation="positive",
        source="SO 39328935——原话：Why doesn't my embedded image display in Gmail or Office 365?",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b'start="<img001@example.invalid>"',),
        note="`start` 缺省时取第一个子部件（本题口径）；显式给出却不指向首部件 → 登记。",
    )


def a_rfc822() -> tuple[dict[str, bytes], dict[str, object]]:
    """`message/rfc822` 转发体归属无法判定（MC-A06）。"""
    inner = (
        b"From: carol@example.invalid\r\n"
        b"To: dave@example.invalid\r\n"
        b"Subject: forwarded message\r\n"
        b"Message-ID: <fixed-0066@example.invalid>\r\n"
        b"Content-Type: text/plain; charset=us-ascii\r\n"
        b"\r\n"
        b"forwarded body text\r\n"
    )
    data = _mixed_parts(
        65,
        b"forwarded message attached without a disposition",
        [
            _part([_H_CT_TEXT], b"please review the attached message\r\n"),
            _part([b"Content-Type: message/rfc822"], inner),
        ],
    )
    at = _line_start(data, b"Content-Type: message/rfc822")
    defects = [
        _defect(
            "MC-A06",
            "diff",
            "note",
            "0.2",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="message/rfc822 转发体没有 disposition：它是转发副本还是附件无法判定（内层消息自己的头块单独成节）",
        )
    ]
    return _case(
        "a-rfc822",
        expectation="positive",
        source="自造归属样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"Content-Type: message/rfc822",),
        note="嵌套消息的头块属于内层部件（引擎递归下钻），外层只登记归属无法判定。",
    )


def a_inline_nocid() -> tuple[dict[str, bytes], dict[str, object]]:
    """`inline` 却无 Content-ID（MC-A07）。"""
    data = _mixed_parts(
        67,
        b"inline part without a Content-ID",
        [
            _part([_H_CT_TEXT], b"body text\r\n"),
            _part(
                [
                    b'Content-Type: image/png; name="img001.png"',
                    b'Content-Disposition: inline; filename="img001.png"',
                    b"Content-Transfer-Encoding: base64",
                ],
                b"iVBORw0KGgo=\r\n",
            ),
        ],
    )
    at = _line_start(data, b"Content-Disposition: inline; filename=")
    defects = [
        _defect(
            "MC-A07",
            "diff",
            "note",
            "0.2",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="disposition 是 `inline` 却没有 Content-ID：正文无法用 cid: 引用它（内嵌图不显示的一类成因）",
        )
    ]
    return _case(
        "a-inline-nocid",
        expectation="positive",
        source="自造归属样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b"Content-Disposition: inline; filename=",),
        note="与 MC-A04 互不依赖：这里正文不引用 cid:，缺的是被引用的资格（Content-ID 本身）。",
    )


def a_no_disposition() -> tuple[dict[str, bytes], dict[str, object]]:
    """多个叶节点都无可判定 disposition（MC-A08；复现 SO 24246391）。"""
    data = _mixed_parts(
        68,
        b"several leaves without any decidable disposition",
        [
            _part(
                [b'Content-Type: application/octet-stream; name="a.txt"', b"Content-Transfer-Encoding: base64"],
                b"QUJD\r\n",
            ),
            _part(
                [b'Content-Type: application/octet-stream; name="b.txt"', b"Content-Transfer-Encoding: base64"],
                b"QUJD\r\n",
            ),
        ],
    )
    at = _line_start(data, b'Content-Type: multipart/mixed; boundary="mix1"')
    defects = [
        _defect(
            "MC-A08",
            "diff",
            "note",
            "0",
            offset=at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="两个叶节点都缺可判定 disposition，且没有 text/plain 正文候选：下游的正文/附件归属无法判定（SO 24246391 的形状）",
        )
    ]
    return _case(
        "a-no-disposition",
        expectation="positive",
        source="SO 24246391——原话：message-text always goes into attachment",
        infile="msg.eml",
        data=data,
        defects=defects,
        needles=(b'name="a.txt"', b'name="b.txt"'),
        note="登记在 multipart 节点（path `0`）：现象是「整棵树归属不可判定」，不是单个叶节点的账。",
    )


def a_clean_mixed() -> tuple[dict[str, bytes], dict[str, object]]:
    """负例：`multipart/mixed`（正文 + 2 附件）归属全对。"""
    data = _mixed_parts(
        69,
        b"well-formed mixed message with two attachments",
        [
            _part([_H_CT_TEXT], b"the actual body text\r\n"),
            _part(
                [
                    b'Content-Type: application/pdf; name="a.pdf"',
                    b'Content-Disposition: attachment; filename="a.pdf"',
                    b"Content-Transfer-Encoding: base64",
                ],
                b"JVBERi0xLjQK\r\n",
            ),
            _part(
                [
                    b'Content-Type: image/png; name="img001.png"',
                    b'Content-Disposition: attachment; filename="img001.png"',
                    b"Content-Transfer-Encoding: base64",
                ],
                b"iVBORw0KGgo=\r\n",
            ),
        ],
    )
    return _case(
        "a-clean-mixed",
        expectation="negative",
        source="自造归属样本（无外部来源）",
        infile="msg.eml",
        data=data,
        defects=[],
        needles=(b'filename="a.pdf"', b'filename="img001.png"'),
        note="零缺陷基线：正文位 + 两个 attachment（name 与 filename 一致、base64 合法）→ 任何 A 簇误报都会打挂它。",
    )


# ── c 簇：容器层（mbox / Maildir，模块 M5 ↔ 里程碑 M5；全部 diff/note）──────
#
# 偏移口径：容器层用 `message-relative`（§7.10：从该消息的 `From ` 行首起）；路径 `msg#N`
# （N 从 1 起）；文件级偏移另记在 `expect_extra.file_offset`。§7.7 要求**所有变体的切分表**
# 都进报告 —— `expect_extra.variant_split_counts` 登记各读法下的消息条数（字节级表由 M5 产出）。

LF = b"\n"
#: 三条 mboxo 形态的分隔行（ctime 风格日期；全是假数据）。
_SEP_A = b"From alice@example.invalid Thu Jan  1 00:00:00 2026"
_SEP_B = b"From bob@example.invalid Thu Jan  1 00:00:00 2026"
_SEP_C = b"From carol@example.invalid Thu Jan  1 00:00:00 2026"


def c_from_bad() -> tuple[dict[str, bytes], dict[str, object]]:
    """畸形 `From ` 分隔行（MC-C01；复现 cpython #93376）。"""
    malformed = b"From alice@example.invalid"  # 缺日期字段
    data = (
        _SEP_A + LF
        + b"From: alice@example.invalid" + LF
        + b"To: bob@example.invalid" + LF
        + b"Subject: first message" + LF
        + b"Message-ID: <fixed-0070@example.invalid>" + LF
        + LF
        + b"first body" + LF
        + malformed + LF
        + b"From: carol@example.invalid" + LF
        + b"To: alice@example.invalid" + LF
        + b"Subject: second message with a malformed separator" + LF
        + b"Message-ID: <fixed-0071@example.invalid>" + LF
        + LF
        + b"second body" + LF
    )
    at = _off(data, malformed + LF)
    defects = [
        _defect(
            "MC-C01",
            "diff",
            "note",
            "msg#2",
            offset=0,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="分隔行 `From alice@example.invalid` 缺日期字段（envelope 无法解析）：mbox 约定是 `From <地址> <日期>`，它不是 RFC（D3）→ 只登记（文件内位置见 expect_extra.file_offset）",
            offset_kind=C.OFFSET_MESSAGE_RELATIVE,
        )
    ]
    return _case(
        "c-from-bad",
        expectation="positive",
        source="cpython #93376（open）—— issue 原话：mailbox.mbox malformed From lines not being detected/handled",
        infile="mail.mbox",
        data=data,
        defects=defects,
        needles=(malformed + LF,),
        extra={"variant_split_counts": {"mboxo": 2, "mboxrd": 2, "mboxcl": 2}, "auto": "mboxo", "file_offset": at},
        note="该行仍被当作消息边界（片段自身可解析）→ 唯一的问题是分隔行形态，不再叠报其他容器规则。",
    )


def c_from_unescaped() -> tuple[dict[str, bytes], dict[str, object]]:
    """正文里的 `From ` 行未转义 → 变体间切分表不一致（MC-C02）。"""
    body_region = b"body line one" + LF + _SEP_A + LF + b"body line three" + LF
    cl = str(len(body_region)).encode()
    data = (
        _SEP_A + LF
        + b"From: alice@example.invalid" + LF
        + b"To: bob@example.invalid" + LF
        + b"Subject: an unescaped From line sits in this body" + LF
        + b"Message-ID: <fixed-0072@example.invalid>" + LF
        + b"Content-Length: " + cl + LF
        + LF
        + body_region
        + _SEP_C + LF
        + b"From: carol@example.invalid" + LF
        + b"To: alice@example.invalid" + LF
        + b"Subject: second real message" + LF
        + b"Message-ID: <fixed-0073@example.invalid>" + LF
        + LF
        + b"second body" + LF
    )
    inner_at = _off(data, _SEP_A, len(_SEP_A) + 1)  # 第二处出现（第一处在文件开头）
    defects = [
        _defect(
            "MC-C02",
            "diff",
            "note",
            "msg#1",
            offset=inner_at,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="正文里的 `From ` 行未转义（mboxo 约定应写成 `>From `）：mboxo/mboxrd 读法在此误切一条消息，mboxcl 按 Content-Length 不受影响 → 各变体切分表不一致，全部要输出",
            offset_kind=C.OFFSET_MESSAGE_RELATIVE,
        )
    ]
    return _case(
        "c-from-unescaped",
        expectation="positive",
        source="HN 32979369 / HN 6855700（mbox 转义问题；逐字原话见 data/README.md §1.4，本 case 只引编号、不改写引文）",
        infile="mail.mbox",
        data=data,
        defects=defects,
        needles=(_SEP_A, b"Content-Length: " + cl + LF),
        extra={
            "variant_split_counts": {"mboxo": 3, "mboxrd": 3, "mboxcl": 2},
            "auto": "mboxcl",
            "content_length": len(body_region),
        },
        note="`auto` 按 §7.7 的纯字节规则：出现 `Content-Length:` 头 → mboxcl（本 case 的主表）。变体差异即本规则的证据。",
    )


def c_empty_msg() -> tuple[dict[str, bytes], dict[str, object]]:
    """零长度消息（MC-C03）。"""
    data = (
        _SEP_A + LF
        + b"From: alice@example.invalid" + LF
        + b"To: bob@example.invalid" + LF
        + b"Subject: first message" + LF
        + b"Message-ID: <fixed-0074@example.invalid>" + LF
        + LF
        + b"first body" + LF
        + _SEP_B + LF
        + _SEP_C + LF
        + b"From: carol@example.invalid" + LF
        + b"To: alice@example.invalid" + LF
        + b"Subject: third message" + LF
        + b"Message-ID: <fixed-0075@example.invalid>" + LF
        + LF
        + b"third body" + LF
    )
    at = _off(data, _SEP_B + LF)
    defects = [
        _defect(
            "MC-C03",
            "diff",
            "note",
            "msg#2",
            offset=0,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="零长度消息：`From ` 分隔行（bob）与下一条分隔行（carol）之间没有任何字节（文件内位置见 expect_extra.file_offset）",
            offset_kind=C.OFFSET_MESSAGE_RELATIVE,
        )
    ]
    return _case(
        "c-empty-msg",
        expectation="positive",
        source="自造容器样本（无外部来源）",
        infile="mail.mbox",
        data=data,
        defects=defects,
        needles=(_SEP_B + LF + _SEP_C + LF,),
        extra={"variant_split_counts": {"mboxo": 3, "mboxrd": 3, "mboxcl": 3}, "auto": "mboxo", "file_offset": at},
        note="空消息仍占一个 `msg#N` 序号（后面的消息序号不回收）——序号按分隔行出现顺序、不按内容长度。",
    )


def c_body_from() -> tuple[dict[str, bytes], dict[str, object]]:
    """正文含裸 `From ` 行 → 被误当分隔行（MC-C04）。"""
    data = (
        _SEP_A + LF
        + b"From: alice@example.invalid" + LF
        + b"To: bob@example.invalid" + LF
        + b"Subject: raw From line in the body" + LF
        + b"Message-ID: <fixed-0076@example.invalid>" + LF
        + LF
        + b"body line one" + LF
        + _SEP_B + LF
        + b"body line three" + LF
    )
    at = _off(data, _SEP_B + LF)
    defects = [
        _defect(
            "MC-C04",
            "diff",
            "note",
            "msg#2",
            offset=0,
            rfc=C.RFC_NONE_BY_DESIGN,
            detail="该 `From ` 行信封完整，但它是被误当分隔行的正文内容 —— 切出的片段不具备消息头块：正文含裸 `From ` 行的直接证据（本节无 Content-Length，三种读法一致误切）",
            offset_kind=C.OFFSET_MESSAGE_RELATIVE,
        )
    ]
    return _case(
        "c-body-from",
        expectation="positive",
        source="自造容器样本（无外部来源）",
        infile="mail.mbox",
        data=data,
        defects=defects,
        needles=(_SEP_B + LF,),
        extra={"variant_split_counts": {"mboxo": 2, "mboxrd": 2, "mboxcl": 2}, "auto": "mboxo", "file_offset": at},
        note="与 MC-C02 的分工：C02 = 变体读法**不一致**（有 Content-Length 兜住的那类）；C04 = 三种读法**一致**误切（片段不成消息）。",
    )


def c_maildir_name() -> tuple[dict[str, bytes], dict[str, object]]:
    """Maildir 条目名不合规（MC-C05）。"""
    msg = (
        b"From: alice@example.invalid" + LF
        + b"To: bob@example.invalid" + LF
        + b"Subject: maildir entry whose name is not compliant" + LF
        + b"Message-ID: <fixed-0077@example.invalid>" + LF
        + LF
        + b"body" + LF
    )
    return _case(
        "c-maildir-name",
        expectation="positive",
        source="自造容器样本（无外部来源）",
        infile="maildir/cur/1700000000-bad-name",
        data=msg,
        defects=[
            _defect(
                "MC-C05",
                "diff",
                "note",
                "msg#1",
                offset=0,
                rfc=C.RFC_NONE_BY_DESIGN,
                detail="cur/ 下的条目名 `1700000000-bad-name` 缺 `:2,<flags>` 信息段（Maildir 约定：cur 条目应为 `<unique>:2,<flags>`）；Maildir 没有 RFC 依据 → 只登记",
            )
        ],
        needles=(),
        extra={
            "container": "maildir",
            "entry": "cur/1700000000-bad-name",
            "offset_note": "规则作用于文件名、无字节偏移 → offset=0 是占位",
        },
        note="输入是目录形态（Maildir）：`input.file` 指向目录里的条目，M5 的 golden 回归按 case 目录下的 `maildir/` 定位容器。",
    )


def c_clean_mbox() -> tuple[dict[str, bytes], dict[str, object]]:
    """负例：干净 mbox（3 条消息 + 正确转义）。"""
    data = (
        _SEP_A + LF
        + b"From: alice@example.invalid" + LF
        + b"To: bob@example.invalid" + LF
        + b"Subject: clean message one" + LF
        + b"Message-ID: <fixed-0078@example.invalid>" + LF
        + LF
        + b">From the desk of alice" + LF
        + b"regular body line" + LF
        + _SEP_B + LF
        + b"From: bob@example.invalid" + LF
        + b"To: carol@example.invalid" + LF
        + b"Subject: clean message two" + LF
        + b"Message-ID: <fixed-0079@example.invalid>" + LF
        + LF
        + b"another body" + LF
        + _SEP_C + LF
        + b"From: carol@example.invalid" + LF
        + b"To: alice@example.invalid" + LF
        + b"Subject: clean message three" + LF
        + b"Message-ID: <fixed-0080@example.invalid>" + LF
        + LF
        + b"third body" + LF
    )
    return _case(
        "c-clean-mbox",
        expectation="negative",
        source="自造容器样本（无外部来源）",
        infile="mail.mbox",
        data=data,
        defects=[],
        needles=(b">From the desk of alice" + LF,),
        extra={"variant_split_counts": {"mboxo": 3, "mboxrd": 3, "mboxcl": 3}, "auto": "mboxo"},
        note="零缺陷基线：`>From ` 行是**正确转义**（原正文行以 `From ` 开头）。它的读法差异（mboxo 保留 / mboxrd 反转义）属变体行为、不构成违规；MC-C02 只在「未转义（裸 `From ` 行被误当分隔行）」时触发。",
    )


# ── 注册表 · 构造期自检 · 入口 ──────────────────────────────────────────────

CASES: tuple[Callable[[], tuple[dict[str, bytes], dict[str, object]]], ...] = (
    # b 簇：树与边界
    b_no_boundary, b_boundary_long, b_delim_not_bol, b_close_malformed, b_inner_dup,
    b_no_final, b_preamble_epilogue, b_empty_multipart, b_deep_nest, b_clean_nested,
    b_wrapped_header,
    # h 簇：头编码
    h_ew_long, h_ew_line_long, h_ew_space, h_q_invalid, h_b_length, h_2231_seq,
    h_2231_quote, h_2231_pct, h_8bit_header, h_ew_newline, h_line_998, h_clean_folded,
    # t 簇：传输编码
    t_cte_mismatch, t_b64_pad, t_b64_len, t_b64_foreign, t_qp_long, t_qp_soft,
    t_qp_artifact, t_qp_double, t_cte_unknown, t_7bit_long, t_undeclared_8bit,
    t_clean_b64, t_clean_qp,
    # a 簇：归属与引用
    a_body_attach, a_name_mismatch, a_noname, a_cid_open, a_related_start, a_rfc822,
    a_inline_nocid, a_no_disposition, a_clean_mixed,
    # c 簇：容器层
    c_from_bad, c_from_unescaped, c_empty_msg, c_body_from, c_maildir_name, c_clean_mbox,
)


def case_name(func_name: str) -> str:
    """函数名 → case 目录名（下划线换连字符）。"""
    return func_name.replace("_", "-")


def _parsed_defects(expect: dict[str, object]) -> list[Defect]:
    """把落盘形态的 defects（``class`` 是序列化键）重建成 :class:`Defect` 对象。"""
    rows = expect["defects"]
    assert isinstance(rows, list)
    parsed: list[Defect] = []
    for index, row in enumerate(rows):
        assert isinstance(row, dict), f"defects[{index}] 不是对象"
        parsed.append(
            Defect(
                rule_id=str(row["rule_id"]),
                klass=str(row["class"]),
                severity=str(row["severity"]),
                path=str(row["path"]),
                offset=int(row["offset"]),
                offset_kind=str(row["offset_kind"]),
                rfc=str(row["rfc"]),
                detail=str(row["detail"]),
            )
        )
    return parsed


def _self_check(name: str, files: dict[str, bytes], expect: dict[str, object]) -> None:
    """构造期自检（`plan/04` §三.2）—— **挂在 build() 里**，``--check`` 也会跑。

    判据：
    1. ``case`` 与目录名一致；``expectation`` 合法；
    2. 输入文件在产出里，且 sha256 / 字节数可复算；
    3. 正例 ``defects`` 非空、负例 ``defects == []``；
    4. 每条缺陷六元组合法、``rfc`` 非空（D8）、落盘即按 (rule_id, path, offset) 有序；
    5. ``defect_count`` / ``exit_code`` / ``fingerprint`` 由构造复算，不手写魔数；
    6. 证据锚点必须真在输入字节里（"正例文件确实含它声称的字节"）；
    7. 隐私红线：所有产出的字节里不得出现真实 TLD。
    """
    if expect.get("case") != name:
        raise AssertionError(f"{name}: expect.case 与目录名不一致: {expect.get('case')!r}")
    expectation = expect.get("expectation")
    if expectation not in {"positive", "negative"}:
        raise AssertionError(f"{name}: expectation 非法: {expectation!r}")

    info = expect["input"]
    assert isinstance(info, dict)
    rel = str(info["file"])
    if rel not in files:
        raise AssertionError(f"{name}: input.file {rel!r} 不在产出的文件里")
    blob = files[rel]
    if hashlib.sha256(blob).hexdigest() != info["sha256"]:
        raise AssertionError(f"{name}: input.sha256 与字节不一致")
    if len(blob) != info["bytes"]:
        raise AssertionError(f"{name}: input.bytes 与字节数不一致")

    defects = expect["defects"]
    assert isinstance(defects, list)
    if expectation == "positive" and not defects:
        raise AssertionError(f"{name}: 正例的 defects 不得为空")
    if expectation == "negative" and defects:
        raise AssertionError(f"{name}: 负例的 defects 必须为空")

    parsed = _parsed_defects(expect)
    for defect in parsed:
        defect.validate()
        if not defect.rfc.strip():
            raise AssertionError(f"{name}: {defect.rule_id} 的 rfc 为空（D8）")
    keys = [defect.sort_key for defect in parsed]
    if keys != sorted(keys):
        raise AssertionError(f"{name}: defects 未按 (rule_id, path, offset) 排序")

    if expect["defect_count"] != len(parsed):
        raise AssertionError(f"{name}: defect_count 与 defects 长度不一致")
    if expect["exit_code"] != decide_exit_code(parsed, fail_on=C.FAIL_ON_DEFAULT):
        raise AssertionError(f"{name}: exit_code 无法由缺陷集复算")
    if expect["fingerprint"] != fingerprint(parsed):
        raise AssertionError(f"{name}: fingerprint 无法复算")

    for needle in _NEEDLES.get(name, ()):
        if needle not in blob:
            raise AssertionError(f"{name}: 输入字节里找不到证据锚点 {needle!r}")

    for file_rel, content in files.items():
        _assert_no_foreign_domains(content, f"{name}/{file_rel}")


def _check_clusters(collected: list[tuple[str, dict[str, bytes], dict[str, object]]]) -> None:
    """矩阵自检：每个规则簇（b/h/t/a/c）≥2 正例 + ≥1 负例（`plan/04` §二）。"""
    stats: dict[str, list[int]] = {}
    for name, _files, expect in collected:
        bucket = stats.setdefault(name.split("-", 1)[0], [0, 0])
        bucket[0 if expect["expectation"] == "positive" else 1] += 1
    for prefix, (positives, negatives) in sorted(stats.items()):
        if positives < 2 or negatives < 1:
            raise AssertionError(
                f"{prefix}-* 簇：正例 {positives}、负例 {negatives}（要求 ≥2 正例 + ≥1 负例）"
            )


def _collect() -> list[tuple[str, dict[str, bytes], dict[str, object]]]:
    """跑完所有 case 并逐条自检（发现任何不一致立即 AssertionError）。"""
    if not CASES:
        raise AssertionError("CASES 为空 —— 判据空跑")
    collected: list[tuple[str, dict[str, bytes], dict[str, object]]] = []
    for case_fn in CASES:
        name = case_name(case_fn.__name__)
        files, expect = case_fn()
        _self_check(name, files, expect)
        collected.append((name, files, expect))
    return collected


def _write_case(case_dir: Path, files: dict[str, bytes], expect: dict[str, object]) -> None:
    """落盘一个 case：入仓字节（可能含 `maildir/…` 子路径）+ `expect.json` + `README.md`。"""
    for rel, blob in files.items():
        target = case_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)  # 一律 write_bytes：golden 的字节就是被测对象
    (case_dir / "expect.json").write_bytes(dumps(expect).encode("utf-8"))
    (case_dir / "README.md").write_bytes(_render_readme(str(expect["case"]), expect))


def _tree_diff(expected: Path, actual: Path) -> list[str]:
    """逐字节比对两棵树；返回差异列表（空 = 一致）。"""
    if not expected.is_dir():
        return [f"语料目录不存在: {expected}"]
    expected_files = {p.relative_to(expected): p for p in expected.rglob("*") if p.is_file()}
    actual_files = {p.relative_to(actual): p for p in actual.rglob("*") if p.is_file()}
    diffs: list[str] = []
    for rel in sorted(expected_files.keys() | actual_files.keys(), key=lambda p: p.as_posix()):
        if rel not in expected_files:
            diffs.append(f"{rel}: 只出现在生成结果里（语料目录缺该文件）")
            continue
        if rel not in actual_files:
            diffs.append(f"{rel}: 只出现在语料目录里（生成器不产出该文件）")
            continue
        left = expected_files[rel].read_bytes()
        right = actual_files[rel].read_bytes()
        if left != right:
            diffs.append(f"{rel}: 字节不一致（语料 {len(left)}B vs 生成 {len(right)}B）")
    return diffs


def build(out_dir: object) -> None:
    """把全部 case 写到 ``out_dir``（每个 case 一个子目录）。

    **自检挂在本函数末尾**（`plan/04` §三）：逐 case ``_self_check`` + 全簇矩阵检查，
    任何一条不成立都在**写盘前**抛 AssertionError（不落半套语料）。
    """
    collected = _collect()
    _check_clusters(collected)
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    for name, files, expect in collected:
        _write_case(root / name, files, expect)


def check(expected_dir: object) -> int:
    """在系统临时目录重建并与 ``expected_dir`` 逐字节比对；返回进程退出码。"""
    expected_root = Path(expected_dir)
    if not expected_root.is_dir():
        sys.stderr.write(f"gen_golden: 语料目录不存在: {expected_root}\n")
        return 1
    with tempfile.TemporaryDirectory(prefix="mimeconform-golden-") as tmp:
        build(Path(tmp) / "golden")  # build() 内部含自检；临时目录不在仓库内
        diffs = _tree_diff(expected_root, Path(tmp) / "golden")
    if diffs:
        sys.stdout.write(f"{len(CASES)} cases, {len(diffs)} diff\n")
        for line in diffs:
            sys.stdout.write(f"DIFF  {line}\n")
        return 1
    sys.stdout.write(f"{len(CASES)} cases, 0 diff\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mimeconform.devtools.gen_golden",
        description="golden 语料生成器（里程碑 M1）：默认写入 data/golden；--check 位级核对",
    )
    parser.add_argument("--out", metavar="DIR", default="data/golden", help="输出目录（--check 时为比对基准）")
    parser.add_argument("--check", action="store_true", help="在系统临时目录重建并逐字节比对，不写仓库")
    args = parser.parse_args(argv)

    if args.check:
        return check(args.out)
    build(args.out)
    sys.stdout.write(f"{len(CASES)} cases 已写入 {args.out}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
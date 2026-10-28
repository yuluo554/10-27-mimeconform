"""归属与引用审计（模块 M4 / 里程碑 M5）。

**全部规则 ``diff`` / ``note``，无 ``hard``**（`plan/00` D11）：
``Content-Disposition`` 与 ``multipart/related`` 的规范定义不在本题核对的五部 RFC
（2045/2046/2047/2231/5322）之内。按"不得编造条款"红线，宁可全降级。

``filename`` 取值顺序：先 RFC 2231（含续行）→ 再 RFC 2047（`plan/00` D10）——
本模块是 `headers.decode_filename` 的**调用点**（顺序写在那边，不在这里重写）。

**偏移口径**（与 `data/golden/a-*/expect.json` 对齐）：

* A01 → 该叶节点 ``Content-Type`` 头**行首**；
* A02 / A03 / A07 → 该节点 ``Content-Disposition`` 头**行首**；
* A04 → 正文里那处 ``cid:`` 引用的**绝对字节偏移**（`offset_kind="absolute"`）；
* A05 / A08 → 该 multipart 节点 ``Content-Type`` 头**行首**（`path` 指向该节点）；
* A06 → ``message/rfc822`` 叶节点的 ``Content-Type`` 头**行首**。

**分层**：本模块位于 `headers` 之上（`plan/02` §一），因此可 import `headers`
（`filename` 取值），但**不得** import `scan` / `transfer` / `report` / `cli`。

**保守判定的三条纪律**（误报是本题最贵的失败）：

1. A01 只在"叶节点自身带 ``name``/``filename`` 参数（像附件）+ 同父有纯文本正文候选"时触发
   —— 没有 name 的 `text/html` 与 `text/plain` 并列**不是**缺陷（`b-wrapped-header` 的形态）；
2. A08 只在"同一 multipart 至少两个叶节点、全部缺可判定 disposition、且没有 text/plain
   正文候选"时触发 —— 有正文候选时归属是**可判定**的（`a-unrelated` 类形态不报）；
3. ``cid:`` 比较按**尖括号内字面值、不 URL 解码**（`plan/01` §二 模块 M4 确定性纪律）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import constants as C
from .headers import HeaderBlock, decode_filename, parse_headers
from .model import Defect, Header, Node

#: MC-A 系列的静态形态（``class`` / ``severity`` / ``rfc``）—— 引擎侧的唯一定义点。
#: 与 ``mimeconform/rules/catalog.json`` **逐值一致**
#: （``tests/test_catalog_consistency.py`` 断言；``plan/03`` §四 / §九）。
#: A 簇全部 ``diff/note`` + ``none-by-design``：`Content-Disposition` / `multipart/related`
#: 不在五部核对 RFC 内（D11），台账里没有任何可引原句的子项。
_RULE_META: dict[str, tuple[str, str, str]] = {
    "MC-A01": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-A02": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-A03": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-A04": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-A05": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-A06": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-A07": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-A08": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
}

#: 可判定的 disposition 取值（其余 token 一律按"无法判定"处理，不猜）。
_DECIDABLE_DISPOSITIONS = frozenset({"attachment", "inline"})

#: 正文里的 ``cid:`` 引用：取到第一个分隔符为止（引号 / 空白 / 尖括号 / 括号）。
#: **不做 URL 解码** —— 比较的就是这个字面值（`plan/01` §二 模块 M4）。
_CID_REFERENCE = re.compile(rb"cid:([^\s\"'<>()\[\]]+)")


@dataclass(frozen=True, slots=True)
class Attachment:
    """一个叶节点的归属事实（报告/测试消费；判定在 :func:`audit_attribution`）。"""

    path: str
    disposition: str | None
    filename: str | None
    name: str | None
    content_id: str | None
    referenced_by: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class AttributionResult:
    attachments: tuple[Attachment, ...] = field(default=())
    defects: tuple[Defect, ...] = field(default=())


# ── 节点事实（只读；不做判定）─────────────────────────────────────────────


def _iter_nodes(node: Node):
    yield node
    for child in node.children:
        yield from _iter_nodes(child)


def _block_of(node: Node, data: bytes) -> HeaderBlock:
    """还原节点头块并交给 `headers.parse_headers`（取参数与 encoded-word 事实）。

    为什么要绕一趟：``scan`` 只做头块**定位**（名字 / 行跨度），``Header.params`` 一律留空
    （`plan/03` §二 的落法 ①）。参数事实由 `headers` 这一层给出，`attribution` 消费它。
    """
    if not node.headers:
        return HeaderBlock()
    start = node.headers[0].line_spans[0][0]
    end = node.headers[-1].line_spans[-1][1]
    return parse_headers(data[start:end], start, path=node.path)


def _find(headers: tuple[Header, ...], name: str) -> Header | None:
    for header in headers:
        if header.name.lower() == name:
            return header
    return None


def _raw_value(data: bytes, header: Header) -> bytes:
    """头字段值的原始字节（第一个冒号之后，含内部折行）。"""
    start = header.line_spans[0][0]
    end = header.line_spans[-1][1]
    raw = data[start:end]
    colon = raw.find(b":")
    return raw[colon + 1 :] if colon >= 0 else raw


def _line_start(header: Header | None, fallback: int) -> int:
    if header is None or not header.line_spans:
        return fallback
    return header.line_spans[0][0]


def _disposition_token(data: bytes, header: Header | None) -> str | None:
    """``Content-Disposition`` 的首个 token（小写）；缺失或空值时 ``None``。"""
    if header is None:
        return None
    text = _raw_value(data, header).decode("latin-1")
    token = text.split(";", 1)[0].strip().split()
    return token[0].lower() if token else None


def _plain_param(params: tuple[dict[str, object], ...] | list[dict[str, object]], stem: str) -> str | None:
    """取**普通形态** ``stem=value`` 的值（扩展形态 ``stem*`` 不在本轮口径内，见模块 docstring）。"""
    for param in params:
        if str(param.get("name") or "").lower() == stem:
            return str(param.get("value") or "")
    return None


def _content_id(data: bytes, header: Header | None) -> str | None:
    """``Content-ID`` 的尖括号内字面值；无头或空值时 ``None``。"""
    if header is None:
        return None
    text = _raw_value(data, header).decode("latin-1").strip()
    if text.startswith("<") and text.endswith(">") and len(text) >= 2:
        return text[1:-1]
    return text or None


@dataclass(frozen=True, slots=True)
class _Facts:
    node: Node
    disposition: str | None
    filename: str | None
    has_filename_param: bool
    name: str | None
    content_id: str | None
    content_type_line: int
    disposition_line: int


def _facts(node: Node, data: bytes) -> _Facts:
    """一个节点的归属事实（纯读取）。"""
    block = _block_of(node, data)
    headers = block.headers
    ctx = _find(headers, "content-type") or _find(node.headers, "content-type")
    cd = _find(headers, "content-disposition") or _find(node.headers, "content-disposition")
    cid = _find(headers, "content-id") or _find(node.headers, "content-id")

    params_ct: tuple[dict[str, object], ...] = ctx.params if ctx is not None else ()
    params_cd: tuple[dict[str, object], ...] = cd.params if cd is not None else ()

    filename: str | None = None
    has_filename_param = any(
        str(param.get("name") or "").lower().startswith("filename") for param in params_cd
    )
    if cd is not None and has_filename_param:
        raw = _raw_value(data, cd)
        try:
            filename = decode_filename(list(params_cd), raw.decode("latin-1"))
        except ValueError:
            # 续行编号不连续（MC-H09 已记账）：取值层不猜，按"无法解码"处理。
            filename = None

    body_start = node.body_range[0]
    return _Facts(
        node=node,
        disposition=_disposition_token(data, cd),
        filename=filename,
        has_filename_param=has_filename_param,
        name=_plain_param(params_ct, "name"),
        content_id=_content_id(data, cid),
        content_type_line=_line_start(ctx, node.headers[0].line_spans[0][0] if node.headers else body_start),
        disposition_line=_line_start(cd, body_start),
    )


# ── 缺陷构造 ──────────────────────────────────────────────────────────────


def _defect(rule_id: str, path: str, offset: int, detail: str) -> Defect:
    klass, severity, rfc = _RULE_META[rule_id]
    defect = Defect(
        rule_id=rule_id,
        klass=klass,
        severity=severity,
        path=path,
        offset=offset,
        offset_kind=C.OFFSET_ABSOLUTE,
        rfc=rfc,
        detail=detail,
    )
    defect.validate()
    return defect


def _is_leaf(node: Node) -> bool:
    return not node.children and not node.content_type.startswith("multipart/")


def _is_body_candidate(facts: _Facts) -> bool:
    """正文候选：`text/plain`、无 ``name`` 参数、无可判定 disposition。"""
    return (
        facts.node.content_type == "text/plain"
        and facts.name is None
        and facts.disposition is None
    )


# ── 逐规则判定 ────────────────────────────────────────────────────────────


def _a01_a08(parents: list[tuple[Node, list[_Facts]]]) -> list[Defect]:
    """A01（文本附件被当正文）与 A08（多个叶节点都无可判定 disposition）。"""
    out: list[Defect] = []
    for parent, facts_list in parents:
        if parent.content_type == "multipart/alternative":
            continue  # alternative 的多个 text/* 是**同义正文**，不是"附件被当正文"
        leaves = [facts for facts in facts_list if _is_leaf(facts.node)]
        if not leaves:
            continue
        body_candidate = next((facts for facts in leaves if _is_body_candidate(facts)), None)

        # MC-A01：某 text/* 叶节点自带 name/filename（像附件）、缺可判定 disposition，
        # 且同父存在纯文本正文候选 → 下游会把它当正文（SO 6255202）。
        if body_candidate is not None:
            for facts in leaves:
                if facts is body_candidate:
                    continue
                if not facts.node.content_type.startswith("text/"):
                    continue
                if facts.disposition is not None:
                    continue
                if facts.name is None and not facts.has_filename_param:
                    continue
                out.append(
                    _defect(
                        "MC-A01",
                        facts.node.path,
                        facts.content_type_line,
                        f"text/* 叶节点缺可判定 disposition，且 {body_candidate.node.path} 是兄弟 "
                        "text/plain 正文候选：下游会把这个文本附件当成正文（SO 6255202 的形状）",
                    )
                )

        # MC-A08：同一 multipart/*mixed* 至少两个叶节点、全部缺可判定 disposition、且无正文候选。
        # 只对 `multipart/mixed` 判：`related` 的首部件本身就是正文、`alternative` 是正文同义，
        # 对它们判"归属不可判定"只会制造噪声（误报是本题最贵的失败）。
        if (
            parent.content_type == "multipart/mixed"
            and len(leaves) >= 2
            and all(facts.disposition is None for facts in leaves)
            and body_candidate is None
        ):
            out.append(
                _defect(
                    "MC-A08",
                    parent.path,
                    _parent_content_type_line(parent),
                    f"{len(leaves)} 个叶节点都缺可判定 disposition，且没有 text/plain 正文候选："
                    "下游的正文/附件归属无法判定（SO 24246391 的形状）",
                )
            )
    return out


def _parent_content_type_line(parent: Node) -> int:
    header = _find(parent.headers, "content-type")
    if header is not None and header.line_spans:
        return header.line_spans[0][0]
    return parent.body_range[0]


def _a02_to_a07(facts_list: list[_Facts]) -> list[Defect]:
    """A02 / A03 / A06 / A07：单节点就能判的归属事实。"""
    out: list[Defect] = []
    for facts in facts_list:
        if not _is_leaf(facts.node):
            continue
        # MC-A02：name 与 filename 不一致（两个字段都给名，但给的不是同一个名）。
        if facts.name is not None and facts.filename is not None and facts.name != facts.filename:
            out.append(
                _defect(
                    "MC-A02",
                    facts.node.path,
                    facts.disposition_line,
                    f'Content-Type 的 name="{facts.name}" 与 Content-Disposition 的 '
                    f'filename="{facts.filename}" 不一致（下游按不同字段取名会得到两个名字）',
                )
            )
        # MC-A03：声明了 disposition 却没有任何名字参数（下游显示 Noname）。
        if (
            facts.disposition in _DECIDABLE_DISPOSITIONS
            and not facts.has_filename_param
            and facts.name is None
        ):
            out.append(
                _defect(
                    "MC-A03",
                    facts.node.path,
                    facts.disposition_line,
                    "attachment 没有任何 filename / name 参数：下游把附件显示成 Noname"
                    "（SO 12816042 的形状）",
                )
            )
        # MC-A06：message/rfc822 转发体没有 disposition（转发副本还是附件无法判定）。
        if facts.node.content_type == "message/rfc822" and facts.disposition is None:
            out.append(
                _defect(
                    "MC-A06",
                    facts.node.path,
                    facts.content_type_line,
                    "message/rfc822 转发体没有 disposition：它是转发副本还是附件无法判定"
                    "（内层消息自己的头块单独成节）",
                )
            )
        # MC-A07：inline 却没有 Content-ID（正文无法用 cid: 引用它）。
        if facts.disposition == "inline" and facts.content_id is None:
            out.append(
                _defect(
                    "MC-A07",
                    facts.node.path,
                    facts.disposition_line,
                    "disposition 是 `inline` 却没有 Content-ID：正文无法用 cid: 引用它"
                    "（内嵌图不显示的一类成因）",
                )
            )
    return out


def _a04(facts_list: list[_Facts], data: bytes) -> list[Defect]:
    """MC-A04：正文 ``cid:`` 引用无对应 ``Content-ID``（比较尖括号内字面值）。"""
    known = {facts.content_id for facts in facts_list if facts.content_id}
    seen: dict[str, tuple[str, int]] = {}
    for facts in facts_list:
        node = facts.node
        if not _is_leaf(node):
            continue
        start, end = node.body_range
        for match in _CID_REFERENCE.finditer(data[start:end]):
            literal = match.group(1).decode("latin-1")
            if literal in known or literal in seen:
                continue
            seen[literal] = (node.path, start + match.start())
    out: list[Defect] = []
    for literal, (path, offset) in seen.items():
        out.append(
            _defect(
                "MC-A04",
                path,
                offset,
                f"正文引用 `cid:{literal}`，但没有任何部件的 Content-ID 与之对应"
                "（比较按尖括号内字面值、不 URL 解码）",
            )
        )
    return out


def _a05(parents: list[tuple[Node, list[_Facts]]], data: bytes) -> list[Defect]:
    """MC-A05：``multipart/related`` 的 ``start`` / ``type`` 与实际首部件不一致。"""
    out: list[Defect] = []
    for parent, facts_list in parents:
        if parent.content_type != "multipart/related":
            continue
        if not facts_list:
            continue
        first = facts_list[0]
        header = _find(_block_of(parent, data).headers, "content-type")
        params = header.params if header is not None else ()
        start_param = _plain_param(params, "start")
        type_param = _plain_param(params, "type")
        problems: list[str] = []
        if start_param is not None:
            expected = f"<{first.content_id}>" if first.content_id else None
            if expected is None or start_param != expected:
                problems.append(
                    f"start={start_param} 而实际首部件是 {first.node.path}"
                    f"（{expected or '无 Content-ID'}）"
                )
        if type_param is not None and type_param.lower() != first.node.content_type:
            problems.append(f'type="{type_param}" 而实际首部件是 {first.node.content_type}')
        if problems:
            out.append(
                _defect(
                    "MC-A05",
                    parent.path,
                    _parent_content_type_line(parent),
                    "；".join(problems) + "：multipart/related 的 start/type 与实际首部件不一致"
                    "（SO 39328935 的形状）",
                )
            )
    return out


# ── 入口 ──────────────────────────────────────────────────────────────────


def audit_attribution(root: Node, data: bytes) -> AttributionResult:
    """遍历整棵树，产出 MC-A 系列缺陷与归属事实。

    ``root`` 是 `scan.scan_message` 的默认树；``data`` 是整封邮件的原始字节
    （用于取头块字节与正文里的 ``cid:`` 引用）。
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"data 必须是 bytes（收到 {type(data).__name__}）")
    data = bytes(data)

    facts_by_node = [_facts(node, data) for node in _iter_nodes(root)]
    parents: list[tuple[Node, list[_Facts]]] = []
    for node in _iter_nodes(root):
        if not node.content_type.startswith("multipart/"):
            continue
        children = [_facts(child, data) for child in node.children]
        parents.append((node, children))

    defects: list[Defect] = []
    defects.extend(_a01_a08(parents))
    defects.extend(_a02_to_a07(facts_by_node))
    defects.extend(_a04(facts_by_node, data))
    defects.extend(_a05(parents, data))

    # 引用闭合（附件事实）：cid 引用 → 哪些叶节点引用了它。
    referenced: dict[str, list[str]] = {}
    for facts in facts_by_node:
        if not _is_leaf(facts.node):
            continue
        start, end = facts.node.body_range
        for match in _CID_REFERENCE.finditer(data[start:end]):
            literal = match.group(1).decode("latin-1")
            bucket = referenced.setdefault(literal, [])
            if facts.node.path not in bucket:
                bucket.append(facts.node.path)

    attachments = tuple(
        Attachment(
            path=facts.node.path,
            disposition=facts.disposition,
            filename=facts.filename,
            name=facts.name,
            content_id=facts.content_id,
            referenced_by=tuple(referenced.get(facts.content_id or "", ())),
        )
        for facts in facts_by_node
        if _is_leaf(facts.node)
    )

    ordered = tuple(sorted(defects, key=lambda item: item.sort_key))
    return AttributionResult(attachments=attachments, defects=ordered)

"""头编码审计：RFC 2047（encoded-word）与 RFC 2231（参数续行）（模块 M2 / 里程碑 M3）。

**判定顺序写死（`data/README` §7.5 第 1–3 条）**：

1. 头块切分 → 头行 > 998（MC-H07）**先于** encoded-word 检查；
2. 先判 "encoded-word 跨行"（MC-H12，`diff`）；命中则**不再**报 MC-H03（内空白），
   被压掉的那条进 ``related`` —— 同一字节不得双记；
3. RFC 2231：先合并续行并判编号（MC-H09）→ 再判 ``charset'language'value`` 的单引号
   （MC-H10）→ 再判 ``%HH``（MC-H11）。**同一参数按此顺序只记第一条**：前缀形态坏了，
   后面的判定就没有意义（否则一个坏参数会同时出三条账，定位精度反而下降）。

**编码长度按字节计**（`plan/01` M2 纪律）：encoded-word 本身必须是 ASCII，
故拿编码后的字节数比 75 / 76 是保守且可复算的口径，不去猜 charset。

**分层**：本模块位于 `scan` 之下（`plan/02` §一 的依赖图），因此**不得** import
`scan`。行切分因此有一份语义等价的本地实现（K7），二者的一致性由
``tests/test_golden_engine_headers.py::test_line_splitter_matches_scan`` 交叉断言 ——
不是"各写一套然后互相不知道"。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass, field

from . import constants as C
from .model import Defect, Header, Node

# ── RFC 原文的数值上限（R1 / R2 / R5，见 `data/README` §三）────────────────
MAX_ENCODED_WORD = 75        # MC-H01：encoded-word ≤ 75 字符
MAX_ENCODED_WORD_LINE = 76   # MC-H02：含 encoded-word 的头行 ≤ 76 字符
MAX_HEADER_LINE_OCTETS = 998  # MC-H07：头行 ≤ 998 octets（不含 CRLF）

#: MC-H 系列的静态形态（``class`` / ``severity`` / ``rfc``）—— 引擎侧的唯一定义点。
#: 与 ``mimeconform/rules/catalog.json`` **逐值一致**
#: （``tests/test_catalog_consistency.py`` 断言；``plan/03`` §九）。
_RULE_META: dict[str, tuple[str, str, str]] = {
    "MC-H01": (C.CLASS_HARD, C.SEV_MINOR, "RFC 2047 §2"),
    "MC-H02": (C.CLASS_HARD, C.SEV_MINOR, "RFC 2047 §2"),
    "MC-H03": (C.CLASS_HARD, C.SEV_MINOR, "RFC 2047 §2"),
    "MC-H04": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2047 §4.1"),
    "MC-H05": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2047 §4.2"),
    "MC-H06": (C.CLASS_HARD, C.SEV_MAJOR, "RFC 2047 §5"),
    "MC-H07": (C.CLASS_HARD, C.SEV_MAJOR, "RFC 5322 §2.1.1"),
    "MC-H08": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-H09": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2231 §3"),
    "MC-H10": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2231 §4"),
    "MC-H11": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2231 §4.1"),
    "MC-H12": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
}

#: RFC 2231 的参数只出现在 "可带参数的头" 上；正文里 `; a=b` 这种形态不是参数，
#: 对它做 2231 判定会把普通文本误报成参数缺陷（假阳风险，见 docs/defect-catalog.md）。
_PARAM_HEADERS = frozenset({"content-type", "content-disposition"})

#: encoded-word 形态（RFC 2047 §2）：``=?charset?encoding?encoded-text?=``。
#: ``charset`` 取 `[!-~]+`（不含 `?`），``encoded-text`` 不含 `?` —— 故这条正则**不会**
#: 跨越两个相邻 encoded-word 合并匹配。``[^?]`` 天然跨行，MC-H12 靠这一点可见。
_EW_PATTERN = re.compile(rb"=\?([!-~]+?)\?([QqBb])\?([^?]*)\?=")

#: 同一套形态的文本版（`decode_filename` 在 ``str`` 上做 RFC 2047 解码）。
_EW_TEXT_PATTERN = re.compile(r"=\?([!-~]+?)\?([QqBb])\?([^?]*)\?=")

#: RFC 2231 参数名：``name`` / ``name*`` / ``name*0`` / ``name*0*``。
_EXT_NAME = re.compile(r"^(?P<stem>[^*]+)\*(?P<num>\d*)(?P<ext>\*?)$")

_HEX_BYTES = frozenset(b"0123456789abcdefABCDEF")
_LWSP = (b" ", b"\t")


@dataclass(frozen=True, slots=True)
class HeaderBlock:
    """一个头块的解析产物：头字段事实 + 头级缺陷 + 头块结束的绝对偏移。"""

    headers: tuple[Header, ...] = field(default=())
    defects: tuple[Defect, ...] = field(default=())
    end_offset: int = 0


@dataclass(frozen=True, slots=True)
class _Line:
    number: int      # 头块内行号（从 1 起，`data/README` §7.10 的 offset_kind="line"）
    start: int       # 本地偏移（头块内）
    content: bytes   # 去掉行尾 CRLF / LF 后的内容


@dataclass(frozen=True, slots=True)
class _Entry:
    """一个逻辑头（含折行）。``value_*`` 是**本地**偏移，行范围也是本地的。"""

    name: str
    value_start: int
    value_end: int
    line_ranges: tuple[tuple[int, int, int], ...]   # (行号, 内容起, 内容止)


@dataclass(frozen=True, slots=True)
class _Param:
    """一个 ``name=value`` 参数的字节级事实（不做字符集解码）。"""

    name: str          # 小写，原样（保留 `*` 与数字）
    value: bytes       # 引号已剥离、反斜杠已还原的**内容**字节
    name_offset: int   # 参数名在文件中的绝对偏移
    value_offset: int  # 内容首字节的绝对偏移；无值时 -1


# ── 行切分（K7：与 `scan.split_lines` 同语义，但不得反向 import）──────────


def _iter_lines(block: bytes) -> list[_Line]:
    """按 ``\\n`` 切行（不吞 ``\\r``、不把 ``\\x0b`` 当行界、保留原始偏移）。

    与 ``scan.split_lines`` 的语义一致；差异由交叉断言测试兜住（模块 docstring）。
    """
    lines: list[_Line] = []
    pos = 0
    stop = len(block)
    number = 1
    while pos < stop:
        newline = block.find(b"\n", pos)
        if newline < 0:
            raw = block[pos:stop]
            pos = stop
        else:
            raw = block[pos : newline + 1]
            pos = newline + 1
        content = raw[:-1] if raw.endswith(b"\n") else raw
        if content.endswith(b"\r"):
            content = content[:-1]
        lines.append(_Line(number=number, start=pos - len(raw), content=content))
        number += 1
    return lines


def _is_field_name(name: bytes) -> bool:
    """RFC 5322 §2.2：字段名是可见 ASCII（排除 ``:`` 与空白）。"""
    if not name:
        return False
    return all(33 <= byte <= 126 and byte != 58 for byte in name)


# ── 头块切分 ──────────────────────────────────────────────────────────────


def _scan_entries(block: bytes) -> tuple[list[_Entry], list[_Line]]:
    """把头块切成逻辑头；返回 ``(头列表, 已消费的物理行)``。

    终止条件与 `scan._parse_header_block` 一致：空行 / 字段名非法 / 无主的续行 →
    该行起不再是头块的一部分（不在本函数里猜正文）。
    """
    entries: list[_Entry] = []
    consumed: list[_Line] = []
    pending: dict[str, object] | None = None

    def close() -> None:
        nonlocal pending
        if pending is None:
            return
        entries.append(
            _Entry(
                name=str(pending["name"]),
                value_start=int(pending["value_start"]),
                value_end=int(pending["value_end"]),
                line_ranges=tuple(pending["line_ranges"]),  # type: ignore[arg-type]
            )
        )
        pending = None

    for line in _iter_lines(block):
        content = line.content
        line_end = line.start + len(content)
        if content == b"":
            break
        if content[:1] in _LWSP:
            if pending is None:
                break
            pending["value_end"] = line_end
            ranges = pending["line_ranges"]
            assert isinstance(ranges, list)
            ranges.append((line.number, line.start, line_end))
            consumed.append(line)
            continue
        colon = content.find(b":")
        if colon <= 0 or not _is_field_name(content[:colon]):
            break
        close()
        pending = {
            "name": content[:colon].decode("ascii", "replace"),
            "value_start": line.start + colon + 1,
            "value_end": line_end,
            "line_ranges": [(line.number, line.start, line_end)],
        }
        consumed.append(line)
    close()
    return entries, consumed


def _params_of(value: bytes, base: int) -> list[_Param]:
    """切分 ``; name=value`` 参数（字节级；不判合法性、不做字符集解码）。"""
    params: list[_Param] = []
    index = 0
    stop = len(value)
    while index < stop:
        if value[index : index + 1] != b";":
            index += 1
            continue
        index = _skip_ws(value, index + 1)
        name_start = index
        while index < stop and value[index : index + 1] not in (b"=", b";", b" ", b"\t", b"\r", b"\n"):
            index += 1
        name = value[name_start:index].decode("ascii", "replace").lower()
        if not name:
            continue
        if index < stop and value[index : index + 1] == b"=":
            index = _skip_ws(value, index + 1)
            if value[index : index + 1] == b'"':
                index += 1
                content_start = index
                buf = bytearray()
                while index < stop:
                    char = value[index : index + 1]
                    if char == b"\\" and index + 1 < stop:
                        buf += value[index + 1 : index + 2]
                        index += 2
                        continue
                    if char == b'"':
                        break
                    buf += char
                    index += 1
                params.append(_Param(name, bytes(buf), base + name_start, base + content_start))
                if index < stop:  # 跳过闭引号
                    index += 1
            else:
                content_start = index
                while index < stop and value[index : index + 1] not in (b";", b" ", b"\t", b"\r", b"\n"):
                    index += 1
                params.append(_Param(name, value[content_start:index], base + name_start, base + content_start))
        else:
            params.append(_Param(name, b"", base + name_start, -1))
    return params


def _skip_ws(value: bytes, index: int) -> int:
    stop = len(value)
    while index < stop and value[index : index + 1] in (b" ", b"\t", b"\r", b"\n"):
        index += 1
    return index


# ── 缺陷构造 ──────────────────────────────────────────────────────────────


def _defect(
    rule_id: str,
    path: str,
    offset: int,
    detail: str,
    *,
    offset_kind: str = C.OFFSET_ABSOLUTE,
    related: tuple[str, ...] = (),
) -> Defect:
    klass, severity, rfc = _RULE_META[rule_id]
    defect = Defect(
        rule_id=rule_id,
        klass=klass,
        severity=severity,
        path=path,
        offset=offset,
        offset_kind=offset_kind,
        rfc=rfc,
        detail=detail,
        related=related,
    )
    defect.validate()
    return defect


# ── RFC 2047 语法判定 ────────────────────────────────────────────────────


def _q_escape_problem(text: bytes) -> bytes | None:
    """Q 编码里第一处非法转义（``=`` 后不是两位十六进制）；没有则 ``None``。

    ``_``（0x5F）表示空格，是合法字符，不在这里判。
    """
    index = 0
    stop = len(text)
    while index < stop:
        if text[index] == 0x3D:  # '='
            if index + 2 >= stop or text[index + 1] not in _HEX_BYTES or text[index + 2] not in _HEX_BYTES:
                return text[index : index + 3]
            index += 3
            continue
        index += 1
    return None


def _decode_q(text: bytes) -> bytes:
    """Q 解码：``_`` → 空格，``=HH`` → 字节，其余原样（非法转义不吞字符）。"""
    out = bytearray()
    index = 0
    stop = len(text)
    while index < stop:
        char = text[index]
        if char == 0x5F:
            out.append(0x20)
            index += 1
            continue
        if char == 0x3D and index + 2 < stop and text[index + 1] in _HEX_BYTES and text[index + 2] in _HEX_BYTES:
            out.append(int(text[index + 1 : index + 3], 16))
            index += 3
            continue
        out.append(char)
        index += 1
    return bytes(out)


def _decode_b(text: bytes) -> bytes | None:
    """B 解码（RFC 2045 base64，字母表外字符按 RFC 忽略）；非法则 ``None``。"""
    cleaned = bytes(char for char in text if char not in b" \t\r\n")
    try:
        return base64.b64decode(cleaned, validate=False)
    except (binascii.Error, ValueError):
        return None


def _decode_bytes(payload: bytes, charset: str | None) -> str:
    """按 charset 解码；未知名 / 解码失败一律回落 UTF-8（``replace``），从不抛。"""
    candidates = [charset] if charset else []
    candidates.append("utf-8")
    for name in candidates:
        assert name is not None
        try:
            return payload.decode(name)
        except (LookupError, UnicodeDecodeError, ValueError):
            continue
    return payload.decode("utf-8", "replace")


# ── 单个逻辑头的判定 ──────────────────────────────────────────────────────


def _entry_defects(entry: _Entry, block: bytes, base: int, path: str) -> list[Defect]:
    out: list[Defect] = []
    value = block[entry.value_start : entry.value_end]
    tokens = list(_EW_PATTERN.finditer(value))

    for match in tokens:
        token = match.group(0)
        token_start = base + entry.value_start + match.start()
        charset = match.group(1).decode("ascii", "replace")
        encoding = match.group(2).decode("ascii")
        text = match.group(3)

        # §7.5 第 2 条：先判折行（MC-H12），命中则 H03 只进 related。
        folded = b"\n" in text or b"\r" in text
        if len(token) > MAX_ENCODED_WORD:
            out.append(
                _defect(
                    "MC-H01",
                    path,
                    token_start,
                    f"encoded-word 长度 {len(token)} > {MAX_ENCODED_WORD}（按编码后 ASCII 字节计）",
                )
            )
        if folded:
            out.append(
                _defect(
                    "MC-H12",
                    path,
                    token_start,
                    "encoded-word 跨折行：encoded-text 被 FWS 折在一个 encoded-word 内"
                    "（先折叠还是先解码，RFC 未定）",
                    related=("MC-H03",),
                )
            )
        elif any(char in text for char in (b" ", b"\t")):
            out.append(
                _defect(
                    "MC-H03",
                    path,
                    token_start,
                    "encoded-word 内部出现空白（形态定义排除 LWSP；本 token 无折行，不与 MC-H12 互斥）",
                )
            )

        # 折行时 encoded-text 的连续性归 MC-H12；再判 Q/B 语法会把同一字节双记。
        if not folded and encoding in "Qq":
            bad = _q_escape_problem(text)
            if bad is not None:
                out.append(
                    _defect(
                        "MC-H04",
                        path,
                        token_start,
                        f"Q 编码里 `{bad.decode('ascii', 'replace')}` 不是合法的 =HH 转义"
                        "（R4 §4.1 子项原句未录 → 门禁降级，只登记）",
                    )
                )
        elif not folded and len(text) % 4 != 0:
            out.append(
                _defect(
                    "MC-H05",
                    path,
                    token_start,
                    f"B 编码 base64 长度 {len(text)} 不是 4 的倍数"
                    "（R4 §4.2 子项原句未录 → 门禁降级，只登记）",
                )
            )

    out.extend(_continuation_defects(tokens, entry, value, base, path))
    out.extend(_line_width_defects(tokens, entry, path))
    out.extend(_unencoded_8bit_defects(tokens, entry, value, base, path))
    if entry.name.lower() in _PARAM_HEADERS:
        out.extend(_param_defects(entry, value, base, path))
    return out


def _continuation_defects(
    tokens: list[re.Match[bytes]],
    entry: _Entry,
    value: bytes,
    base: int,
    path: str,
) -> list[Defect]:
    """MC-H06：encoded-text 跨 encoded-word 续写（R4 §5 全录 → 可以 `hard`）。

    判定要**保守**，只认"前一段自身不完整、与后一段拼接后才完整"这一种形态：

    * 同 charset、同 encoding，两者之间只有 FWS；
    * Q：前一段末尾是一个**被切断的转义**（以 `=` 或 `=H` 结尾），拼接后整段合法；
    * B：前一段长度不是 4 的倍数，拼接后是 4 的倍数。

    为什么要这么写：两个各自完整的 encoded-word 之间只有 FWS 是**合法形态**
    （`h-clean-folded` 是它的负例基线）。若按"相邻即续写"判，会把合法折叠全部误报。
    """
    for first, second in zip(tokens, tokens[1:]):
        between = value[first.end() : second.start()]
        if between.strip(b" \t\r\n") != b"":
            continue
        if first.group(1).lower() != second.group(1).lower() or first.group(2) != second.group(2):
            continue
        head, tail = first.group(3), second.group(3)
        if first.group(2) in b"Qq":
            incomplete = _q_escape_problem(head) is not None and _q_escape_problem(head + tail) is None
        else:
            incomplete = len(head) % 4 != 0 and (len(head) + len(tail)) % 4 == 0 and _decode_b(head + tail) is not None
        if not incomplete:
            continue
        return [
            _defect(
                "MC-H06",
                path,
                base + entry.value_start + first.start(),
                "encoded-text 从一个 encoded-word 续写到下一个"
                "（RFC 2047 §5：MUST NOT；前一段自身不完整、与后一段拼接后才完整）",
            )
        ]
    return []


def _line_width_defects(
    tokens: list[re.Match[bytes]],
    entry: _Entry,
    path: str,
) -> list[Defect]:
    """MC-H02：含 encoded-word 的头行 > 76 字符（R2 全录）。

    行宽按**物理行**、不含 CRLF。只对"行内含 encoded-word 起点"的行判 ——
    没有 encoded-word 的长行不属本规则（那是 MC-H07 / 其它簇的事）。
    """
    starts = [entry.value_start + match.start() for match in tokens]
    out: list[Defect] = []
    for number, line_start, line_end in entry.line_ranges:
        width = line_end - line_start
        if width <= MAX_ENCODED_WORD_LINE:
            continue
        if not any(line_start <= start < line_end for start in starts):
            continue
        out.append(
            _defect(
                "MC-H02",
                path,
                number,
                f"含 encoded-word 的头行 {width} > {MAX_ENCODED_WORD_LINE} 字符",
                offset_kind=C.OFFSET_LINE,
            )
        )
    return out


def _unencoded_8bit_defects(
    tokens: list[re.Match[bytes]],
    entry: _Entry,
    value: bytes,
    base: int,
    path: str,
) -> list[Defect]:
    """MC-H08：头值里的未编码非 ASCII 字节（`diff`，`none-by-design`）。

    encoded-word 本身是 ASCII；落在 token 跨度内的八位组理论上不存在，
    但仍按跨度排除，避免把"token 里混进 8bit"的畸形样本记成 H08。
    """
    spans = [(match.start(), match.end()) for match in tokens]
    for index, char in enumerate(value):
        if char < 0x80:
            continue
        if any(start <= index < end for start, end in spans):
            continue
        return [
            _defect(
                "MC-H08",
                path,
                base + entry.value_start + index,
                f"{entry.name} 头值含未编码的非 ASCII 字节"
                "（RFC 2047 是编码机制，不是禁令；现实实现常直传 8bit）",
            )
        ]
    return []


# ── RFC 2231 参数判定 ────────────────────────────────────────────────────


def _classify(name: str) -> tuple[str, int | None, str, bool] | None:
    """``filename*0*`` → ``("filename", 0, "0", True)``；``filename*`` → ``("filename", None, "", True)``。

    四个分量依次是 ``(stem, 编号, 编号原文, 是否扩展形态)`` —— **保留编号原文**是因为
    ``"00"`` 与 ``"0"`` 的 ``int`` 相同，前导零只能靠原文判（R10 §3 的子项之一）。

    非扩展形态（``filename``）返回 ``None`` —— 它不参与 2231 编号判定。
    """
    match = _EXT_NAME.match(name)
    if not match:
        return None
    digits = match.group("num")
    number = int(digits) if digits else None
    extended = bool(match.group("ext")) or number is None
    return match.group("stem"), number, digits, extended


def _percent_problem(body: bytes) -> int | None:
    """第一处非法 ``%HH`` 的**相对位移**；没有则 ``None``。"""
    index = 0
    stop = len(body)
    while index < stop:
        if body[index] == 0x25:  # '%'
            if index + 2 >= stop or body[index + 1] not in _HEX_BYTES or body[index + 2] not in _HEX_BYTES:
                return index
            index += 3
            continue
        index += 1
    return None


def _param_defects(entry: _Entry, value: bytes, base: int, path: str) -> list[Defect]:
    """RFC 2231 参数的三阶段判定（§7.5 第 3 条）：编号 → 单引号 → ``%HH``。

    **同一参数只记第一条**：前缀形态坏了，后面的判定就没有意义（一个坏参数出三条账会
    稀释定位精度）。编号的连续性按**出现顺序**推进（``expected``），因此跳号 / 重号
    在"第一个不按序的参数"上落点，而不是事后再扫一遍。
    """
    out: list[Defect] = []
    params = _params_of(value, base + entry.value_start)
    expected: dict[str, int] = {}

    for param in params:
        info = _classify(param.name)
        if info is None:
            continue
        stem, number, digits, extended = info

        # 阶段 1：续行编号（MC-H09）
        if number is None:
            out.append(
                _defect(
                    "MC-H09",
                    path,
                    param.name_offset,
                    f"RFC 2231 参数缺 `*0` 序号：`{param.name}=` 应写成 `{stem}*0*=`"
                    "（修正提示是文本，不自动改文件）",
                )
            )
            continue
        if len(digits) > 1 and digits.startswith("0"):
            out.append(
                _defect(
                    "MC-H09",
                    path,
                    param.name_offset,
                    f"RFC 2231 参数续行编号带前导零：`{param.name}`（应为 `{stem}*{number}`）",
                )
            )
            continue
        want = expected.get(stem, 0)
        if number != want:
            out.append(
                _defect(
                    "MC-H09",
                    path,
                    param.name_offset,
                    f"RFC 2231 续行编号跳号/重号：`{stem}*{number}` 出现在应为 `{stem}*{want}` 的位置"
                    "（编号必须从 0 起连续、不重复）",
                )
            )
            continue
        expected[stem] = want + 1

        # 阶段 2：`charset'language'value` 的单引号（MC-H10）
        if not extended:
            continue
        if param.value.count(b"'") < 2:
            out.append(
                _defect(
                    "MC-H10",
                    path,
                    param.name_offset,
                    "`charset'language'value` 的单引号不完整"
                    f"（`{param.value.decode('latin-1')}`；应为 `charset''value`）",
                )
            )
            continue

        # 阶段 3：`%HH` 转义（MC-H11）
        body_start = param.value.find(b"'", param.value.find(b"'") + 1) + 1
        bad = _percent_problem(param.value[body_start:])
        if bad is not None:
            raw = param.value[body_start + bad : body_start + bad + 3].decode("latin-1")
            out.append(
                _defect(
                    "MC-H11",
                    path,
                    param.value_offset + body_start + bad,
                    f"`{raw}` 不是合法的 %HH 转义（H 必须是两位十六进制）",
                )
            )
    return out


# ── 头字段事实 ────────────────────────────────────────────────────────────


def _build_header(entry: _Entry, block: bytes, base: int) -> Header:
    value = block[entry.value_start : entry.value_end]
    words: list[dict[str, object]] = []
    for match in _EW_PATTERN.finditer(value):
        words.append(
            {
                "token_start": base + entry.value_start + match.start(),
                "token_end": base + entry.value_start + match.end(),
                "charset": match.group(1).decode("ascii", "replace"),
                "encoding": match.group(2).decode("ascii"),
                "text": match.group(3).decode("ascii", "replace"),
                "length": match.end() - match.start(),
            }
        )
    params: list[dict[str, object]] = []
    if entry.name.lower() in _PARAM_HEADERS:
        for param in _params_of(value, base + entry.value_start):
            info = _classify(param.name)
            extended = bool(info and info[3])
            charset: str | None = None
            language: str | None = None
            if extended and param.value.count(b"'") >= 2:
                first = param.value.find(b"'")
                second = param.value.find(b"'", first + 1)
                charset = param.value[:first].decode("ascii", "replace") or None
                language = param.value[first + 1 : second].decode("ascii", "replace") or None
            params.append(
                {
                    "name": param.name,
                    "value": param.value.decode("latin-1"),
                    "extended": extended,
                    "segments": [info[1]] if info and info[1] is not None else [],
                    "charset": charset,
                    "language": language,
                }
            )
    return Header(
        name=entry.name,
        raw_value_sha256=hashlib.sha256(value).hexdigest(),
        octets=len(value),
        line_spans=tuple((base + start, base + end) for _number, start, end in entry.line_ranges),
        encoded_words=tuple(words),
        params=tuple(params),
    )


# ── 入口 ──────────────────────────────────────────────────────────────────


def parse_headers(raw_header_block: bytes, base_offset: int = 0, *, path: str = "0") -> HeaderBlock:
    """解析原始头块字节（未解码、未展开），产出头级缺陷与头字段事实。

    ``base_offset`` 是 ``raw_header_block[0]`` 在文件里的绝对偏移；缺陷的
    ``offset_kind="absolute"`` 一律换算成**文件绝对偏移**，而 ``offset_kind="line"``
    是**头块内行号**（从 1 起，`data/README` §7.10）。

    判定顺序（§7.5 第 1–3 条）：头行 > 998 → encoded-word 跨行 / 内空白 → 2231 三阶段。
    """
    if isinstance(raw_header_block, bytearray):
        raw_header_block = bytes(raw_header_block)
    if not isinstance(raw_header_block, bytes):
        raise TypeError(f"raw_header_block 必须是 bytes（收到 {type(raw_header_block).__name__}）")
    if base_offset < 0:
        raise ValueError(f"base_offset 不得为负: {base_offset}")

    entries, consumed = _scan_entries(raw_header_block)
    defects: list[Defect] = []

    # §7.5 第 1 条：头行 > 998 先于 encoded-word 检查（同一行的行宽账与 token 账各自成立）。
    for line in consumed:
        if len(line.content) > MAX_HEADER_LINE_OCTETS:
            defects.append(
                _defect(
                    "MC-H07",
                    path,
                    line.number,
                    f"头行 {len(line.content)} > {MAX_HEADER_LINE_OCTETS} octets（不含 CRLF）",
                    offset_kind=C.OFFSET_LINE,
                )
            )

    for entry in entries:
        defects.extend(_entry_defects(entry, raw_header_block, base_offset, path))

    end_local = consumed[-1].start + len(consumed[-1].content) if consumed else 0
    return HeaderBlock(
        headers=tuple(_build_header(entry, raw_header_block, base_offset) for entry in entries),
        defects=tuple(sorted(defects, key=lambda item: item.sort_key)),
        end_offset=base_offset + end_local,
    )


def _iter_nodes(node: Node):
    yield node
    for child in node.children:
        yield from _iter_nodes(child)


def audit_headers(root: Node, data: bytes) -> tuple[Defect, ...]:
    """遍历整棵树，对每个节点的头块跑 :func:`parse_headers`，缺陷打该节点的 ``path``。

    为什么从这里回头取字节（`plan/03` §二 的落法 ①）：``scan`` 只做头块**定位**
    （名字 / 值字节 / 行跨度 / 偏移），把 ``line_spans`` 交出来；语法审计在 `headers`
    这一层独立做，``scan`` 的契约因此不必知道 2047 / 2231。
    """
    defects: list[Defect] = []
    for node in _iter_nodes(root):
        if not node.headers:
            continue
        start = node.headers[0].line_spans[0][0]
        end = node.headers[-1].line_spans[-1][1]
        if not (0 <= start <= end <= len(data)):
            raise ValueError(f"节点 {node.path} 的头块跨度越界: [{start}, {end})")
        block = parse_headers(data[start:end], start, path=node.path)
        defects.extend(block.defects)
    return tuple(sorted(defects, key=lambda item: item.sort_key))


# ── filename 取值（D10：先 2231，再 2047）─────────────────────────────────


def _as_bytes(value: object) -> bytes:
    """把参数值还原成字节：先按 latin-1（`parse_headers` 的字节视图），再按 UTF-8。"""
    text = str(value)
    try:
        return text.encode("latin-1")
    except UnicodeEncodeError:
        return text.encode("utf-8", "replace")


def _split_extended(payload: bytes) -> tuple[str | None, bytes]:
    """``charset'language'value`` → ``(charset, value)``；单引号不全时按"无前缀"处理。

    单引号缺失由 MC-H10 记账；取值层不因此丢值（丢了就是静默改数据）。
    """
    first = payload.find(b"'")
    if first < 0:
        return None, payload
    second = payload.find(b"'", first + 1)
    if second < 0:
        return None, payload
    charset = payload[:first].decode("ascii", "replace") or None
    return charset, payload[second + 1 :]


def _unquote_percent(body: bytes) -> bytes:
    """``%HH`` 反转义；非法转义按字面保留（MC-H11 记账，取值层不吞字节）。"""
    out = bytearray()
    index = 0
    stop = len(body)
    while index < stop:
        if body[index] == 0x25 and index + 2 < stop and body[index + 1] in _HEX_BYTES and body[index + 2] in _HEX_BYTES:
            out.append(int(body[index + 1 : index + 3], 16))
            index += 3
            continue
        out.append(body[index])
        index += 1
    return bytes(out)


def _merge_filename_params(params: list[dict[str, object]]) -> tuple[str | None, bytes] | None:
    """按 RFC 2231 合并 ``filename`` 系列参数；没有扩展形态则 ``None``。

    顺序（§7.5 第 3 条）：先合并续行 → 再解析 ``charset'language'value`` → 再 ``%HH``。
    **编号不连续即显式失败**（不静默拼接出一段"看起来对"的文件名）。
    """
    plain: bytes | None = None
    single: bytes | None = None
    segments: dict[int, tuple[bool, bytes]] = {}

    for param in params:
        name = str(param.get("name") or "").lower()
        if not name:
            continue
        info = _classify(name)
        stem = info[0] if info else name
        if stem != "filename":
            continue
        payload = _as_bytes(param.get("value", ""))
        if info is None:
            plain = payload
            continue
        _stem, number, _digits, extended = info
        if number is None:
            if extended:
                single = payload
            continue
        segments[number] = (extended, payload)

    if segments:
        numbers = sorted(segments)
        if numbers != list(range(len(numbers))):
            raise ValueError(
                f"RFC 2231 参数续行编号不连续（filename 实际为 {numbers}，应 0..{len(numbers) - 1}）："
                "不静默拼接（MC-H09）"
            )
        charset: str | None = None
        pieces: list[bytes] = []
        for index in numbers:
            extended, payload = segments[index]
            if not extended:
                pieces.append(payload)
                continue
            if index == 0:
                charset, body = _split_extended(payload)
            else:
                body = payload
            pieces.append(_unquote_percent(body))
        return charset, b"".join(pieces)
    if single is not None:
        charset, body = _split_extended(single)
        return charset, _unquote_percent(body)
    if plain is not None:
        return None, plain
    return None


def _decode_encoded_words(text: str) -> str:
    """把文本里的 RFC 2047 encoded-word 解出来；相邻 encoded-word 之间的 LWSP 丢弃。

    §6.2 的"相邻 encoded-word 间的 LWSP 显示时忽略"在这里落地：``a?= =?b`` 拼成 ``ab``，
    而不是 ``a b``。不可解的 token **原样保留**（不吞、不猜）。
    """
    pieces: list[str] = []
    position = 0
    previous_end = -1
    for match in _EW_TEXT_PATTERN.finditer(text):
        gap = text[position : match.start()]
        decoded = _decode_word(match)
        if decoded is None:
            pieces.append(gap)
            pieces.append(match.group(0))
            position = match.end()
            previous_end = -1
            continue
        adjacent = previous_end == position and gap.strip() == ""
        if not adjacent:
            pieces.append(gap)
        pieces.append(decoded)
        position = match.end()
        previous_end = match.end()
    pieces.append(text[position:])
    return "".join(pieces)


def _decode_word(match: re.Match[str]) -> str | None:
    charset = match.group(1)
    encoding = match.group(2)
    text = match.group(3).encode("latin-1", "replace")
    if encoding in "Qq":
        payload = _decode_q(text)
    else:
        payload = _decode_b(text)
        if payload is None:
            return None
    return _decode_bytes(payload, charset)


def _decode_plain(payload: bytes) -> str:
    """非扩展形态（普通 ``filename=``）的字符集：UTF-8 → latin-1 → 替换。

    RFC 2045 只保证 ASCII；现实里 8bit 直传多为 UTF-8（少数是 latin-1）。
    latin-1 兜底是**无损**的（256 个码位一一对应），因此"解不出来"比"猜错"更少见。
    """
    for name in ("utf-8", "latin-1"):
        try:
            return payload.decode(name)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", "replace")


def decode_filename(params: list[dict[str, object]], raw_value: str) -> str:
    """按 §7.5 第 3–4 条取 ``filename``：先 RFC 2231（含续行）→ 再 RFC 2047。

    顺序**不可交换**（`plan/00` D10）：两层叠加时顺序不同会得出不同文件名，
    golden 就无法逐字节验收。调用点是 M5 的 attribution；本棒只保证可被单测。

    * 参数里有 ``filename`` 系列 → 用它（2231 解码后再走 2047）；
    * 参数里没有 → 退回 ``raw_value``（普通取值）做 2047 解码；
    * 2231 编号不连续 → :class:`ValueError`（显式失败，不静默拼接）；
    * 单引号缺失 → 按"无 charset 前缀"处理（值照用，缺陷由 MC-H10 记账）。

    **为什么参数优先于 ``raw_value``**：``raw_value`` 是整条头的原始值（`attachment; …`），
    拿它当文件名只会得到一段协议文本；参数才是文件名的定义处。
    """
    merged = _merge_filename_params(params)
    if merged is None:
        return _decode_encoded_words(raw_value)
    charset, payload = merged
    text = _decode_bytes(payload, charset) if charset else _decode_plain(payload)
    return _decode_encoded_words(text)

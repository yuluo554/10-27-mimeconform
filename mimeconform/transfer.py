"""传输编码审计：自写 base64 / QP 观察与解码（模块 M3 / 里程碑 M4）。

**为什么自写**（plan/03 §三）：需要 ``foreign_chars`` 计数与"非法填充/非法 ``=HH`` 的字节偏移"；
标准库解码器把这些信息丢掉或直接抛异常。``base64`` 只在测试端做交叉校验。

**纪律**（`plan/03` §三 / `data/README` §7.5）：

* 行宽按 **octets**（不含 CRLF/LF）；
* base64 字母表外字符**按 RFC 2045 §6.8 忽略**并计数（"出现"本身不是违规，MC-T04 只出 note）；
* QP 非法 ``=HH`` **原样保留该字节**（不吞字符）—— SO 79133579 的 ``=ustomers`` 正是被吞的结果。

**判定顺序写死（`data/README` §7.5 第 5 条）**：

1. **先判声明值是否已知**（MC-T08）：声明值不在 {7bit, 8bit, binary, quoted-printable, base64}
   之列 → 只出 MC-T08，**不再做交叉校验**（CTE 未知时无法判 declared vs observed）；
2. **再判声明形态**：声明 base64 → 其填充（MC-T02）/ 长度（MC-T03）/ 字母表外字符（MC-T04）；
   声明 quoted-printable → 行宽（MC-T05）、软换行接续（MC-T06）、非法转义（MC-T07）、
   二次编码残留（MC-T11）；
3. **最后才判 declared vs observed**（MC-T01）：`observed_shape` 与声明不符 → `diff`。

**压账（同一段字节不双记，`data/README` §7.5 / `data/golden/t-cte-mismatch`）**：

* 声明 base64 而**实测完全不是 base64 形态**时，只出 MC-T01，**不逐条登记** MC-T02/T03/T04
  （否则一段明文会出几十条 note 账）；
* QP 行宽（MC-T05）**只在合法 encoded line 上判**：某行含非法转义（MC-T07）时，该行不再记行宽
  （非法转义使该行已不是合法 encoded line —— R8 的 76 上限只约束 encoded line）；
* QP 软换行（行末 `=`）**不计入下一行**，其宽度按本行计。

**分层**：本模块位于 `scan` 之上（`plan/02` §一），因此**不得** import `scan`。行切分因此有一份
语义等价的本地实现（K7），与 `scan.split_lines()` 的一致性由
``tests/test_golden_engine_transfer.py::test_line_splitter_matches_scan`` 交叉断言。

**`offset_kind` 一律 `absolute`**：T 簇全部落文件级字节偏移（MC-T08 落在 CTE 头行的行首）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from . import constants as C
from .model import Defect, Node

# ── 数值上限（R8 / R9 / R11，见 `data/README` §三）────────────────────────
MAX_QP_LINE_OCTETS = 76        # MC-T05：QP 编码行 ≤ 76（不含 CRLF）
MAX_7BIT_LINE_OCTETS = 998     # MC-T09：7bit/8bit 行 ≤ 998 octets

#: RFC 2045 §6.8 的 base64 字母表（把 ``bytes`` 转成 ``int`` 集合，便于逐字节判定）。
_BASE64_ALPHABET = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
_HEX = frozenset(b"0123456789abcdefABCDEF")
_EOL_BYTES = frozenset(b"\r\n")
#: 逐字节扫描时按"线性空白/行尾"忽略的字节（RFC 2045 §6.8：字母表外字符忽略）。
_IGNORABLE = frozenset(b"\r\n \t")
_CR = 0x0D
_LF = 0x0A
_EQUAL = 0x3D

#: 已知的 CTE 取值（RFC 2045 §6.1/§2.7/§2.8/§6.7/§6.8：7bit / 8bit / binary / quoted-printable / base64）。
#: 之外一律 MC-T08（**不**自动承认任何"扩展 token"—— `x-mystery-enc` 也是未知）。
KNOWN_CTE = frozenset({"7bit", "8bit", "binary", "quoted-printable", "base64"})

#: MC-T 系列的静态形态（``class`` / ``severity`` / ``rfc``）—— 引擎侧的唯一定义点。
#: 与 ``mimeconform/rules/catalog.json`` **逐值一致**
#: （``tests/test_catalog_consistency.py`` 断言；``plan/03`` §九）。
#:
#: ``hard`` 只给"有逐字原句的子项"：T04（R9 的字母表外字符子项全录）、T05/T06/T07（R8 全录）。
#: T01/T08/T11 是语义层（`none-by-design`）；T02/T03（R9 填充/长度子项未录）、
#: T09/T10（R11 整行未录）一律降级 `diff/note`。
_RULE_META: dict[str, tuple[str, str, str]] = {
    "MC-T01": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-T02": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2045 §6.8"),
    "MC-T03": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2045 §6.8"),
    "MC-T04": (C.CLASS_HARD, C.SEV_NOTE, "RFC 2045 §6.8"),
    "MC-T05": (C.CLASS_HARD, C.SEV_MINOR, "RFC 2045 §6.7"),
    "MC-T06": (C.CLASS_HARD, C.SEV_MINOR, "RFC 2045 §6.7"),
    "MC-T07": (C.CLASS_HARD, C.SEV_MAJOR, "RFC 2045 §6.7"),
    "MC-T08": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-T09": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2045 §2.7/§2.8/§6.1"),
    "MC-T10": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2045 §2.7/§2.8/§6.1"),
    "MC-T11": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
}

#: ``observed_shape`` 的中文名（只用于 detail 文案，不参与判定）。
_KIND_LABEL = {
    "text": "明文",
    "binary": "含 8bit 字节的二进制",
    "qp": "QP 编码文本",
    "base64": "base64",
    "empty": "空",
}


@dataclass(frozen=True, slots=True)
class Shape:
    """不依赖声明、按字节给出的实际形态。"""

    kind: str                       # text | base64 | qp | binary | empty
    line_max_octets: int = 0
    soft_breaks: int = 0
    foreign_chars: int = 0


@dataclass(frozen=True, slots=True)
class BodyFacts:
    declared_cte: str | None = None
    shape: Shape | None = None
    decoded_sha256: str | None = None
    defects: tuple[Defect, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class QpLine:
    """一个物理行（去掉行尾 CRLF / LF 后的内容 + 本地偏移）。"""

    number: int      # body 内行号（从 1 起）
    start: int       # 内容首字节的本地偏移
    content: bytes   # 去掉行尾后的内容
    end: int         # 内容末字节之后的本地偏移
    eol: bytes       # 原始行尾字节（b"\\r\\n" / b"\\n" / b""）


# ── 行切分（K7：与 `scan.split_lines` 同语义，但不得反向 import）──────────


def _iter_body_lines(body: bytes) -> list[QpLine]:
    """按 ``\\n`` 切行（不吞 ``\\r``、不把 ``\\x0b`` 当行界、保留原始偏移）。

    与 ``scan.split_lines`` 的语义一致；差异由交叉断言测试兜住（模块 docstring）。
    """
    lines: list[QpLine] = []
    pos = 0
    stop = len(body)
    number = 1
    while pos < stop:
        newline = body.find(b"\n", pos, stop)
        if newline < 0:
            raw = body[pos:stop]
            pos = stop
        else:
            raw = body[pos : newline + 1]
            pos = newline + 1
        content = raw[:-1] if raw.endswith(b"\n") else raw
        if content.endswith(b"\r"):
            content = content[:-1]
        start = pos - len(raw)
        lines.append(QpLine(number=number, start=start, content=content, end=start + len(content), eol=raw[len(content) :]))
        number += 1
    return lines


def qp_lines(body: bytes) -> tuple[QpLine, ...]:
    """QP 行级事实（行宽按 octets、不含 CRLF；软换行位置 = 行末 ``=``）。"""
    return tuple(_iter_body_lines(body))


# ── 形态观察（不依赖声明）────────────────────────────────────────────────


def observe_body_shape(body: bytes) -> Shape:
    """按字节判定实际形态（不做解码）。

    形态分类（**保守**，误报是本题最贵的失败）：

    * ``empty``：除空白与行尾外无内容；
    * ``binary``：含 >= 0x80 的八位组；
    * ``base64``：行内**无 SP/TAB** 且全 ASCII（字母表外字符按 RFC 2045 §6.8 视为可忽略，
      故仍算 base64 形态 —— MC-T04 正是要登记这些字符）；
    * ``qp``：行内有空白且正文含 ``=``（QP 的转义/软换行标记）；
    * ``text``：其余。

    **为什么用"行内空白"作分界**：base64 的编码行不含内部空格；一段英文正文
    （如 ``this body is plainly readable text``）每个词之间都有空格 ⇒ 判 ``text``
    而非 base64 —— 这正是 MC-T01 的判据（`data/golden/t-cte-mismatch`）。
    """
    lines = _iter_body_lines(body)
    line_max = max((len(line.content) for line in lines), default=0)
    soft_breaks = sum(1 for line in lines if line.content.endswith(b"="))
    foreign = sum(
        1 for byte in body if byte not in _BASE64_ALPHABET and byte not in _IGNORABLE and byte != _EQUAL
    )
    has_8bit = any(byte >= 0x80 for byte in body)
    stripped = body.strip(b" \t\r\n")

    if not stripped:
        kind = "empty"
    elif has_8bit:
        kind = "binary"
    elif not any(0x20 in line.content or 0x09 in line.content for line in lines):
        # 行内无空白 + 全 ASCII ⇒ base64 候选（字母表外字符按 §6.8 忽略，故不作排除）。
        kind = "base64"
    elif _EQUAL in body:
        kind = "qp"
    else:
        kind = "text"
    return Shape(kind=kind, line_max_octets=line_max, soft_breaks=soft_breaks, foreign_chars=foreign)


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


# ── base64：自写解码与形态事实 ───────────────────────────────────────────


def _base64_scan(body: bytes) -> dict[str, object]:
    """逐字节扫描 base64 正文，产出填充/长度/字母表外字符的事实（不做解码判定）。

    字母表外字符（含 SP/TAB）按 RFC 2045 §6.8 忽略；但**分离**计数，因为 MC-T04 要登记它们。
    """
    data_count = 0
    pad_count = 0
    foreign_count = 0
    first_foreign: int | None = None
    first_pad: int | None = None
    seen_pad = False
    misplaced_pad: int | None = None

    for index, byte in enumerate(body):
        if byte in _EOL_BYTES:
            continue
        if byte == _EQUAL:
            pad_count += 1
            if first_pad is None:
                first_pad = index
            seen_pad = True
            continue
        if byte in _BASE64_ALPHABET:
            data_count += 1
            if seen_pad and misplaced_pad is None:
                misplaced_pad = first_pad  # 填充之后仍有数据字符 ⇒ 填充不在末尾
            continue
        foreign_count += 1
        if first_foreign is None:
            first_foreign = index

    if pad_count > 2 and misplaced_pad is None:
        misplaced_pad = first_pad  # 填充数超过两个 ⇒ 同样非法

    return {
        "data_count": data_count,
        "pad_count": pad_count,
        "total_count": data_count + pad_count,
        "foreign_count": foreign_count,
        "first_foreign": first_foreign,
        "misplaced_pad": misplaced_pad,
    }


def decode_base64(body: bytes) -> tuple[bytes, dict[str, object]]:
    """按 RFC 2045 §6.8 解码：字母表外字符**忽略并计数**，填充/长度问题记入 facts。

    **不抛异常**：畸形输入一律按"能解多少解多少"处理，问题留给 facts 与 MC-T02/T03/T04。
    """
    facts = _base64_scan(body)
    digits: list[int] = []
    for byte in body:
        if byte in _BASE64_ALPHABET:
            digits.append(_BASE64_INDEX[byte])
    out = bytearray()
    # 每 4 个字符交出 3 字节；末组不足 4 个字符按"能交多少交多少"（截断组丢 1~2 字节，进度不吞）。
    full = len(digits) - len(digits) % 4
    for offset in range(0, full, 4):
        block = (
            (digits[offset] << 18)
            | (digits[offset + 1] << 12)
            | (digits[offset + 2] << 6)
            | digits[offset + 3]
        )
        out += bytes(((block >> 16) & 0xFF, (block >> 8) & 0xFF, block & 0xFF))
    remainder = len(digits) - full
    if remainder == 2:
        out.append(((digits[full] << 2) | (digits[full + 1] >> 4)) & 0xFF)
    elif remainder == 3:
        block = (digits[full] << 12) | (digits[full + 1] << 6) | digits[full + 2]
        out += bytes(((block >> 10) & 0xFF, (block >> 2) & 0xFF))
    facts["decoded_bytes"] = len(out)
    return bytes(out), facts


_BASE64_INDEX = {byte: index for index, byte in enumerate(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")}


# ── quoted-printable：自写解码 ────────────────────────────────────────────


def _decode_qp_tracked(body: bytes) -> tuple[bytes, list[int], dict[str, object]]:
    """QP 解码并**记录每个输出字节的来源偏移**（供 MC-T11 把解码结果映射回编码位置）。

    纪律（`plan/03` §三）：非法 ``=HH``（``=`` 后不是两位十六进制，且不在行末）**原样保留该字节**，
    不吞字符。行末 ``=`` 视作软换行（连同其后 CRLF/LF 一起吞掉，不产出任何字节）。
    """
    out = bytearray()
    origins: list[int] = []
    illegal: list[dict[str, object]] = []
    soft_breaks: list[int] = []
    index = 0
    stop = len(body)
    while index < stop:
        byte = body[index]
        if byte != _EQUAL:
            out.append(byte)
            origins.append(index)
            index += 1
            continue
        # 软换行：`=` 紧邻 CRLF / LF / 部件末尾
        if index + 1 >= stop or body[index + 1 : index + 2] in (b"\r", b"\n"):
            soft_breaks.append(index)
            if body[index + 1 : index + 3] == b"\r\n":
                index += 3
            elif index + 1 < stop:
                index += 2
            else:
                index += 1
            continue
        if index + 2 < stop and body[index + 1] in _HEX and body[index + 2] in _HEX:
            out.append(int(body[index + 1 : index + 3], 16))
            origins.append(index)
            index += 3
            continue
        # 非法转义：原样保留 `=`（随后逐字节照抄）
        text = body[index : index + 3]
        illegal.append({"offset": index, "text": text})
        out.append(byte)
        origins.append(index)
        index += 1
    return bytes(out), origins, {"illegal": illegal, "soft_breaks": soft_breaks}


def decode_qp(body: bytes) -> tuple[bytes, dict[str, object]]:
    """解码 quoted-printable：非法 ``=HH`` 原样保留并登记偏移。"""
    decoded, _origins, facts = _decode_qp_tracked(body)
    facts["decoded_bytes"] = len(decoded)
    return decoded, facts


# ── 逐规则判定 ────────────────────────────────────────────────────────────


def _base64_defects(body: bytes, path: str, body_offset: int) -> list[Defect]:
    """声明 base64 且实测为 base64 形态时的填充（T02）/ 长度（T03）/ 字母表外字符（T04）。"""
    out: list[Defect] = []
    facts = _base64_scan(body)
    misplaced = facts["misplaced_pad"]
    if misplaced is not None:
        out.append(
            _defect(
                "MC-T02",
                path,
                body_offset + int(misplaced),
                "base64 填充非法：`=` 之后仍有数据字符（填充只允许出现在末尾，且最多两个）",
            )
        )
    total = int(facts["total_count"])
    if total % 4 != 0:
        out.append(
            _defect(
                "MC-T03",
                path,
                body_offset,
                f"base64 字符数 {total} 不是 4 的倍数（末组被截断，解码会丢字节）",
            )
        )
    first_foreign = facts["first_foreign"]
    if first_foreign is not None:
        index = int(first_foreign)
        char = body[index : index + 1].decode("latin-1")
        out.append(
            _defect(
                "MC-T04",
                path,
                body_offset + index,
                f"base64 出现字母表外字符 `{char}`"
                "（RFC 2045 §6.8 原句要求忽略它 → 出现本身不是违规，只登记并计入 foreign_chars）",
            )
        )
    return out


def _qp_defects(body: bytes, path: str, body_offset: int) -> list[Defect]:
    """声明 quoted-printable 时的行宽（T05）/ 软换行（T06）/ 非法转义（T07）/ 二次编码（T11）。"""
    out: list[Defect] = []
    lines = _iter_body_lines(body)
    decoded, origins, facts = _decode_qp_tracked(body)

    illegal_by_line: set[int] = set()
    for entry in facts["illegal"]:  # type: ignore[union-attr]
        assert isinstance(entry, dict)
        start = int(entry["offset"])
        line = next((item for item in lines if item.start <= start <= item.end), None)
        illegal_by_line.add(line.number if line is not None else -1)

    # MC-T05：合法 encoded line 的行宽（含非法转义的行不记 —— 那一行已不是 encoded line）。
    for line in lines:
        width = len(line.content)
        if width <= MAX_QP_LINE_OCTETS:
            continue
        if line.number in illegal_by_line:
            continue
        out.append(
            _defect(
                "MC-T05",
                path,
                body_offset + line.start,
                f"QP 编码行 {width} > {MAX_QP_LINE_OCTETS} octets（不含 CRLF）",
            )
        )

    # MC-T06：行末 `=` 之后已无内容行 —— 软换行无法接续。
    content_lines = [line for line in lines if line.content != b""]
    if content_lines and content_lines[-1].content.endswith(b"="):
        last = content_lines[-1]
        equal_offset = last.end - 1
        out.append(
            _defect(
                "MC-T06",
                path,
                body_offset + equal_offset,
                "行末 `=` 之后已无下一行（部件在此结束）：软换行无法接续，`=` 成了悬空转义",
            )
        )

    # MC-T07：非法转义（`=` 后不是两位十六进制，且不在行末）—— 每处各记一条、精确到字节偏移。
    for entry in facts["illegal"]:  # type: ignore[union-attr]
        assert isinstance(entry, dict)
        offset = int(entry["offset"])
        text = bytes(entry["text"])  # type: ignore[arg-type]
        window = text.decode("latin-1")
        out.append(
            _defect(
                "MC-T07",
                path,
                body_offset + offset,
                f"QP 非法转义 `{window}`：`=` 后不是两位十六进制"
                "（R8 把行末 `=` 的唯一合法语义限定为软换行，故 `=` 后非 `HH` 即违反 §6.7）",
            )
        )

    # MC-T11：解码一遍之后正文里仍见字面 `=HH`（上游疑似被编码两次）。
    resid = _first_hex_escape(decoded)
    if resid is not None:
        residue = decoded[resid : resid + 3].decode("latin-1")
        source = origins[resid] if resid < len(origins) else 0
        out.append(
            _defect(
                "MC-T11",
                path,
                body_offset + source,
                f"QP 解码一遍之后正文里仍出现字面 `{residue}`：上游疑似被编码了两次"
                "（只登记，不猜责任方）",
            )
        )
    return out


def _first_hex_escape(decoded: bytes) -> int | None:
    """解码结果里第一处字面 ``=HH`` 的位移；没有则 ``None``。"""
    index = 0
    stop = len(decoded)
    while index + 2 < stop:
        if decoded[index] == _EQUAL and decoded[index + 1] in _HEX and decoded[index + 2] in _HEX:
            return index
        index += 1
    return None


def _line_width_defects(body: bytes, path: str, body_offset: int, label: str) -> list[Defect]:
    """MC-T09：7bit / 8bit 正文行 > 998 octets（R11 整行未录 → 只登记）。"""
    out: list[Defect] = []
    for line in _iter_body_lines(body):
        width = len(line.content)
        if width > MAX_7BIT_LINE_OCTETS:
            out.append(
                _defect(
                    "MC-T09",
                    path,
                    body_offset + line.start,
                    f"{label} 正文行 {width} > {MAX_7BIT_LINE_OCTETS} octets（R11 整行未录 → 只登记）",
                )
            )
    return out


# ── 声明面（CTE 头）──────────────────────────────────────────────────────


def declared_cte_of(node: Node, data: bytes) -> tuple[str | None, int | None]:
    """取节点的 ``Content-Transfer-Encoding`` 值与其**首行行首**的绝对偏移。

    返回 ``(值小写化, 行首偏移)``；无该头时 ``(None, None)``。同名头取**首个**（与 `scan`
    对 `Content-Type` 的口径一致）。值里的折行空白在取值时去掉。
    """
    for header in node.headers:
        if header.name.lower() != "content-transfer-encoding":
            continue
        spans = header.line_spans
        if not spans:
            return None, None
        start = spans[0][0]
        raw = data[start : spans[-1][1]]
        colon = raw.find(b":")
        value = raw[colon + 1 :] if colon >= 0 else raw
        text = value.decode("ascii", "replace").split()
        token = text[0].lower() if text else ""
        return (token or None), start
    return None, None


# ── 入口：单叶节点 ────────────────────────────────────────────────────────


def audit_body(
    body: bytes,
    declared_cte: str | None,
    *,
    path: str = "0",
    body_offset: int = 0,
    cte_offset: int | None = None,
) -> BodyFacts:
    """产出一个叶节点的正文级缺陷（MC-T 系列）。

    :param body: 该节点的**原始正文字节**（未解码）。
    :param declared_cte: ``Content-Transfer-Encoding`` 头值（原始大小写）；缺失写 ``None``。
    :param path: 树路径（`data/README` §7.3）。
    :param body_offset: ``body[0]`` 在文件里的绝对偏移（缺陷 ``offset`` 一律换算成绝对偏移）。
    :param cte_offset: CTE 头**首行行首**的绝对偏移（MC-T08 落点）；缺省时回落到 ``body_offset``。

    判定顺序见模块 docstring（§7.5 第 5 条）。
    """
    declared = declared_cte.strip().lower() if declared_cte else None
    shape = observe_body_shape(body)
    offsets = cte_offset if cte_offset is not None else body_offset
    defects: list[Defect] = []

    # ① 声明值是否已知（MC-T08）。未知 → 无法交叉校验，只出这一条。
    if declared is not None and declared not in KNOWN_CTE:
        defects.append(
            _defect(
                "MC-T08",
                path,
                offsets,
                f"未知 CTE 取值 `{declared}`"
                "（既不是 7bit/8bit/binary/quoted-printable/base64，也不在已登记形态内）",
            )
        )
        return BodyFacts(
            declared_cte=declared, shape=shape, decoded_sha256=None, defects=tuple(defects)
        )

    decoded_sha256: str | None = None

    # ② 声明形态合法性。
    if declared == "base64":
        if shape.kind == "base64":
            defects.extend(_base64_defects(body, path, body_offset))
            decoded, _facts = decode_base64(body)
            decoded_sha256 = hashlib.sha256(decoded).hexdigest()
        elif shape.kind != "empty":
            # ③ declared vs observed：声明 base64 而实测不是 base64 —— 只出 MC-T01。
            defects.append(
                _defect(
                    "MC-T01",
                    path,
                    body_offset,
                    f"声明 base64、实际形态为{_KIND_LABEL[shape.kind]}"
                    "（语义层判定，不是条款判定；不硬判 → 退出码不受影响）",
                )
            )
    elif declared == "quoted-printable":
        defects.extend(_qp_defects(body, path, body_offset))
        decoded, _qfacts = decode_qp(body)
        decoded_sha256 = hashlib.sha256(decoded).hexdigest()

    effective = declared or "7bit"
    if effective in {"7bit", "8bit"}:
        defects.extend(_line_width_defects(body, path, body_offset, effective))

    # MC-T10：**未声明** CTE（缺省 7bit）而正文含 8bit 字节。
    if declared is None and shape.kind == "binary":
        index = next(i for i, byte in enumerate(body) if byte >= 0x80)
        defects.append(
            _defect(
                "MC-T10",
                path,
                body_offset + index,
                "未声明 Content-Transfer-Encoding（缺省为 7bit），但正文含 8bit 字节"
                "（R11 整行未录 → 只登记）",
            )
        )

    return BodyFacts(
        declared_cte=declared,
        shape=shape,
        decoded_sha256=decoded_sha256,
        defects=tuple(sorted(defects, key=lambda item: item.sort_key)),
    )


# ── 入口：整棵树 ──────────────────────────────────────────────────────────


def _iter_nodes(node: Node):
    yield node
    for child in node.children:
        yield from _iter_nodes(child)


def audit_transfer(root: Node, data: bytes) -> tuple[Defect, ...]:
    """遍历整棵树，对每个**非 multipart** 节点跑 :func:`audit_body`，缺陷打该节点的 ``path``。

    为什么跳过 ``multipart/*``：那类节点的"正文"是 delimiter 与子部件的拼接，不是传输编码的
    产物；对它做 base64/QP 判定只会把结构字节误报成编码缺陷。叶节点与 ``message/rfc822``
    等非 multipart 节点才会被审计。
    """
    defects: list[Defect] = []
    for node in _iter_nodes(root):
        if node.content_type.startswith("multipart/"):
            continue
        declared, cte_offset = declared_cte_of(node, data)
        start, end = node.body_range
        facts = audit_body(
            data[start:end],
            declared,
            path=node.path,
            body_offset=start,
            cte_offset=cte_offset,
        )
        defects.extend(facts.defects)
    return tuple(sorted(defects, key=lambda item: item.sort_key))
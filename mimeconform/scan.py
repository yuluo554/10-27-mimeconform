"""字节扫描状态机：头块定位 → multipart 切分 → 递归子部件（模块 M1 / 里程碑 M2）。

**状态机契约（plan/02 §二，实现时不得改变语义）**::

    HEADER_BLOCK ──空行──▶ BODY
                        ├─ Content-Type: multipart/*; boundary=B ──▶ PART_BODY(B)
                        └─ message/rfc822 ──▶ 递归（内层消息归属审计自 M5 起）

    PART_BODY(B) 逐行扫描（CRLF 与裸 LF 都接受，行界保留原始偏移）：
      "--"+B                     → part 开始（前一 part 结束）
      "--"+B+"--"[LWSP]          → multipart 关闭
      "--"+B+"--"+非空白内容      → MC-B04（形态错误；该行按内容处理）
      行首空白 + "--"+B           → MC-B03（delimiter 未在行首；该行按内容处理）
      其余                        → 归入当前 part 的字节区间

**纪律**：
* 行界按 ``\\n`` 切分而非 ``str.splitlines()``（后者还会切 ``\\r`` / ``\\x0b`` / ``\\u2028``）；
* boundary 比较**按字节**、不做大小写折叠（``plan/01`` M1 纪律）；
* preamble / epilogue **不计入** ``body_sha256``；
* delimiter 行前的 CRLF 归 delimiter（RFC 2046 §5.1.1），故 part 正文不含那一对行尾。

**判定顺序（§7.5 第 6 条，写死）**：B01 缺 boundary → B02 超 70 → B03/B04 形态 →
B06 嵌套复用 → B05 缺 final boundary。B03/B04 在**区域扫描期**登记（最外层作用域优先），
B06/B09 在**子节点构造期**，B07/B08/B10/B05 在**区域收尾期**。

**两棵候选树（plan/00 D9）**：嵌套复用同一 boundary 时，close-delimiter 的归属在字节层
无法唯一确定 —— 引擎产出 ``tree_alternatives``（长度 2：内层先闭合 / 外层先闭合）与
``divergence``（首个分歧的 path + 首个歧义 delimiter 的字节偏移）。**默认展示（= 内层先闭合）
不构成判定**：它只是 ``plan/02`` §二 指定的展示顺序。缺陷只从默认树产出；同一段字节不因
歧义出两条互斥账 —— 复用节点的**父** multipart 因此不再登记 MC-B05（缺 final boundary）。

**深度**：``--max-depth`` 是策略项（§7.6）而非 RFC 条款。节点深度 = 路径段数（根 ``0`` 为
第 1 层）；超限即登记 MC-B09（``gray``）并**停止下钻**，登记进 ``facts["truncated_paths"]``
与节点的 ``truncated=True`` —— 不是崩溃、不是静默截断。

**头块**：本模块只做**定位**（头名 / 值字节 / 行跨度 / 偏移），供建树取 ``Content-Type`` 与
``boundary``；RFC 2047 / 2231 的语法审计属 ``headers.py``（模块 M2 / 里程碑 M3），故此处
``Header.encoded_words`` / ``Header.params`` 一律留空 —— 不在扫描层替上层下结论。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from . import constants as C
from .model import Defect, Divergence, Header, Node, path_key

_LWSP = b" \t"

#: 默认（展示用）树的解析语义：内层先闭合。
DEFAULT_TREE_MODE = "inner-first"
#: 备选树的解析语义：外层先闭合。
ALTERNATIVE_TREE_MODE = "outer-first"

#: MC-B 系列的静态形态（``class`` / ``severity`` / ``rfc``）—— 引擎侧的唯一定义点。
#: 取值与 ``data/README`` §7.1/§7.4 及 ``data/golden/b-*/expect.json`` 同口径；
#: ``catalog.json``（M3）落地后这组值机读化，判据不变。
_RULE_META: dict[str, tuple[str, str, str]] = {
    "MC-B01": (C.CLASS_HARD, C.SEV_BLOCKER, "RFC 2046 §5.1.1"),
    "MC-B02": (C.CLASS_HARD, C.SEV_MINOR, "RFC 2046 §5.1.1"),
    "MC-B03": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2046 §5.1.1"),
    "MC-B04": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2046 §5.1.1"),
    "MC-B05": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-B06": (C.CLASS_HARD, C.SEV_MAJOR, "RFC 2046 §5.1.1/§5.1.2"),
    "MC-B07": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2046 §5.1.1"),
    "MC-B08": (C.CLASS_DIFF, C.SEV_NOTE, "RFC 2046 §5.1.1"),
    "MC-B09": (C.CLASS_GRAY, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-B10": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
}

#: MC-B06 的歧义声明（报告必须显式写出，不得只写"违规"）。
AMBIGUITY_NOTE = (
    "内层 boundary 与外层重复时，字节层无法唯一确定 close-delimiter 的归属："
    "``tree_alternatives`` 给出两棵候选树（内层先闭合 / 外层先闭合），"
    "``divergence`` 给出首个分歧的 path 与字节偏移。默认展示内层先闭合，**不构成判定**"
    "（plan/00 D9）。"
)


@dataclass(frozen=True, slots=True)
class ScanResult:
    """一次扫描的完整产出（渲染层只消费它，不做判定）。"""

    root: Node
    defects: tuple[Defect, ...] = field(default=())
    tree_alternatives: tuple[Node, ...] = field(default=())
    divergence: Divergence | None = None
    facts: dict[str, object] = field(default_factory=dict)


# ── 行切分（引擎的唯一入口，K7）────────────────────────────────────────────


def split_lines(data: bytes, start: int = 0, end: int | None = None) -> list[tuple[int, bytes]]:
    """按 ``\\n`` 切行，返回 ``(行首偏移, 行字节含行尾)`` 列表。

    这是引擎的**唯一**切行实现：不做解码、不吞 ``\\r``、不把 ``\\x0b`` 当行界。
    Unicode 的 ``splitlines()`` 语义与 MIME 的行定义不同，用它会改变字节偏移。

    ``end`` 限定扫描窗口（默认到 ``len(data)``）：区域恰在中途结束时，最后一"行"
    可以没有行尾 —— 那时按实际字节切，不补、不吞。
    """
    if start < 0 or start > len(data):
        raise ValueError(f"start 越界: {start}")
    stop = len(data) if end is None else end
    if stop < start or stop > len(data):
        raise ValueError(f"end 越界: {end}")
    out: list[tuple[int, bytes]] = []
    pos = start
    while pos < stop:
        newline = data.find(b"\n", pos, stop)
        if newline < 0:
            out.append((pos, data[pos:stop]))
            break
        out.append((pos, data[pos : newline + 1]))
        pos = newline + 1
    return out


def _line_content(raw: bytes) -> bytes:
    """行字节 → 内容字节（去掉行尾 ``\\n`` / ``\\r\\n``；不碰其他空白）。"""
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    return raw


def _trim_eol_before(data: bytes, start: int, stop: int) -> int:
    """part 结束于 ``stop``（某 delimiter 行首）时，把紧邻的 CRLF/LF 归给 delimiter。

    RFC 2046 §5.1.1：delimiter 行前的 CRLF 概念上属于 delimiter 本身，故 part 正文
    不含那一对行尾 —— ``body_sha256`` 因此不会被"换行算谁"的歧义污染。
    """
    if stop - start >= 2 and data[stop - 2 : stop] == b"\r\n":
        return stop - 2
    if stop - start >= 1 and data[stop - 1 : stop] == b"\n":
        return stop - 1
    return stop


def _has_visible_content(data: bytes, start: int, stop: int) -> bool:
    """区间内除 LWSP / 行尾外是否还有内容（preamble / epilogue 的登记判据）。"""
    return data[start:stop].strip(b" \t\r\n") != b""


def _is_field_name(name: bytes) -> bool:
    """RFC 5322 §2.2：字段名是可见 ASCII（排除 ``:`` 与空白）。"""
    if not name:
        return False
    return all(33 <= byte <= 126 and byte != 58 for byte in name)


# ── 头块定位 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Param:
    """一个 ``name=value`` 参数的**字节级**事实（不做解码、不做判定）。"""

    name: str
    value: bytes
    name_offset: int    # 参数名在文件中的绝对偏移
    value_offset: int   # 参数值（含引号形态）在文件中的绝对偏移；无值时为 -1


@dataclass(frozen=True, slots=True)
class _HeaderBlock:
    headers: tuple[Header, ...]
    body_start: int
    content_type: str
    boundary: bytes | None
    ct_line_start: int | None        # Content-Type 头首行的行首偏移
    boundary_line_start: int | None  # boundary 参数名所在物理行的行首偏移


def _skip_fws(value: bytes, index: int) -> int:
    stop = len(value)
    while index < stop and value[index : index + 1] in (b" ", b"\t", b"\r", b"\n"):
        index += 1
    return index


def _parse_media_type(value: bytes, base: int) -> tuple[str | None, list[_Param]]:
    """切分 ``type/subtype; name=value; ...``（折行已由行拼接保留为原始字节）。

    只做**语法切分**：不判合法性、不解码、不区分大小写以外的一切语义。
    """
    index = _skip_fws(value, 0)
    stop = len(value)
    start = index
    while index < stop and value[index : index + 1] not in (b";", b" ", b"\t", b"\r", b"\n"):
        index += 1
    media = value[start:index].decode("ascii", "replace").lower()
    params: list[_Param] = []
    while index < stop:
        if value[index : index + 1] != b";":
            index += 1
            continue
        index = _skip_fws(value, index + 1)
        name_start = index
        while index < stop and value[index : index + 1] not in (b"=", b";", b" ", b"\t", b"\r", b"\n"):
            index += 1
        name = value[name_start:index].decode("ascii", "replace").lower()
        if not name:
            continue
        if index < stop and value[index : index + 1] == b"=":
            index = _skip_fws(value, index + 1)
            value_start = index
            if value[index : index + 1] == b'"':
                end = index + 1
                buf = bytearray()
                while end < stop:
                    char = value[end : end + 1]
                    if char == b"\\" and end + 1 < stop:
                        buf += value[end + 1 : end + 2]
                        end += 2
                        continue
                    if char == b'"':
                        end += 1
                        break
                    buf += char
                    end += 1
                params.append(_Param(name, bytes(buf), base + name_start, base + value_start))
                index = end
            else:
                while index < stop and value[index : index + 1] not in (b";", b" ", b"\t", b"\r", b"\n"):
                    index += 1
                params.append(_Param(name, value[value_start:index], base + name_start, base + value_start))
        else:
            params.append(_Param(name, b"", base + name_start, -1))
    return (media if media else None), params


def _parse_header_block(data: bytes, start: int, end: int) -> _HeaderBlock:
    """定位 ``[start, end)`` 上的头块。

    终止条件（按字节、逐行）：
    * 空行 → 头块结束，``body_start`` 在空行之后；
    * 字段名非法（无冒号 / 非法字符）/ 孤立的续行 → **该行起就是正文**（``body_start = 行首``）。

    折叠行（SP/TAB 开头）并入前一个头；``raw_value`` 取原始字节切片（含内部 CRLF 与
    续行空白），因此参数偏移可直接映射回文件绝对偏移。
    """
    entries: list[dict[str, object]] = []
    body_start = end
    for line_start, raw in split_lines(data, start, end):
        content = _line_content(raw)
        if content == b"":
            body_start = min(line_start + len(raw), end)
            break
        if content[:1] in (b" ", b"\t"):
            if not entries:
                body_start = line_start
                break
            last = entries[-1]
            last["last_end"] = line_start + len(content)
            spans = last["line_spans"]
            assert isinstance(spans, list)
            spans.append((line_start, line_start + len(content)))
            continue
        colon = content.find(b":")
        if colon <= 0 or not _is_field_name(content[:colon]):
            body_start = line_start
            break
        entries.append(
            {
                "name": content[:colon].decode("ascii", "replace"),
                "value_start": line_start + colon + 1,
                "last_end": line_start + len(content),
                "line_spans": [(line_start, line_start + len(content))],
            }
        )

    headers: list[Header] = []
    for entry in entries:
        value_start = int(entry["value_start"])
        last_end = int(entry["last_end"])
        raw_value = data[value_start:last_end]
        spans = entry["line_spans"]
        assert isinstance(spans, list)
        headers.append(
            Header(
                name=str(entry["name"]),
                raw_value_sha256=hashlib.sha256(raw_value).hexdigest(),
                octets=len(raw_value),
                line_spans=tuple((int(a), int(b)) for a, b in spans),
            )
        )

    # RFC 2045 §5.2：缺失 Content-Type 的缺省值是 text/plain; charset=us-ascii。
    content_type = "text/plain"
    boundary: bytes | None = None
    ct_line_start: int | None = None
    boundary_line_start: int | None = None
    for entry in entries:
        if str(entry["name"]).lower() != "content-type":
            continue
        value_start = int(entry["value_start"])
        media, params = _parse_media_type(data[value_start : int(entry["last_end"])], value_start)
        spans = entry["line_spans"]
        assert isinstance(spans, list)
        ct_line_start = int(spans[0][0])
        # `multipart` 之外的主类型无法判定时按 application/octet-stream 处理（不猜）。
        content_type = media if media and "/" in media else "application/octet-stream"
        for param in params:
            if param.name != "boundary":
                continue
            boundary = param.value
            boundary_line_start = data.rfind(b"\n", 0, param.name_offset) + 1
            break
        break  # 首个 Content-Type 生效（同名头的"取首个 + 登记"口径属 M3）
    if boundary is not None and not boundary.strip():
        boundary = None  # 空值等价于缺失 → MC-B01（显式拒绝，不静默当合法）
    return _HeaderBlock(
        headers=tuple(headers),
        body_start=body_start,
        content_type=content_type,
        boundary=boundary,
        ct_line_start=ct_line_start,
        boundary_line_start=boundary_line_start,
    )


# ── 扫描器 ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Event:
    """multipart 区域扫描命中的一行形态。"""

    line_start: int
    line_end: int   # 含行尾
    kind: str       # "delim" | "close"


@dataclass(frozen=True, slots=True)
class _Part:
    """一个部件的头块级事实（**不递归** —— 递归由 :meth:`_Scanner._build_node` 决定）。"""

    path: str
    headers: tuple[Header, ...]
    content_type: str
    boundary: bytes | None
    ct_line_start: int | None
    boundary_line_start: int | None
    body_start: int
    span_end: int
    depth: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class _Region:
    """一次 multipart 区域扫描的结果。"""

    children: tuple[Node, ...]
    close_found: bool
    close_line_end: int | None
    first_event_start: int | None
    epilogue_start: int | None
    preamble_visible: bool
    ambiguous: bool
    body_start: int
    region_end: int


class _Scanner:
    """一次解析（默认树或备选树）的全部状态。

    ``inner_first=False`` 时不再让复用 boundary 的子节点吸收父区域余量 —— 于是
    ``--b`` 类 delimiter 全部归外层作用域，产出"外层先闭合"的那棵候选树。
    """

    def __init__(
        self,
        data: bytes,
        *,
        max_depth: int,
        inner_first: bool,
        collect: bool,
        strict_depth: bool = False,
    ) -> None:
        self.data = data
        self.max_depth = max_depth
        self.inner_first = inner_first
        self.collect = collect          # 备选树只建结构，不产出缺陷
        self.strict_depth = strict_depth
        self.defects: list[Defect] = []
        self.truncated_paths: list[str] = []
        self.reused_paths: list[str] = []
        self.ambiguity_offsets: list[int] = []

    # -- 缺陷 ------------------------------------------------------------

    def _defect(self, rule_id: str, path: str, offset: int, detail: str, *, severity: str | None = None) -> None:
        if not self.collect:
            return
        klass, default_severity, rfc = _RULE_META[rule_id]
        self.defects.append(
            Defect(
                rule_id=rule_id,
                klass=klass,
                severity=severity if severity is not None else default_severity,
                path=path,
                offset=offset,
                offset_kind=C.OFFSET_ABSOLUTE,
                rfc=rfc,
                detail=detail,
            )
        )

    def finalize_defects(self) -> tuple[Defect, ...]:
        """去重 + 按 §7.8 排序（落盘即有序）。

        B03/B04 在区域扫描期登记，同一行可能同时落在"父区域扫描"与"内层区域扫描"两处
        作用域 —— 按 ``(rule_id, offset)`` 只留**先登记的**那一条（最外层作用域优先），
        保证同一段字节不出两条形态账。
        """
        seen: set[tuple[str, int]] = set()
        kept: list[Defect] = []
        for defect in self.defects:
            if defect.rule_id in {"MC-B03", "MC-B04"}:
                key = (defect.rule_id, defect.offset)
                if key in seen:
                    continue
                seen.add(key)
            kept.append(defect)
        return tuple(sorted(kept, key=lambda item: item.sort_key))

    # -- 节点 ------------------------------------------------------------

    def _parse_part(self, path: str, start: int, span_end: int, depth: int) -> _Part:
        block = _parse_header_block(self.data, start, span_end)
        truncated = depth > self.max_depth
        if truncated:
            self.truncated_paths.append(path)
            self._defect(
                "MC-B09",
                path,
                block.ct_line_start if block.ct_line_start is not None else start,
                f"嵌套深度 {depth} > --max-depth {self.max_depth}"
                "（RFC 未规定深度上限；策略项"
                + ("，--strict-depth 已开启故计入退出码）" if self.strict_depth else "，默认不影响退出码）"),
                severity=C.SEV_MINOR if self.strict_depth else None,
            )
        return _Part(
            path=path,
            headers=block.headers,
            content_type=block.content_type,
            boundary=block.boundary,
            ct_line_start=block.ct_line_start,
            boundary_line_start=block.boundary_line_start,
            body_start=block.body_start,
            span_end=span_end,
            depth=depth,
            truncated=truncated,
        )

    def _build_node(
        self,
        path: str,
        start: int,
        span_end: int,
        depth: int,
        ancestors: tuple[bytes, ...],
        *,
        absorb_end: int | None,
    ) -> tuple[Node, bool]:
        """构造一个节点；返回 ``(node, absorbed)``。

        ``absorbed=True``（仅默认树）表示该节点吸收了**父 multipart 区域余下的字节**
        —— 父级据此确认自己的 close-delimiter 归属有歧义，不再登记 MC-B05。
        """
        part = self._parse_part(path, start, span_end, depth)
        is_multipart = part.content_type.startswith("multipart/")
        children: tuple[Node, ...] = ()
        absorbed = False
        body_range = (part.body_start, part.span_end)

        # §7.5 第 6 条：B01 缺 boundary → B02 超 70 → 之后才谈 delimiter / 嵌套 / final。
        if is_multipart and part.boundary is None:
            self._defect(
                "MC-B01",
                part.path,
                part.ct_line_start if part.ct_line_start is not None else start,
                f"{part.content_type} 缺 boundary 参数（RFC 2046 §5.1.1 要求多部件实体必须有一个 boundary 参数）",
            )
        elif is_multipart:
            boundary = part.boundary
            assert boundary is not None
            if len(boundary) > 70:
                self._defect(
                    "MC-B02",
                    part.path,
                    part.boundary_line_start if part.boundary_line_start is not None else start,
                    f"boundary 长度 {len(boundary)} > 70（不含前导两个连字符）",
                )
            reuse = boundary in ancestors
            if reuse:
                self.reused_paths.append(part.path)
                self._defect(
                    "MC-B06",
                    part.path,
                    part.ct_line_start if part.ct_line_start is not None else start,
                    f"内层 multipart 复用了外层 boundary {boundary.decode('ascii', 'replace')!r}"
                    "（RFC 2046 §5.1.1/§5.1.2 要求每层用不同 boundary）",
                )
            if part.truncated:
                pass  # 超深度即停止下钻（更深的缺陷无从判定，也不猜）
            else:
                if reuse and self.inner_first and absorb_end is not None:
                    region = self._parse_multipart_region(
                        part.path,
                        part.body_start,
                        absorb_end,
                        boundary,
                        part.content_type,
                        depth + 1,
                        ancestors + (boundary,),
                    )
                    absorbed = True
                    if region.first_event_start is not None:
                        self.ambiguity_offsets.append(region.first_event_start)
                else:
                    region = self._parse_multipart_region(
                        part.path,
                        part.body_start,
                        part.span_end,
                        boundary,
                        part.content_type,
                        depth + 1,
                        ancestors + (boundary,),
                    )
                children = region.children
                body_range = _multipart_body_range(region)

        return (
            Node(
                path=part.path,
                content_type=part.content_type,
                boundary=part.boundary.decode("ascii", "replace") if part.boundary is not None else None,
                headers=part.headers,
                body_range=body_range,
                body_sha256=hashlib.sha256(self.data[body_range[0] : body_range[1]]).hexdigest(),
                children=children,
                truncated=part.truncated,
            ),
            absorbed,
        )

    def _parse_multipart_region(
        self,
        path: str,
        region_start: int,
        region_end: int,
        boundary: bytes,
        media: str,
        child_depth: int,
        ancestors: tuple[bytes, ...],
    ) -> _Region:
        """切分一个 multipart 区域并递归构造子节点。"""
        dash = b"--" + boundary
        close_marker = dash + b"--"
        readable = boundary.decode("ascii", "replace")
        events: list[_Event] = []
        for line_start, raw in split_lines(self.data, region_start, region_end):
            content = _line_content(raw)
            line_end = line_start + len(raw)
            if content == dash:
                events.append(_Event(line_start, line_end, "delim"))
                continue
            if content == close_marker or (
                content.startswith(close_marker) and content[len(close_marker) :].strip(_LWSP) == b""
            ):
                events.append(_Event(line_start, line_end, "close"))
                continue
            if content.startswith(close_marker):
                self._defect(
                    "MC-B04",
                    path,
                    line_start,
                    f"close-delimiter 形态错误：`--{readable}--` 之后还有内容（只允许可忽略的空白与行尾）",
                )
                continue
            if content.lstrip(_LWSP).startswith(dash):
                self._defect(
                    "MC-B03",
                    path,
                    line_start,
                    f"疑似 delimiter `--{readable}` 未出现在行首（前导空白）——"
                    "R7 的 delimiter 形态子项原句未留档，只登记",
                )

        first_event = events[0].line_start if events else None
        children: list[Node] = []
        close_found = False
        close_line_end: int | None = None
        epilogue_start: int | None = None
        ambiguous = False

        index = 0
        while index < len(events):
            event = events[index]
            if event.kind == "close":
                close_found = True
                close_line_end = event.line_end
                epilogue_start = event.line_end
                break
            next_event = events[index + 1] if index + 1 < len(events) else None
            content_start = event.line_end
            content_end = (
                region_end if next_event is None else _trim_eol_before(self.data, content_start, next_event.line_start)
            )
            node, absorbed = self._build_node(
                f"{path}.{len(children) + 1}",
                content_start,
                content_end,
                child_depth,
                ancestors,
                absorb_end=region_end,
            )
            children.append(node)
            index += 1
            if absorbed:
                # 余量已被复用 boundary 的内层节点吸收 —— 外层 close-delimiter 归属有歧义
                ambiguous = True
                break

        # ── 区域收尾（§7.5 第 6 条的末段）：B07/B08 登记 → B10 空 multipart → B05 缺 final
        preamble = (region_start, first_event if first_event is not None else region_end)
        if _has_visible_content(self.data, *preamble):
            self._defect(
                "MC-B07",
                path,
                preamble[0],
                "存在 preamble 字节区间（RFC 2046 §5.1.1 要求忽略；存在本身不是违规）",
            )
        if epilogue_start is not None and _has_visible_content(self.data, epilogue_start, region_end):
            self._defect(
                "MC-B08",
                path,
                epilogue_start,
                "存在 epilogue 字节区间（RFC 2046 §5.1.1 要求忽略；存在本身不是违规）",
            )
        if not children:
            self._defect(
                "MC-B10",
                path,
                first_event if first_event is not None else region_start,
                f"{media} 无任何 body part（RFC 无明文条款；"
                "依据 stdlib MultipartInvariantViolationDefect 的实现事实，只登记）",
            )
        if not close_found and not ambiguous:
            self._defect(
                "MC-B05",
                path,
                region_end,
                f"缺 final boundary：树在第 {region_end} 字节被迫闭合（RFC 只描述 truncated entity，无恢复规程）",
            )
        return _Region(
            children=tuple(children),
            close_found=close_found,
            close_line_end=close_line_end,
            first_event_start=first_event,
            epilogue_start=epilogue_start,
            preamble_visible=_has_visible_content(self.data, *preamble),
            ambiguous=ambiguous,
            body_start=region_start,
            region_end=region_end,
        )

    # -- 入口 ------------------------------------------------------------

    def build_root(self) -> Node:
        node, _absorbed = self._build_node("0", 0, len(self.data), 1, (), absorb_end=None)
        return node


def _multipart_body_range(region: _Region) -> tuple[int, int]:
    """multipart 节点的 ``body_range``：首个 delimiter 行首 → close-delimiter 行末。

    preamble / epilogue **不计入**（``plan/01`` M1 确定性纪律）；无 delimiter 时退回整段
    ——节点仍然可复核，不对"没有 boundary 的 multipart"伪造一个区间。
    """
    lower = region.first_event_start if region.first_event_start is not None else region.body_start
    upper = region.close_line_end if region.close_line_end is not None else region.region_end
    return (lower, upper)


def tree_rows(root: Node) -> list[tuple[str, tuple[object, ...]]]:
    """按 path 整数排序的节点行 —— 两棵树的结构比对与 ``divergence`` 的判据。"""
    rows: list[tuple[str, tuple[object, ...]]] = []

    def walk(node: Node) -> None:
        rows.append(
            (
                node.path,
                (
                    node.content_type,
                    node.boundary,
                    node.body_sha256,
                    tuple(child.path for child in node.children),
                    node.truncated,
                ),
            )
        )
        for child in node.children:
            walk(child)

    walk(root)
    rows.sort(key=lambda row: path_key(row[0]))
    return rows


def _divergence(
    primary: Node,
    alternative: Node,
    offsets: list[int],
    *,
    reused_paths: list[str],
) -> Divergence:
    """两棵候选树的首个分歧（``path`` 按整数序；``offset`` 取首个歧义 delimiter 的字节位置）。

    **分歧落在"复用 boundary 的那个节点"上**，不是根：根的子节点列表当然也会不同，但那只是
    下游结果——真正"同一段字节被读成两种归属"的位置是该节点自己（内层先闭合时它有子部件与
    自己的 close；外层先闭合时它是叶节点，close 归外层）。按这个口径，``divergence.path``
    与 MC-B06 的 ``path`` 指向同一处，报告因此能一句话回答"哪一层的归属有歧义"。
    """
    rows_a = dict(tree_rows(primary))
    rows_b = dict(tree_rows(alternative))
    offset = offsets[0] if offsets else 0
    for path in sorted(reused_paths, key=path_key):
        if rows_a.get(path) != rows_b.get(path):
            return Divergence(
                path=path,
                offset=offset,
                note=(
                    f"两棵树在 `{path}` 首次分歧：close-delimiter 归属在字节层无法唯一确定"
                    f"（首个歧义 delimiter 位于第 {offset} 字节）—— {AMBIGUITY_NOTE}"
                ),
            )
    # 复用节点在两棵树下解析一致（理论上不该出现）：仍给出声明落点，绝不返回"没有歧义"。
    fallback = reused_paths[0]
    return Divergence(
        path=fallback,
        offset=offset,
        note=f"复用 boundary 的节点 `{fallback}` 触发了两棵树路径 —— {AMBIGUITY_NOTE}",
    )


def _node_count(root: Node) -> int:
    return 1 + sum(_node_count(child) for child in root.children)


def scan_message(
    data: bytes,
    *,
    max_depth: int = C.MAX_DEPTH_DEFAULT,
    strict_depth: bool = False,
) -> ScanResult:
    """把一封邮件的原始字节切成 multipart 树并产出 MC-B 系列缺陷。

    ``max_depth`` 必须 >= 1（显式拒绝 0/负数，不静默改回默认值 —— CLI 同口径）。
    ``strict_depth=True`` 时 MC-B09 的 severity 提为 ``minor``（``class`` 仍是 ``gray``，
    见 §7.6：这是**用户显式选择**，不是 RFC 结论）。
    复用 boundary 时**总是**产出两棵候选树 + ``divergence``（plan/00 D9）：
    默认 ``root`` = 内层先闭合，``tree_alternatives`` = (默认树, 外层先闭合树)。
    """
    if max_depth < 1:
        raise ValueError(f"max_depth 必须 >= 1（收到 {max_depth}）：0/负数不是合法策略值")
    scanner = _Scanner(data, max_depth=max_depth, inner_first=True, collect=True, strict_depth=strict_depth)
    root = scanner.build_root()
    defects = scanner.finalize_defects()
    alternatives: tuple[Node, ...] = ()
    divergence: Divergence | None = None
    if scanner.reused_paths:
        alt_scanner = _Scanner(
            data, max_depth=max_depth, inner_first=False, collect=False, strict_depth=strict_depth
        )
        alt_root = alt_scanner.build_root()
        alternatives = (root, alt_root)
        divergence = _divergence(root, alt_root, scanner.ambiguity_offsets, reused_paths=scanner.reused_paths)
    facts: dict[str, object] = {
        "mode": DEFAULT_TREE_MODE,
        "max_depth": max_depth,
        "strict_depth": strict_depth,
        "node_count": _node_count(root),
        "reused_boundary_paths": list(scanner.reused_paths),
        "truncated_paths": list(scanner.truncated_paths),
        "ambiguity_offsets": list(scanner.ambiguity_offsets),
    }
    return ScanResult(
        root=root,
        defects=defects,
        tree_alternatives=alternatives,
        divergence=divergence,
        facts=facts,
    )
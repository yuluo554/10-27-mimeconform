# 缺陷分类表（人读）

> **机读镜像**：`mimeconform/rules/catalog.json`。本文件与它**规则数一致**、`class` / `severity` / `rfc` 逐值一致，
> 由 `tests/test_catalog_doc.py` 机器断言（不是人工核对）。
> **编号语义**只在 `data/README.md` §7.2 定义；**数值口径**（三值 / 四档 / 退出码 / 指纹 / 判定顺序）只在 §七；
> 本文只写"这条规则判什么、依据到哪一行、正负例在哪、常见误报是什么"。
> **覆盖范围**：本文件随里程碑增量维护。当前覆盖 **B 簇 10 条（M2）+ H 簇 12 条（M3）+ T 传输编码 11 条（M4）+
> A 簇 8 条（M5）+ C 容器 5 条（M5）= 46 条**；`catalog.json` 与本文同一笔提交同轮增长。
> **A / C 两簇全部 `diff`/`note`**（`plan/00` D11）：`Content-Disposition`、`multipart/related` 与
> mbox / Maildir 都不在本题核对的五部 RFC 之内 → `rfc = none-by-design`。

---

## 一、`class` 三值怎么读（引用 §7.1，不另立表述）

| 值 | 一句话 | 机械判据 |
| --- | --- | --- |
| `hard` | 有**逐字原句**支撑的硬规则 | `ledger_key` 解析出的 `verbatim` 非空 |
| `diff` | RFC 无条款，或实现间存在可辩护分歧 | `verbatim` 为 null，或 `ledger_key = none-by-design` |
| `gray` | RFC 未规定的**策略项**（如最大嵌套深度） | 同上 + 必须附策略参数名与默认值 |

**原句门禁是机械的**：`catalog.json` 里 `class=hard` 而 `ledger_key` 没有逐字原句 → `load_catalog()` 直接抛
`CatalogError`（`mimeconform/rules/__init__.py`）。所以下面每条 `hard` 都能在 `data/README.md` §三 指到同一节号
**并且**该子项确实留了原句。

**未录清单（本轮现状，`data/README` §7.1）**：R10（RFC 2231 §3/§4/§4.1 全行）、R11（RFC 2045 §2.7/§2.8/§6.1 全行）、
R3 的 §6.2 子项、R4 的 §4.1/§4.2 子项、R7 的 delimiter 形态与 preamble/epilogue 子项、R9 的「base64 行 ≤76」子项。
**对应规则一律只出 `note`**，直到补上逐字摘录（届时同笔改 `data/README` §三、`rfc-ledger.json`、`catalog.json`、本文）。

---

## 二、B 簇 · boundary / multipart 树（`scan.py`，里程碑 M2）

| rule_id | 判定 | class | severity | 台账行 / 子项 | 正例 | 负例 | 常见误报与规避 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B01 | `multipart/*` 缺 `boundary` 参数 | hard | blocker | R6 `#boundary-required` | `b-no-boundary` | — | 空值 `boundary=""` 等价于缺失（显式判，不当合法） |
| MC-B02 | `boundary` > 70 字符（不含前导 `--`） | hard | minor | R6 `#boundary-max-70` | `b-boundary-long` | `b-clean-nested` | 只数 boundary 本身，不数 `--` |
| MC-B03 | delimiter 未出现在行首 | diff | note | R7 `#delimiter-at-line-start`（未录） | `b-delim-not-bol` | — | **只在已进入某 multipart 且该行匹配某 ancestor boundary 前缀时**才判；正文里恰好 `--` 开头不报 |
| MC-B04 | close-delimiter 形态错误 | diff | note | R7 `#close-delimiter-form`（未录） | `b-close-malformed` | — | `--b--` 后只允许可忽略 LWSP |
| MC-B05 | 缺 final boundary | diff | note | `none-by-design` | `b-no-final` | — | 与 MC-B06 **互斥**：复用 boundary 时父级不登记 B05（`plan/03` §一） |
| MC-B06 | 嵌套复用同一 boundary | hard | major | R7 `#nested-boundary-distinct` | `b-inner-dup` | `b-clean-nested` | boundary 比较**按字节**、不折叠大小写；必须同时给两棵候选树 |
| MC-B07 | 存在 preamble | diff | note | R7 `#preamble-epilogue-ignored`（未录） | `b-preamble-epilogue` | — | 只有可见内容才算；纯 CRLF 不算 |
| MC-B08 | 存在 epilogue | diff | note | 同上（未录） | `b-preamble-epilogue` | — | 同上 |
| MC-B09 | 嵌套深度 > `--max-depth` | gray | note（`--strict-depth` → minor） | `none-by-design`（§7.6 策略项） | `b-deep-nest` | — | `class` 恒为 `gray`；用户加开关只提 severity |
| MC-B10 | `multipart/*` 无任何 body part | diff | note | `none-by-design` | `b-empty-multipart` | — | 依据只有标准库 `MultipartInvariantViolationDefect` 的实现事实，无明文条款 |

**B 簇的两条结构性纪律**

1. **MC-B05 × MC-B06 互斥**（M2 定）：父 multipart 的子节点里有"复用 boundary 并吸收父区域余量"的节点时，父级不再登记 B05。
   理由：那时父级 close-delimiter 的归属本身有歧义（`divergence` 已声明），再报"缺 final boundary"等于对同一段字节给出两条互斥结论。
2. **MC-B06 必须附歧义说明**：`class=hard` 是"复用确实违反 R7 原句"，但字节层无法唯一确定 close-delimiter 归属
   （cpython #69914）。报告同时给两棵树，**不替用户选一个**。

---

## 三、H 簇 · 头编码（`headers.py`，里程碑 M3）

| rule_id | 判定 | class | severity | 台账行 / 子项 | 正例 | 负例 | 常见误报与规避 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H01 | encoded-word > 75（按编码后字节） | hard | minor | R1 `#ew-length-75` | `h-ew-long` | `h-clean-folded` | 按**字节**计，不按字符；不含 `Subject: ` 前缀 |
| MC-H02 | 含 encoded-word 的头行 > 76 | hard | minor | R2 `#header-line-76` | `h-ew-line-long` | `h-clean-folded` | 只判**行内含 encoded-word 起点**的行；行宽不含 CRLF |
| MC-H03 | encoded-word 内部出现空白（非折行） | hard | minor | R3 §2 子项 `#ew-inner-space-forbidden` | `h-ew-space` | `h-clean-folded` | 与 MC-H12 **互斥**：折行时 H03 只进 `related` |
| MC-H04 | Q 编码 `=HH` 不合法 | diff | note | R4 `#q-encoding-syntax`（未录） | `h-q-invalid` | `h-clean-folded` | `_` 表示空格，合法；只认 `=` 后非两位十六进制 |
| MC-H05 | B 编码长度非 4 的倍数 | diff | note | R4 `#b-encoding-length-4`（未录） | `h-b-length` | `h-clean-folded` | 只数字符数，不先解码 |
| MC-H06 | encoded-text 跨 encoded-word 续写 | hard | major | R4 §5 `#no-continuation-across-ew` | 见下方构造说明 | `h-clean-folded` | **只认"前段自身不完整、拼接后完整"**；相邻完整 token 之间只有 FWS 是合法折叠 |
| MC-H07 | 头行 > 998 octets | hard | major | R5 `#line-max-998` | `h-line-998` | — | 判定**先于** encoded-word 检查（§7.5 第 1 条）；值不含 CRLF |
| MC-H08 | 头值含未编码非 ASCII | diff | note | `none-by-design` | `h-8bit-header` | — | 落在 encoded-word 跨度内的八位组不判（那是 token 内部的畸形，另算） |
| MC-H09 | 2231 续行缺 `*0` / 前导零 / 跳号 | diff | note | R10 §3（未录） | `h-2231-seq` | `h-2231-quote`（形合但编号全） | 同一参数按 §7.5 第 3 条**只记第一处**（前缀坏了后续判定无意义） |
| MC-H10 | `charset'language'value` 单引号不全 | diff | note | R10 §4（未录） | `h-2231-quote` | `h-2231-seq` | 少于两个 `'` 才判；空 language 是合法的 `UTF-8''x` |
| MC-H11 | `%HH` 转义非法 | diff | note | R10 §4.1（未录） | `h-2231-pct` | `h-2231-seq` | 只在扩展形态（含 `*`）上判；普通 `filename=` 不做百分号反转义 |
| MC-H12 | encoded-word 内部含折行 | diff | note | `none-by-design`（§7.5 第 2 条） | `h-ew-newline` | `h-clean-folded` | 命中即**不**报 H03，被压掉的进 `related` |

### 3.1 判定顺序（写死，§7.5 第 1–3 条；`tests/test_golden_engine_headers.py` 锁住）

```
头块切分（空行 / 非法字段名 / 无主续行 → 头块结束）
  └─ MC-H07  头行 > 998            ← 先于 encoded-word 检查
       └─ 逐 encoded-word：
            MC-H01（长度 > 75）
            MC-H12（内部有 CR/LF）──命中──▶ MC-H03 只进 related，且不再判 H04/H05
            MC-H03（内部有 SP/TAB，无折行）
            MC-H04（Q 非法转义）/ MC-H05（B 长度非 4 倍数）   ← 折行时跳过（同一字节不双记）
       └─ MC-H06（相邻 token 的续写，保守判定）
       └─ MC-H02（含 token 的行 > 76）
       └─ MC-H08（token 跨度外的非 ASCII 八位组）
       └─ 仅 Content-Type / Content-Disposition：
            MC-H09（编号：缺 *0 / 前导零 / 跳号）→ MC-H10（单引号）→ MC-H11（%HH）
```

### 3.2 MC-H06 为什么是 `hard` 但判定必须保守

R4 §5 的原句是 `'encoded-text' MUST NOT be continued from one 'encoded-word' to another.` —— 这是**全录**的 MUST NOT，
所以 `class=hard/major` 成立。但"相邻"本身不是证据：`=?UTF-8?Q?=E4=BD=A0=E5=A5=BD?=
 =?UTF-8?B?5LiA5Liq56S65L6L?=` 之间只有 FWS，是**完全合法**的折叠形态（`h-clean-folded` 就是它的负例基线）。
因此引擎只在"前一段自身不完整、与后一段拼接后才完整"时才判（Q 看末尾是否被切断的转义；B 看长度是否补齐到 4 的倍数）。
按"相邻即续写"判会把这题最该避免的东西——对合法折叠的误报——做出来。

### 3.3 MC-H08 / MC-H12 为什么是 `diff`

- **MC-H08**：RFC 2047 定义的是"非 ASCII 文本**怎么编码**"，它没有一条说"头值里出现 8bit 就是违规"。现实里有大量实现直传 8bit。
  无禁令可引 ⇒ `rfc = none-by-design`、`diff/note`。
- **MC-H12**：RFC 2047 §2/§6.2 说 encoded-word 内不得有空白、相邻 token 间 LWSP 显示时忽略，但**没有**规定
  "先折叠展开还是先解码"。两种顺序会得到不同结果（SO 52442469 正是这个形态）⇒ 实现分歧 ⇒ `diff/note`，并与 H03 互斥。

---

## 四、T 簇 · T 传输编码（`transfer.py`，里程碑 M4）

| rule_id | 判定 | class | severity | 台账行 / 子项 | 正例 | 负例 | 常见误报与规避 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T01 | 声明 CTE 与实际形态不符 | diff | note | `none-by-design`（§四.3） | `t-cte-mismatch` | `t-clean-b64` / `t-clean-qp` | **只在声明 `base64` 时判**（其它声明是兼容性超集，判"不符"会误报）；命中时**压掉** MC-T02/T03/T04 |
| MC-T02 | base64 填充非法（`=` 之后仍有数据字符 / 多于两个） | diff | note | R9 `#b64-padding`（未录） | `t-b64-pad` | `t-clean-b64` | 填充只允许出现在**末尾**且最多两个；落点 = 第一处非法 `=` |
| MC-T03 | base64 字符数不是 4 的倍数 | diff | note | R9 `#b64-length-multiple-of-4`（未录） | `t-b64-len` | `t-clean-b64` | 只数 base64 字符（含填充、不含字母表外字符）；落点 = 正文首字节 |
| MC-T04 | base64 出现字母表外字符 | hard | note | R9 `#b64-foreign-chars-ignored`（**全录**） | `t-b64-foreign` | `t-clean-b64` | 原句要求**忽略**该字符 → 出现本身**不违规**，故只出 `note`；落点 = 第一处字母表外字符 |
| MC-T05 | QP 编码行 > 76 octets | hard | minor | R8 `#qp-line-max-76` | `t-qp-long` | `t-clean-qp` | 行宽按 **octets**、不含 CRLF；软换行行宽**不计入下一行**；**含非法转义的行不记行宽**（那已不是 encoded line） |
| MC-T06 | QP 行末 `=` 之后已无下一行（悬空软换行） | hard | minor | R8 `#qp-soft-line-break` | `t-qp-soft` | `t-clean-qp` | 只钉"软换行之后无内容"这一硬形态；`=` 紧邻线性空白的形态更弱（见 4.3） |
| MC-T07 | QP 非法转义（`=` 后不是两位十六进制） | hard | major | R8 `#qp-illegal-escape`（全录 + **推导**，见 4.2） | `t-qp-artifact` | `t-clean-qp` | **每处非法转义各记一条**（精确到字节偏移）；软换行 `=` 与合法 `=HH` 不判 |
| MC-T08 | 未知 CTE 取值 | diff | note | `none-by-design` | `t-cte-unknown` | `t-clean-b64` | 只在 {7bit,8bit,binary,quoted-printable,base64} 之外触发；命中后**不再交叉校验**（§7.5 第 5 条）；落点 = CTE 头行行首 |
| MC-T09 | 7bit/8bit 正文行 > 998 octets | diff | note | R11 `#7bit-line-max-998`（未录） | `t-7bit-long` | — | 只判 7bit/8bit（含缺省 7bit）；落点 = 该行行首 |
| MC-T10 | 未声明 CTE（缺省 7bit）但正文含 8bit | diff | note | R11 `#default-cte-7bit`（未录） | `t-undeclared-8bit` | — | 只在**没有** CTE 头时判；落点 = 第一处 8bit 字节 |
| MC-T11 | QP 二次编码残留（解码一遍后仍见字面 `=HH`） | diff | note | `none-by-design` | `t-qp-double` | `t-clean-qp` | `=3D` 在**编码态**合法；只在**解码后**仍见字面 `=HH` 时报；落点映射回编码位置 |

### 4.1 判定顺序（写死，§7.5 第 5 条；`tests/test_golden_engine_transfer.py` 锁住）

```
Content-Transfer-Encoding 取值（缺省视为 7bit）
  └─ MC-T08  取值未知？ ──命中──▶ 只出这一条，不再交叉校验
  └─ 声明 base64：
       观察形态 == base64？ ──是──▶ MC-T02（填充）/ MC-T03（长度）/ MC-T04（字母表外字符）
                            ──否──▶ MC-T01（声明 vs 实测不符）── 压掉 MC-T02/T03/T04
  └─ 声明 quoted-printable：
       MC-T05（合法 encoded line 行宽）→ MC-T06（悬空软换行）→ MC-T07（非法转义）→ MC-T11（二次编码残留）
  └─ 声明 / 缺省 7bit、8bit：
       MC-T09（正文行 > 998 octets）
  └─ 未声明 CTE 且正文含 8bit：MC-T10
```

### 4.2 MC-T07 为什么是 `hard`（推导链 + 保守开关，`plan/06` Q1）

R8（RFC 2045 §6.7）**全录**了两句原句：`encoded lines be no more than 76 characters long.` 与
`An equal sign as the last character on an encoded line indicates such a non-significant ('soft') line break.`。
第二句把 `=` 在 QP 编码体里的**唯一合法语义**限定为两种：**行末软换行**，或**`=HH` 转义**。
`=u`（`=ustomers` / `=ure`）与 `=o:`（`=o:p>`）两者都不是 ⇒ **推导**出它违反 §6.7。这是**推导**而非逐字原句，
故 `catalog.json` 里 MC-T07 的 `ledger_key` 指到 `RFC2045-6.7#qp-illegal-escape`（该子项确实留了原句），
`class=hard/major`。

**保守开关（审阅者要求更保守时）**：把 `catalog.json` 里 MC-T07 的 `klass` 改为 `diff`、`severity` 改为 `note`
（同笔改本文与 `tests/test_golden_engine_transfer.py` 中对应断言）。改后仍报 MC-T07，只是不再当作 MUST 级违规。

### 4.3 MC-T01 的判据范围与"实测形态"口径（M4 落地决定）

- **只在声明 `base64` 时做交叉校验**：`quoted-printable` / `7bit` / `8bit` / `binary` 是**兼容性超集**——
  纯 ASCII 正文既可能是 QP 也可能是 7bit（`t-qp-long` 的 80 个 `a` 就是这种双关）。对这些声明判"不符"必然误报，
  故不做。base64 是唯一"由字节形态唯一决定"的声明，判据清晰。
- **"实测形态"的判定（`observe_body_shape`）**：`empty`（无内容）/ `binary`（含 8bit）/ `base64`
  （**行内无 SP/TAB** 且全 ASCII —— 字母表外字符按 §6.8 忽略，仍算 base64）/ `qp`（行内有空白且含 `=`）/ `text`。
  **分界线是"行内空白"**：base64 的编码行不含内部空格，而一段英文正文词间都有空格 ⇒ 判 `text`（`t-cte-mismatch`）。
- 这是**语义层判定**（`rfc = none-by-design`），`class` 恒为 `diff`，`severity` 恒为 `note` —— 不影响退出码。

---

## 五、簇覆盖总览（如实标注，不占位成"已完成"）

| 簇 | 模块 | 规则数 | 状态 |
| --- | --- | --- | --- |
| B boundary / multipart 树 | `scan.py` | 10 | ✅ 里程碑 M2 |
| H 头编码（2047 / 2231） | `headers.py` | 12 | ✅ 里程碑 M3 |
| T 传输编码 | `transfer.py` | 11 | ✅ 里程碑 M4 |
| A 归属与引用 | `attribution.py` | 8 | ✅ 里程碑 M5 |
| C 容器 | `container.py` | 5 | ✅ 里程碑 M5 |
| 扩展项（`--explain` / `--fix-plan` / SARIF） | — | — | ⬜ 不进首期判定路径（`plan/01` §二） |

---

## 六、A 簇 · 归属与引用（`attribution.py`，里程碑 M5）

> **全部 `diff/note`（D11）**：`Content-Disposition` 与 `multipart/related` 的正式定义不在五部 RFC 内
> ⇒ `rfc = none-by-design`，台账无原句可引。`filename` 取值顺序**先 RFC 2231（含续行）再 RFC 2047**
> （`plan/00` D10，`headers.decode_filename`，`attribution` 是它的调用点）。

| rule_id | 判定 | class | severity | 台账行 / 子项 | 正例 | 负例 | 常见误报与规避 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-A01 | 文本附件被当正文（text/* 带 name/filename 却缺 disposition，且同父有 text/plain 正文候选） | diff | note | `none-by-design` | `a-body-attach` | `a-clean-mixed` | 只对带 `name`/`filename` 的 text/* 触发；`text/html` 与 `text/plain` 并列不报（`b-wrapped-header`）；`multipart/alternative` 整簇跳过 |
| MC-A02 | `name` 与 `filename` 不一致 | diff | note | `none-by-design` | `a-name-mismatch` | `a-clean-mixed` | 两个字段都出现且**解码后**不同才报；只有一个时无事 |
| MC-A03 | 声明了 disposition 却无任何 filename / name（下游 Noname） | diff | note | `none-by-design` | `a-noname` | `a-clean-mixed` | 只有 attachment/inline 才算"声明了 disposition"；无 disposition 的归 A01/A08 |
| MC-A04 | 正文 `cid:` 引用无对应 Content-ID | diff | note | `none-by-design` | `a-cid-open` | `a-clean-mixed` | 比较按**尖括号内字面值、不 URL 解码**；同一字面值只记首次出现 |
| MC-A05 | `multipart/related` 的 `start` / `type` 与实际首部件不一致 | diff | note | `none-by-design` | `a-related-start` | `a-clean-mixed` | `start` 缺省时取首部件；只在显式给出且不指向首部件时记；每节点最多一条 |
| MC-A06 | `message/rfc822` 转发体没有 disposition | diff | note | `none-by-design` | `a-rfc822` | `a-clean-mixed` | 只看转发体节点自身；内层消息的头块另算 |
| MC-A07 | `inline` 却无 Content-ID | diff | note | `none-by-design` | `a-inline-nocid` | `a-clean-mixed` | 只有 inline 触发（attachment 不要求 Content-ID） |
| MC-A08 | 多个叶节点都无可判定 disposition，且无 text/plain 正文候选 | diff | note | `none-by-design` | `a-no-disposition` | `a-clean-mixed` | 有正文候选时归属**可判定**，不报；登记在 multipart 节点上 |

### 6.1 保守判定的三条纪律

1. **A01 需要"像附件"的证据**：叶节点自身带 `name`/`filename` 参数。没有名字的 `text/html`
   与 `text/plain` 并列是**合法的正文并置**（`b-wrapped-header` 就是这一形态，误报它会打挂负例）。
2. **A08 需要"整棵树没法判"**：至少两个叶节点、全部缺可判定 disposition、且没有 `text/plain`
   正文候选。有候选时归属是可判定的（`a-body-attach` 因此只出 A01，不出 A08）。
3. **`cid:` 只做字面比较**：不做 URL 解码、不做大小写折叠。

---

## 七、C 簇 · 容器（mbox / Maildir，`container.py`，里程碑 M5）

> **全部 `diff/note`（D3）**：`>From` 转义是 **mboxo 约定，不是 RFC**；mboxrd / mboxcl 的规则互不相同。
> 报告**必须同时输出三种读法的切分表**（`split_variants`），`auto` 只决定主表是哪一份。
> 偏移口径：容器层用 `message-relative`（从该消息 `From ` 行首起），文件级偏移见切分表 `file_offset`。

| rule_id | 判定 | class | severity | 台账行 / 子项 | 正例 | 负例 | 常见误报与规避 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-C01 | `From ` 分隔行无法解析（缺日期字段） | diff | note | `none-by-design` | `c-from-bad` | `c-clean-mbox` | 判据 = 地址之后必须有带数字的日期字段；该行仍被当作消息边界，不再叠报其它容器规则 |
| MC-C02 | 正文里 `From ` 行未转义 → 各变体切分表不一致 | diff | note | `none-by-design` | `c-from-unescaped` | `c-clean-mbox` | 只在"其它变体在此切分、主表不切"时触发；正确转义（`>From `）不报 |
| MC-C03 | 零长度消息（两条分隔行之间 0 字节） | diff | note | `none-by-design` | `c-empty-msg` | `c-clean-mbox` | 空消息仍占一个 `msg#N` 序号（序号不回收） |
| MC-C04 | 正文含裸 `From ` 行被误当分隔行（片段不具备头块） | diff | note | `none-by-design` | `c-body-from` | `c-clean-mbox` | 与 C02 的分工：C02 = 变体**不一致**；C04 = 三种读法**一致**误切且片段不成消息 |
| MC-C05 | Maildir `cur/` 条目名缺 `:2,<flags>` 信息段 | diff | note | `none-by-design` | `c-maildir-name` | `c-clean-mbox` | 只对 `cur/` 触发（`new/` / `tmp/` 无信息段要求）；规则作用于文件名 → `offset=0` 是占位 |

### 7.1 `auto` 的判定（§7.7 纯字节规则，不打分）

```
文件内出现 `Content-Length:` 头 → 主表 mboxcl
否则出现 `>From ` 且无 `>>From ` → 主表 mboxo
否则 → 主表 mboxo
```
**三种读法的切分表全部写进报告**（`split_variants`）；缺陷只从主表产出。切换主表（`--mbox-variant`）
会改变"哪条消息算一条"——这正是 C02 存在的意义：**变体差异是证据，不是某一种读法错了**。

---

## 八、机器断言清单（本文与 catalog 的一致性由谁保证）

| 断言 | 位置 |
| --- | --- |
| 本文的规则数 == `catalog.json` 的规则数 | `tests/test_catalog_doc.py::test_doc_covers_every_catalog_rule` |
| 本文表里的 `class` / `severity` 逐值 == catalog | `tests/test_catalog_doc.py::test_doc_class_and_severity_match_catalog` |
| `catalog.json` 的 `MC-B0x` 五字段 == `scan._RULE_META` | `tests/test_catalog_consistency.py::test_meta_matches_catalog_verbatim[scan]` |
| `catalog.json` 的 `MC-H0x/1x` 五字段 == `headers._RULE_META` | `tests/test_catalog_consistency.py::test_meta_matches_catalog_verbatim[headers]` |
| `catalog.json` 的 `MC-T*` 五字段 == `transfer._RULE_META` | `tests/test_catalog_consistency.py::test_meta_matches_catalog_verbatim[transfer]` |
| `catalog.json` 的 `MC-A*` 五字段 == `attribution._RULE_META` | `tests/test_catalog_consistency.py::test_meta_matches_catalog_verbatim[attribution]` |
| `catalog.json` 的 `MC-C*` 五字段 == `container._RULE_META` | `tests/test_catalog_consistency.py::test_meta_matches_catalog_verbatim[container]` |
| `detector` 能在声明的 `module` 里解析到 | `tests/test_catalog_consistency.py::test_detector_resolves_in_its_module` |
| 原句门禁（`hard` 必须有逐字原句） | `mimeconform/rules/__init__.py::load_catalog` + `tests/test_catalog_gate.py` |
| 语义层规则永不 `hard` | `tests/test_catalog_gate.py::test_semantic_rule_cannot_be_hard` |

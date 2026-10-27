# data · 依据查证、RFC 条款台账、数据源可获取性与数值口径

> **本文件是本题「数值口径」的唯一真相源**（§七）。`plan/01`、`plan/03` 与代码里的定义均为便于阅读的摘录；若与 §七 冲突，以 §七 为准，并在同一提交内修正摘录。
> **基准日**：2026-10-27。**代理实际检索窗口**：**2026-10-27T10:56Z–11:04Z**。
> 星数 / `total_count` 均为**该窗口内一次性快照**，会随时间漂移，只用于说明生态位，**不得写进代码常量或断言阈值**。

---

## 一、三态图例与检索边界

| 标记 | 含义 |
|---|---|
| ✅ | 已核对：官方文档 / RFC 原文可逐字指到节号，或 issue 原话可直连 |
| 🟡 | 部分核对：条款给到 RFC 号 + 节号但本轮未逐字摘录原句（**这类条目不得单独作为 `hard` 依据**） |
| ⬜ | 软论据或未取得（登记获取路径与阻断原因），**不得用确定语气** |

### 1.1 检索边界（如实登记）

- **Reddit 不可达**：本轮 Reddit 直连**超时（ConnectTimeout）**，**未取得任何 Reddit 证据**。本题需求证据全部来自 **StackOverflow API + Hacker News Algolia + cpython issue**，**不含 Reddit 引用**；`plan/01` 与 README 均不出现 Reddit 论据。
- **开源空白检索**用 `gh api` 搜索接口，`total_count` 为检索当日快照，属**软论据**（无结果不等于不存在，也可能只是命名不重合）。
- **星数为检索当日快照**，同属软论据。
- 本轮**不含**任何 RFC 之外的规范（无第三方邮件格式白皮书、无厂商私有规范）——凡不在下表 11 条内的现象，一律只能落 `diff` / `gray`。

### 1.2 开源空白检索（⬜ 软论据，窗口 2026-10-27T10:56Z–11:04Z）

| 检索式 | total_count | 头部 / 说明 |
|---|---|---|
| `mime parser` | **387** | MimeKit 2010★ / mailparser 1673★ / flanker 1646★ —— **均为解码器非审计器** |
| `eml parser` | **323** | GOVCERT-LU/eml_parser 246★ 为**钓鱼/头部向**，触及认证语义，已按切割声明排除 |
| `mbox parser` | **141** | MimeKit 2010★、gmime 142★、emersion/go-mbox 77★、robertklep/node-mbox 72★ —— 全是"切分+解码"，无 `From ` 转义审计 |
| `rfc2047` | **29** | One-com/rfc2047 20★、rfc2047-decoder 13★、rfc2047-ruby 12★ —— **全是编解码小库，不做合规判定** |
| `rfc2231` | **4** | One-com/rfc2231 3★、RFC5987 1★、`gy-vs/mime-rfc2231-params-core` **0★**（描述 "refuses ambiguity: quoted boundaries, duplicate parameter…"，最接近审计语义但 0★ 无生态）、mediatype-param-fold 0★ |
| `content-transfer-encoding` | **61** | 头部**全为无关**（FTC 机器人 / CVPR 论文 / 矩阵运算）；仅 `mathiasbynens/quoted-printable` 96★ 是 JS QP 库，**只编解码不审计**；`Hxzeroone/quoted-printable-Parser` 30★ 是 Burp 插件，**认证/攻击向** |
| `mime structure validator` | **4** | 最高 1★；余为 MHTML / VAST / 上传校验 / 文档校验，**全无关** |
| `mbox validator` | **5** | 最高 118★ 是 Termux 命令清单误命中；余 4/1/0/0★ |
| `maildir mbox converter` | **5** | 最高 1★ |
| **`mime compliance checker`** | **0** | ⬜ 软论据 |
| **`mime defect parser`** | **0** | ⬜ 软论据 |
| **`email mime conformance`** | **0** | ⬜ 软论据 |
| **`mime tree audit scanner`** | **0** | ⬜ 软论据 |
| **`multipart boundary checker`** | **0** | ⬜ 软论据 |

**另一条对照**：`ronomon/mime` **63★**（JS，*"standards-compliant MIME decoder … extensive tests and fuzz tests"*）是最接近"严格解码"的实现，但**是解码器且 2020-09 后归档**；`andris9/mailsplit` **25★**（只切分不审计）。

**判定（⬜ 软论据）**：解码器红海，**"带 RFC 条款引用的结构缺陷账本"未检索到**。0 结果一律按软论据处理：**只写"未检索到"，不得写"首创 / 无人做过"**。

### 1.3 Python 标准库缺陷类（✅ 官方文档）

| 类 | 说明 |
|---|---|
| `NoBoundaryInMultipartDefect` | multipart 缺 boundary |
| `StartBoundaryNotFoundDefect` | 找不到起始 boundary |
| `CloseBoundaryNotFoundDefect` | **找不到结束 boundary —— 记缺陷后继续解析**（"容忍"是设计选择） |
| `MultipartInvariantViolationDefect` | multipart 不变量被破坏（如无子部件） |
| `InvalidBase64PaddingDefect` | base64 填充非法 |
| `InvalidBase64CharactersDefect` | base64 出现字母表外字符 |
| `InvalidBase64LengthDefect` | base64 长度非法 |

- 官方原句：**"the defects are added to the message where the problem was found"** → **只记录，不报告、不计数、不打分、不退出非零**。
- **清单中不存在**"`Content-Transfer-Encoding` 声明与实际不符"这一类（✅ 逐条核对）→ CTE 交叉校验在标准库里是**空位**。
- 最难的缺口：**内层 boundary 重复**被错处理（cpython #69914，**open**，6 评论）。

### 1.4 需求侧证据（✅ 逐条原话，窗口 2026-10-27T10:56Z–11:04Z）

| 编号 | 原话（未改写） | 来源 |
|---|---|---|
| DS-69914 | "email parser ignores inner multipart boundary when outer message duplicates it"（open，6 评论） | https://github.com/python/cpython/issues/69914 |
| DS-56141 | "Email multipart boundary detection fails on a wrapped header"（closed） | https://github.com/python/cpython/issues/56141 |
| DS-93376 | "mailbox.mbox malformed 'From ' lines not being detected/handled"（open，9 评论） | https://github.com/python/cpython/issues/93376 |
| DS-73239 / 86599 / 90040 | 同类 mbox 缺陷（均 open） | https://github.com/python/cpython/issues/73239 · /86599 · /90040 |
| SO-6255202 | "**when someone sends an email with a text attachment, the contents of the text file shows up for the 'body' variable**"（12 赞，2 答） | https://stackoverflow.com/questions/6255202 |
| SO-39328935 | "Why doesn't my embedded image display in Gmail or Office 365?"（3 赞） | https://stackoverflow.com/questions/39328935 |
| SO-34387345 | "**attachment can be seen in all email clients except iOS**"（2 赞） | https://stackoverflow.com/questions/34387345 |
| SO-44154520 | "**attachment file names arrive are in gibberish**"；实样 `name*="UTF-8''%D7%A2%D8%A8..."` / `filename*=UTF-8''%D7%A2...`（**缺 `*0` 序号**）；答者判语 "This is a totally invalid mime header"（3 赞） | https://stackoverflow.com/questions/44154520 |
| SO-52442469 | encoded-word 内**嵌了换行** `=?UTF-8?Q?=C3=A5 =C3=A4?=`；"Are newlines in MIME headers using encoded-words legal?"（2 赞） | https://stackoverflow.com/questions/52442469 |
| HN-26737934 | "sometimes with **attachments with the file name also encoded in SJIS, which results in funny mojibake when saving them to disk**" | https://news.ycombinator.com/item?id=26737934 |
| SO-34668240 | "Email an attachment with non-ascii filename with python email"（5 赞） | https://stackoverflow.com/questions/34668240 |
| SO-5622660 | "Attaching file to an email in python leads to a blank file name?"（10 赞） | https://stackoverflow.com/questions/5622660 |
| SO-79133579 | "We request all our **=ustomers** … =o:p> … please make **=ure**"（QP 伪影样张） | https://stackoverflow.com/questions/79133579 |
| SO-14937196 | "users of Outlook … receive notifications with **equal '=' characters at end of the lines and with broken HTML** … problem with 'soft line breaks'" | https://stackoverflow.com/questions/14937196 |
| SO-6029218 | "sending zip as base64-encoded attachment **corrupts archive**"（3 赞） | https://stackoverflow.com/questions/6029218 |
| SO-51286182 | "**Sendgrid Attachment Corrupted**" | https://stackoverflow.com/questions/51286182 |
| SO-12816042 | "PDF attachment … is called **'Noname'**"（缺 filename 参数，3 赞） | https://stackoverflow.com/questions/12816042 |
| SO-24246391 | "message-text always **goes into attachment**" | https://stackoverflow.com/questions/24246391 |
| SO-10107788 | "how to set a name of the embedded image"（related/cid 归属，4 赞） | https://stackoverflow.com/questions/10107788 |
| HN-32979369 | "**Never heard of the '>From' problem? :) mbox has a well-documented escaping problem -- many tools which parse mbox files will mistake a line which begins…**" | https://news.ycombinator.com/item?id=32979369 |
| HN-6855700 | "**Failure to properly escape such lines was an infamous bug with Mail.app's mbox exporter**" | https://news.ycombinator.com/item?id=6855700 |

> **证据缺口（如实记录）**：Reddit 超时，无 Reddit 原话。若后续取得，须单列一行并重新评估规则覆盖，不得直接并入现有 21 条。

---

## 二、数据源可获取性记录

| 数据源 | 三态 | 获取方式 | 备注 / 阻断原因 |
|---|---|---|---|
| RFC 2045 / 2046 / 2047 / 2231 / 5322 原文 | ✅ 已获取 | 逐条打开原文核对，节号 + 原句照抄（§三） | 基准日 2026-10-27；若链接失效，按"原句已存档于本文件"处理，**不重新编造** |
| Python `email.errors` 官方文档 | ✅ 已获取 | 官方文档页 | 缺陷类清单 + 原句 |
| cpython / SO / HN 需求原话 | ✅ 已获取（21 条） | 逐条直连核对 | 见 §1.4 |
| 生态快照（星数 / total_count） | ✅ 已获取（一次性快照） | GitHub API / 仓库页 | 时间戳见页首；数字漂移，属 ⬜ 软论据 |
| **外部邮件语料（真实 `.eml` / `.mbox`）** | ⬜ **不使用** | — | 隐私风险，且不得入仓；语料一律程序化合成（§六） |
| **Reddit 需求讨论** | ⬜ **不可获取** | 直连超时（ConnectTimeout） | **不作底座、不作论据** |
| **其他邮件客户端实测（Outlook / Gmail / iOS / Thunderbird）** | ⬜ 未实测 | — | 本题只做字节层判定，不承诺"某客户端会如何显示"；如需引用须先实测，不得据 SO 转述写成已实测 |
| **RFC 之外的规范（`Content-Disposition`、`multipart/related` 的正式定义）** | ⬜ 未核对 | — | 因此 M4 全部规则**只能 `diff` / `gray`**（见 §四.3） |
| 真实邮件的高嵌套深度样本 | ⬜ 未取得 | — | 深度是策略项，不依赖实测（§7.6） |
| 性能基线（大 mbox 体积/耗时） | ⬜ 未取得 | 尚无实现 | 以 M5 末态回填，不写死数字 |

---

## 三、RFC 条款原句台账（✅ 节号已逐条核对；原句留档状态逐行标注）

> **本节是 `hard` 判定的唯一依据。** 任何 `hard` 规则必须在此指到同一 RFC 号 + 节号，**并且该行的"原句留档"必须覆盖它所判定的那一条**。指不到、或原句未留档 ⇒ 只能 `diff` / `gray`（见 §7.1 门禁）。
> 「性质」列：**硬规则** = 有 MUST / MUST NOT / 明确数值上限的规定。
> 「原句留档」列：**全录** = 该行判定的每一条都附了逐字原句；**部分** = 部分子项只有节号、无原句（对应子项在补齐前只能出 `note`）；**未录** = 只有号 + 节号，本轮未逐字摘录（**该行整体不得支撑 `hard`**）。

| # | 规则 | 出处（RFC 号 + 节号） | 原句 | 性质 | 原句留档 |
|---|---|---|---|---|---|
| R1 | encoded-word **≤75 字符**（含 charset / encoding / encoded-text 与分隔符） | RFC 2047 §2 | "An 'encoded-word' may not be more than 75 characters long, including 'charset','encoding','encoded-text', and delimiters." | 硬规则 | **全录** |
| R2 | 含 encoded-word 的头行 **≤76 字符** | RFC 2047 §2 | "each line of a header field that contains one or more 'encoded-word's is limited to 76 characters." | 硬规则 | **全录** |
| R3 | encoded-word 内禁止空白；相邻 encoded-word 之间的 LWSP 显示时忽略 | RFC 2047 §2 / §6.2 | §2：见 R1 所在节；§6.2：相邻 encoded-word 间的 LWSP **显示时忽略**（本节号已核，本轮**未逐字摘录原句**） | 硬规则 | **部分**（§6.2 子项未录 → 对应判定暂只出 `note`；**折叠与解码顺序是实现差异**，见 §四.5） |
| R4 | Q 编码用 `=HH`、空格可写 `_`、字面排除 `= ? _`；B 编码 = RFC 2045 base64，**长度 4 的倍数**；encoded-text 不得跨 encoded-word 续写 | RFC 2047 §4.1 / §4.2 / §5 | §5："'encoded-text' MUST NOT be continued from one 'encoded-word' to another."；§4.1（Q 编码）/ §4.2（B 编码）**本轮未逐字摘录原句** | 硬规则 | **部分**（§5 子项全录 = MC-H06 可 `hard`；§4.1/§4.2 子项未录 → MC-H04/MC-H05 在补摘录前只出 `note`） |
| R5 | 正文 / 头行 **≤998 字符**（SHOULD ≤78） | RFC 5322 §2.1.1 | "Each line of characters MUST be no more than 998 characters, and SHOULD be no more than 78 characters, excluding the CRLF." | 硬规则 | **全录** |
| R6 | multipart **必须**有 boundary；boundary **≤70 字符** | RFC 2046 §5.1.1 | "The Content-Type field for multipart entities requires one parameter, 'boundary'." / "must be no longer than 70 characters, not counting the two leading hyphens." | 硬规则 | **全录** |
| R7 | delimiter `--boundary`（须在行首）、close `--boundary--`；preamble / epilogue **必须忽略**；**嵌套必须用不同 boundary** | RFC 2046 §5.1.1 / §5.1.2 | 嵌套："each nested 'multipart' entity uses a different boundary delimiter."；delimiter 形态与 preamble/epilogue 忽略义务**本轮未逐字摘录原句** | 硬规则 | **部分**（嵌套子项全录 = MC-B06 可 `hard`；MC-B03/B04/B07/B08 在补摘录前只出 `note`） |
| R8 | QP 行 **≤76 字符**；软换行 = 行尾 `=` | RFC 2045 §6.7 | "encoded lines be no more than 76 characters long." / "An equal sign as the last character on an encoded line indicates such a non-significant ('soft') line break." | 硬规则 | **全录** |
| R9 | base64 行 ≤76 字符；**字母表外字符须被忽略** | RFC 2045 §6.8 | "Any characters outside of the base64 alphabet are to be ignored in base64-encoded data." | 硬规则 | **部分**（"字母表外字符忽略"全录 = MC-T04 可 `note`；"base64 行 ≤76"子项未逐字摘录 → 该子项只出 `note`。另："忽略"正是宽松实现来源，见 §四.2 附注） |
| R10 | 参数续行 `name*0` / `name*1` **不得前导零或跳号**；`charset'language'value` 中**单引号必须存在**；`%HH` 转义 | RFC 2231 §3 / §4 / §4.1 | §3（续行编号）/ §4（编码形式与单引号）/ §4.1（百分号转义）**本轮仅核对节号与语义，未逐字摘录原句** | 硬规则 | **未录** → MC-H09 / MC-H10 / MC-H11 在补摘录前**只能出 `note`**，不得出 `hard` |
| R11 | 7bit / 8bit 行 ≤998 octets；**未声明 CTE 默认 7bit** | RFC 2045 §2.7 / §2.8 / §6.1 | §2.7/§2.8 定义 7bit/8bit 行限制；§6.1 规定缺省 CTE 为 7bit（**仅核对节号与语义，未逐字摘录原句**） | 硬规则 | **未录** → MC-T09 / MC-T10 在补摘录前**只能出 `note`**，不得出 `hard` |

> **⚠️ 关于本表的诚实说明**：上表"原句留档"列就是本题**自己给自己上的门禁**。R10 / R11 两行以及 R3 / R4 / R7 / R9 的部分子项，本轮只做到了"节号 + 语义核对"，**没有逐字摘录原句**。按 §7.1，这些子项在 M1/M3 落地时必须先补齐摘录，**补齐前不得出 `hard`**。这不是"待办事项"，是"防止拿印象当条款"的机械约束——台账里没原句，代码里就不许报 `hard`。

**本表之外的引用一律禁止。** 尤其：**没有**任何关于"最大嵌套深度"的条款（✅ 反向核实 §5.1.1/§5.1.2）；**没有**任何关于"CTE 声明与实际交叉校验"的条款（✅ 反向核实 §6.1/§6.7/§6.8）；**没有**任何关于"mbox 容器格式"的条款（RFC 5322/2045/2046 均不定义 mbox）；**没有**任何关于"multipart 至少一个子部件"的明文条款（MC-B10 只能由 `MultipartInvariantViolationDefect` 的实现事实支撑，故在补摘录前只出 `note`）。

---

## 四、"实现差异 vs 硬规则"分界表

> 本节是本题的**价值所在**：这五格若强行写成"违规"，报告就会变成误报机器；写成"实现差异"，报告才可复核。**每一格都必须显式标注，不得沉默、不得升级为 `hard`。**

### 4.1 缺 final boundary（MC-B05 → `diff`）

- **RFC 只说什么**：RFC 2046 §5.1.1/§5.1.2 定义 delimiter 与 close-delimiter 的形态，**没有**规定"缺 close-delimiter 时如何处理"，也没有恢复规程。
- **实现分歧**：Python 记 `CloseBoundaryNotFoundDefect` **并继续解析**（宽容派）；严格解析器直接判错（严格派）。两者都可辩护。
- **为什么不能硬判**：没有条款可以引用。判"违规"就是编条款；判"合法"则是无视结构残缺。
- **本题怎么落**：`diff` + `note`，输出"树在第 N 字节被迫闭合"的字节位置，**不影响退出码**。

### 4.2 内层 boundary 与外层重复（MC-B06 → `hard`，但必须附歧义说明）

- **RFC 说得很明确**：R7 原句 "each nested 'multipart' entity uses a different boundary delimiter." → **复用同一 boundary 确实违反条款**，所以 `class=hard`。
- **但判定不能止于"违规"**：字节层无法唯一确定某个 close-delimiter 属于哪一层。Python 实测在此时错处理（cpython #69914）。
- **本题怎么落**：`hard/major` + **两棵候选树**（内层先闭合 / 外层先闭合）+ 两树差异位置。**不替用户选一个**（选了就是复刻标准库的错误）。
- **与 R9 的关系**：这格不是"忽略字符"那类宽松，而是"归属歧义"；因此可以 `hard`，但仍必须同时给出歧义说明。

### 4.3 `Content-Transfer-Encoding` 声明与实际不符（MC-T01 → `diff`，永不 `hard`）

- **RFC 只说什么**：§2.7/§2.8/§6.1 定义各 CTE 的语义与缺省值；§6.7/§6.8 定义 QP/base64 的编码形态。**没有任何"交叉校验"条款**（✅ 逐条核对）。
- **为什么不能硬判**：条款管的是"声明的编码怎么写"，不管"写完之后正文是不是真的按它编的"。要判"不符"，必须实现自己定义"实际编码"的识别算法——这是语义层，不是条款层。
- **本题怎么落**：`class=diff`，`rfc` 写 `none-by-design`，报告里显式写"语义层判定，非条款判定"。**这是本题最需要克制的一格**，也是"三值封闭"最好的试金石。

### 4.4 mbox `>From` 转义（MC-C02 → `diff`，且必须并出多变体）

- **事实**：`>From` 转义是 **mboxo 约定，不是 RFC**。mboxrd 反转义 `>From `、mboxcl 用 `Content-Length` 前缀，三者**互不兼容**。
- **为什么不能硬判**：同一段字节在三种读法下的"正确切分"不同。判一种"正确"必然误报另一种。
- **本题怎么落**：`diff` + **同时输出各变体切分表**（`--mbox-variant=mboxo|mboxrd|auto`）；`auto` 的判定规则写死在 §7.7，不做启发式打分。**这是本题硬规则最弱的一格**，README 必须写死这句话。

### 4.5 折叠发生在 encoded-word 解码之前还是之后（MC-H12 → `diff`）

- **事实**：RFC 2047 §2/§6.2 规定 encoded-word 内不得有空白、相邻 encoded-word 间 LWSP 显示时忽略，**但没有**规定"先折叠展开还是先解码"。
- **实现分歧**：先解码 → encoded-word 内部的折行会被当成字面字符（SO 52442469 的 `=?UTF-8?Q?=C3=A5 =C3=A4?=` 就落在这里）；先折叠 → 内部折行被吞掉，得到一个"看起来正常"的结果。
- **本题怎么落**：`diff/note`，**并与 MC-H03 互斥**（判定顺序见 §7.5），避免同一段字节被双记。

### 4.6 分界表小结

| 现象 | `class` | 能否引用条款 | 报告必须附带什么 |
|---|---|---|---|
| 缺 final boundary | `diff` | 否（无恢复规程条款） | 被迫闭合的字节位置 |
| 内层 boundary 重复 | `hard` | 是（R7） | **两棵候选树 + 差异位置** |
| CTE 声明 vs 实际不符 | `diff` | 否（无交叉校验条款） | `none-by-design` 说明 |
| mbox `>From` 变体 | `diff` | 否（非 RFC） | 各变体切分表 |
| 折叠 / 解码顺序 | `diff` | 否（RFC 未定） | 判定顺序声明（§7.5） |
| 最大嵌套深度 | `gray` | 否（RFC 无此规定） | `--max-depth` 策略值 + 默认不影响退出码 |

---

## 五、语料与样例矩阵（M1 产出结构，占位定义）

> 本节只定**矩阵形状**，不定具体文件名（文件名随 M1 落地）；`expect.json` 的字段定义见 §7.1 / §7.3 / §7.4 / §7.8（另 §7.2 规则编号）。

| 覆盖域 | case 前缀 | 正例（≥2） | 负例（≥1） |
|---|---|---|---|
| 树与边界 | `data/golden/b-*` | 缺 boundary / boundary 超 70 / delimiter 未在行首 / 内层复用同一 boundary / 缺 final boundary / 有 preamble+epilogue | 完好 `mixed`+`alternative` 嵌套 |
| 头编码 | `data/golden/h-*` | encoded-word >75 / 头行 >76 / encoded-word 内空白 / Q 编码非法 `=HH` / B 编码长度非 4 倍数 / `name*0` 跳号 / 缺单引号 / 非 ASCII 未编码 / 998 octets | 合法折叠的多 encoded-word（每个 ≤75、行 ≤76） |
| 传输编码 | `data/golden/t-*` | CTE 声明不符 / base64 长度非 4 倍数 / base64 非法填充 / QP 行 >76 / QP 非法转义（`=ustomers` 类）/ 行末 `=` 残留 / 7bit 行 >998 | 合法 base64（76 列 + 正确填充）/ 合法 QP（含真实软换行） |
| 归属与引用 | `data/golden/a-*` | 文本附件被当正文 / `name`≠`filename` / 缺 `filename` / `cid` 未闭合 / `related` 的 `start` 不符 / `message/rfc822` 归属 / `inline` 无 `Content-ID` | `mixed`（正文 + 2 附件）归属全对 |
| 容器（可选） | `data/golden/c-*` | 畸形 `From ` 行 / `>From` 未转义误切分 / 零长度消息 / 正文含 `From ` / Maildir 文件名不合规 | 干净 mbox（3 条消息 + 正确转义） |

每 case 目录固定三件：`msg.eml`（或 `mail.mbox`）、`expect.json`、`README.md`（来源标注 + 复现命令）。

---

## 六、合成数据纪律

1. **全部程序化生成**：`data/golden/` 下每个 case 由语料生成器产出，**不使用任何真实邮件**。
2. **确定性**：生成器不得读系统时间、不得依赖随机全局状态；同一生成器版本重跑必须产出**逐字节一致**的 `msg.eml` / `mail.mbox` 与 `expect.json`；`--check` 模式在 `git status` 上必须干净。
3. **白名单约定**：
   - 域名统一 `example.invalid`（RFC 2606 保留域，永不解析）；
   - 附件名用假名（`a.txt` / `报告.pdf` / `naïve.png` 等），**不含真实姓名、工号、机构**；
   - 地址用 `alice@example.invalid` / `bob@example.invalid`；
   - `Message-ID` / `Content-ID` 用固定假串（`<fixed-0001@example.invalid>`），便于逐字节比对；
   - **不生成**真实邮箱、真实附件内容、真实 IP、真实机构名。
4. **样本来源标注**：每 case 的 `README.md` 必须写清该 case 复现了哪条 issue / SO 原话（编号引用），或标注"自造边界样本（无外部来源）"。**不得把自造样本写成"来自某 issue 的原样文件"**。
5. **禁入真实数据的兜底**：`.gitignore` 全局排除 `*.eml` / `*.mbox`，仅对 `data/golden/**` 开例外；`fixtures/out/` 与本地输出目录排除。提交前 `git ls-files '*.eml'` 必须只列出 `data/golden/**` 下的合成样本。
6. **规模诚实**：golden 语料是**小型定向样本**（每类缺陷 2 正例 + 1 负例），**不是**语料库，**不得**描述为"经过了大规模邮件语料验证"。

---

## 七、数值口径纪律（**本题唯一数值真相源**）

> §7.x 只在本节定义。代码常量、`plan/01` 摘录、`docs/defect-catalog.md` 全部引用本节；**禁止第二套表述**。

### 7.1 `class` 三值（封闭，不可增第四值）

| 值 | 定义 | 判定条件 |
|---|---|---|
| `hard` | 有**逐字原句**留档支撑的硬规则 | `rfc` 字段必须指到 §三 的表行，**且该行的「原句留档」必须为「全录」或覆盖本条子项** |
| `diff` | RFC 无条款、或实现间存在可辩护分歧 | `rfc` 必须写 `none-by-design` 或"仅定义 X、未定义 Y" |
| `gray` | RFC 未规定的策略项（如最大嵌套深度） | 必须附策略参数名与默认值 |

- **升级禁令**：`diff` / `gray` **不得**在代码中被映射为 `hard`；测试须断言语义层规则集（MC-T01、MC-A01–A08、MC-C01–C05、MC-H08、MC-H12、MC-T08、MC-T11、MC-B05、MC-B09）全部 ≠ `hard`。
- **原句门禁（catalog 生成期强制，非人工纪律）**：`mimeconform/rules/catalog.json` 每条规则的 `rfc` 字段必须能被解析出一个 `(RFC 号, 节号)` 键，该键必须存在于 `data/rfc-ledger.json`（§三 的机读镜像，M3 产出）；**键不存在或该键的 `verbatim` 为 `null` 时，构建期直接失败**。这使"台账没原句 → 代码里报不了 `hard`"成为机械事实，而不是靠人记得。
- **当前未录清单（M1/M3 必须先补）**：R10（全行）、R11（全行）、R3 的 §6.2 子项、R4 的 §4.1/§4.2 子项、R7 的 delimiter 形态与 preamble/epilogue 子项、R9 的"base64 行 ≤76"子项。**对应规则在补齐前一律只出 `note`。**

### 7.2 规则编号语义（`rule_id`）

格式 `MC-<域><两位序号>`，域字母固定：

| 域 | 模块 | 例 |
|---|---|---|
| `B` | boundary / multipart 树 | `MC-B01` 缺 boundary、`MC-B06` 内层复用、`MC-B09` 深度（gray） |
| `H` | 头编码（2047 / 2231） | `MC-H01` encoded-word >75、`MC-H09` 续行跳号 |
| `T` | 传输编码（CTE） | `MC-T01` 声明不符（diff）、`MC-T03` base64 长度 |
| `A` | 归属与引用 | `MC-A01` 正文/附件归属、`MC-A04` cid 未闭合 |
| `C` | 容器（mbox / Maildir） | `MC-C01` 畸形 `From ` 行、`MC-C02` `>From` 变体 |

**编号一经分配不得复用/改义**；废止的规则保留编号并标 `retired: true`。

### 7.3 树路径 `path`（唯一定义）

- 根部件为 `0`；其子部件依次 `.1`、`.2`、…（**按字节出现顺序，从 1 开始**）。
- 例：`0`（根）→ `0.2`（第二个子部件）→ `0.2.1`（该子部件的第一个子部件）。
- 容器层：消息在容器内的序号写作 `msg#<n>`（`n` 从 1 开始，按 `From ` 分隔行出现顺序）；其内部路径追加为 `msg#3/0.1`。
- 路径**不做**任何重排、去重、大小写折叠。

### 7.4 严重度映射（`severity`，四档，与 `class` 正交）

| 值 | 含义 | 典型 |
|---|---|---|
| `blocker` | 结构无法建立，无法继续审计 | multipart 无 boundary 且无任何可用 delimiter |
| `major` | 结构可建立但违反 MUST 级条款，下游极易出错 | 内层 boundary 重复、base64 长度非 4 倍数、QP 非法转义 |
| `minor` | 违反数值/形态限制但影响可控 | 行宽超限、boundary 超 70、encoded-word 超 75 |
| `note` | 登记事实，不构成违规 | 字母表外字符（RFC 要求忽略）、preamble/epilogue 存在、`diff` 类现象的登记 |

映射表（规则 → 默认 severity）只存在于 `mimeconform/rules/catalog.json`，本节只定义**四档语义与判定原则**。

### 7.5 判定顺序（防双记，唯一定义）

同一段字节可能同时满足多条规则的触发条件。**顺序写死，先命中者记账，后命中者只在 `related` 里留引用**：

1. **头块切分**：先按行切分头块（以第一个空行结束）。头行 > 998（MC-H07）**先于** encoded-word 检查。
2. **encoded-word 内折行 vs 内空白**：先判"encoded-word 跨行"（MC-H12，`diff`）；命中则**不再**报 MC-H03（内空白）。理由：折行是"内部有空格"的一种成因，两者同时报会让同一字节出现两条账。
3. **RFC 2231 参数解码顺序**：先按 §3 合并续行（`name*0` / `name*1`…，判跳号/前导零）→ 再按 §4 解析 `charset'language'value`（判单引号缺失）→ 再按 §4.1 做 `%HH` 反转义（判非法转义）→ **最后**若结果仍含 encoded-word，才走 RFC 2047 解码。顺序不可交换。
4. **`filename` 取值**：先 RFC 2231（含续行）→ 再 RFC 2047。多个同名参数取**首个**并记 `duplicate_param`（不静默覆盖）。
5. **CTE 检查顺序**：先判"声明值是否已知"（MC-T08）→ 再判声明形态合法性（MC-T03/T04/T05）→ **最后**才判 `declared vs observed`（MC-T01）。理由：CTE 未知时无法做交叉校验。
6. **boundary 检查顺序**：先判 boundary 是否存在（MC-B01）→ 再判长度（MC-B02）→ 再判 delimiter 形态（MC-B03/B04）→ 再判嵌套复用（MC-B06）→ 最后判 final boundary 缺失（MC-B05）。理由：无 boundary 时后续全部无意义。

### 7.6 `--max-depth`（策略项，唯一定义）

- **默认值 `32`**，`class=gray`，`severity=note`，**默认不影响退出码**。
- `--strict-depth` 才把"超过 max-depth"计入退出码判定（此时仍 `class=gray`，但 severity 提为 `minor`）。
- **理由**：RFC 2046 §5.1.1/§5.1.2 **未规定最大嵌套深度**（✅ 反向核实）。任何硬编码上限都是策略。

### 7.7 mbox 变体判定（唯一定义）

- `--mbox-variant` 取值 `mboxo`（默认）/ `mboxrd` / `mboxcl` / `auto`。
- `mboxo`：`From ` 行即分隔行；`>From ` 保留转义不反转义。
- `mboxrd`：`>From ` 反转义为 `From `；`>>From ` 保持一层转义。
- `mboxcl`：优先使用 `Content-Length` 头切分，缺失时回落 `mboxo` 规则。
- `auto`：**纯字节规则，不打分**——若文件内出现 `Content-Length:` 头 → `mboxcl`；否则若出现 `>From ` 且无 `>>From ` → `mboxo`；否则 `mboxo`。**所有变体的切分表都写入报告**（`split_variants`），`auto` 只决定「主」表是哪一份。
- **报告必须写明**："`>From` 是 mboxo 约定，非 RFC；变体间互不兼容"。

### 7.8 结构指纹（唯一定义）

- **`fingerprint`（缺陷集）**：把每条缺陷规范化为 JSON 行 `{"rule_id","class","severity","path","offset","offset_kind","rfc"}`（键序固定为所列顺序，`ensure_ascii=true`，无空格分隔），按 `(rule_id, path, offset)` 升序排序后以 `\n` 连接（末尾无换行），取 `sha256` 十六进制小写。
- **`tree_digest`（树形）**：把每个节点规范化为 `[path, content_type(小写), boundary或null, body_sha256]`，按 `path` 排序（路径分段按整数比，非字符串比）后 `json.dumps` + `sha256`。
- **不含**时间戳、绝对路径、主机名、运行耗时。
- 两指纹**分别**用于两个问题：`fingerprint` 变了 = 判定/规则变了；`tree_digest` 变了 = 解析结果或输入变了。**混用一个摘要就无法归因。**

### 7.9 退出码（唯一定义）

| 码 | 含义 |
|---|---|
| `0` | 审计完成，**无 `blocker`/`major`** 缺陷（`minor`/`note`/`gray` 可有） |
| `1` | **用法错误或输入不可读**（参数错误、文件不存在、无法按字节读取）—— 绝不可与"干净"混淆 |
| `2` | 审计完成，存在 `minor`（但无 `blocker`/`major`） |
| `3` | 审计完成，存在 `major` 或 `blocker` |

- `--fail-on=note|minor|major|blocker` 可提升门槛（默认 `major`）。
- **`1` 是防腐层**：读不了 ≠ 没问题。任何"解析异常导致无法判定"的情形一律 exit 1 或记为 `blocker`，**不得静默返回 0**。

### 7.10 位置口径（`offset` / `offset_kind`）

- `absolute`：从文件第 0 字节起（`--container` 模式下为容器文件内偏移）。
- `message-relative`：从该消息的 `From ` 行首起（M5 容器层）。
- `line`：头块内行号（从 1 起，用于行宽类规则）。
- 报告必须同时给 `offset` 与 `offset_kind`；不给"大概位置"。

---

## 八、诚实口径（README 必须照抄的四句）

1. **"缺陷账本不是解码器"**：本题不承诺"比别人解得更全"，只承诺"解出来的树 + 缺陷账本可复核"。
2. **"审计引擎不 `import email`"**：标准库的宽松行为正是被审计对象；用它会把结论变成照抄。
3. **"未检索到 ≠ 首创"**：0 结果检索式一律按软论据处理。
4. **"节号不等于原句"**：§三 台账 11 行中，**5 行全录、4 行部分录、2 行未录**（R10 的 RFC 2231 §3/§4/§4.1、R11 的 RFC 2045 §2.7/§2.8/§6.1）。部分录与未录的子项对应的规则在补齐前只能出 `note`。这条必须写进 README，不能只在台账里藏着。

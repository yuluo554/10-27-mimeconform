# plan/00-README 总览 — 10-27-mimeconform（MIME 结构体检器）

> 方法论：`ai-tool-project-sprint`（装订 2026-10-27）｜布局门：`py -3.12 tools/check_sprint_layout.py`｜脱敏门：`py -3.12 tools/check_desensitized.py`｜续接对话第一件事 = 跑布局门

> **项目**：把一封邮件（`.eml` / `.mbox`）的**原始字节**转成"带 RFC 条款引用的结构缺陷账本"——每缺陷 = 位置 + 严重度 + RFC 出处 + 硬规则/实现差异标记，另出结构指纹供回归比对。
> **性质**：不参赛项目题 · 发布 GitHub **公开仓库** · 署名 `yuluo554` · **纯本地 Python CLI（只读字节，零网络）**
> **方法论**：数据先行 + 条款台账逐字核对 + 三值封闭的判定分类（`hard` / `diff` / `gray`）+ 合成 golden 语料 + 确定性输出 + 静默失败视为缺陷
> **交付形态**：单一形态，不设备选。无服务端、无浏览器、无数据库、无模型。
> **命名约定**：本地目录与 GitHub 仓库名均为 `10-27-mimeconform`；命令名 `mimeconform`；署名 `yuluo554`。
> **定位宣言**："解码器已成红海（MimeKit 2010★、mailparser 1673★、flanker 1646★、mail-parser 472★、postal-mime 559★，2026-10-27 快照），但**没有任何工具输出「带 RFC 条款引用的结构缺陷账本」**；Python 标准库把 defect 记在对象上却不报告、且仍漏掉内层 boundary 重复。本工具输出：每缺陷 = 位置 + 严重度 + RFC 出处 + 硬规则/实现差异标记。"
> **严格切割声明**：本系列另有一题做**邮件发件人身份认证**（认证语义层）。本题**只做 MIME 结构层**（multipart 树、头编码、附件编码、边界与容器），**全篇不涉及、不引用、不比较该题**。详见 `plan/01` 头部。
> **版本**：v1（2026-10-27，出题阶段 4 = 骨架 + 首提交）

---

## 一、文档索引表

| 文档 | 内容 | 状态 |
|---|---|---|
| `plan/00-README总览.md` | 索引 / 决策记录（含弃选项）/ 承诺-证据台账 / 提交材料实物表 / 里程碑 / 纪律 | ✅ v1（2026-10-27） |
| `plan/01-题目文档.md` | 十段式题目定稿（头部 + 介绍 + 任务要求 + 提交材料 + 评分 + 锚点 + 边界） | ✅ v1（2026-10-27） |
| `data/README.md` | 依据查证（三态 + URL + 检索窗口）/ **RFC 条款原句台账** / **实现差异 vs 硬规则分界表** / 数据源可获取性 / 合成数据纪律 / 数值口径（§七，唯一真相源） | ✅ v1（2026-10-27） |
| `.gitignore` | Python 标准模板 + `*.eml` 真实邮件排除 + `fixtures/out/` | ✅ v1 |
| `plan/02-架构与技术选型.md` | 目录结构 / 依赖方向 / 字节扫描状态机 / 退出码契约 / 确定性设计 / 发布形态 | ✅ v1（2026-10-27，M0） |
| `plan/03-模块详设.md` | scan / headers / transfer / attribution / container / ledger 六模块详设 + CLI 契约总表 + 规则目录 | ✅ v1（2026-10-27，M0） |
| `plan/04-数据计划.md` | 语料矩阵 / 生成器设计 / `expect.json` 契约 / 重建判据 | ✅ v1（2026-10-27，M0） |
| `plan/05-里程碑与验收.md` | M0–M6 DoD / 守门测试清单 / 固定收尾流程 / 已知未验证项 | ✅ v1（2026-10-27，M0） |
| `plan/06-交付对标与决策.md` | 提交材料落点 / 评分维度证据 / 风险登记 / 缺口 | ✅ v1（2026-10-27，M0） |
| `AGENTS.md` | 仓库锚点：方法论装订 / 强制布局 / 门命令 / 环境事实 | ✅ v1（2026-10-27，M0） |
| `tools/check_sprint_layout.py` + `tools/check_desensitized.py` | 布局门 + 脱敏门（纯标准库，进 CI layout job） | ✅ v1（2026-10-27，M0） |
| `README.md` | 安装 / 三场景 / 字段说明 / 已知边界 / 状态表 | 🟡 骨架版（M0）；场景随模块落地补齐 |
| `docs/defect-catalog.md` + `mimeconform/rules/catalog.json` | 缺陷分类表（人读 + 机读） | ⬜ 待 M3 |
| `data/rfc-ledger.json` | RFC 条款台账的机读镜像（原句门禁的判据源） | ✅ 已落（M0 产出，M1 逐行对账） |
| `data/golden/<case>/` | golden 语料 51 个 case（b/h/t/a/c 五簇，各含负例），每 case 三件 `输入 + expect.json + README.md` | ✅ 完成（M1） |
| `plan/HANDOFF-M<k>.md` | 每棒交接单（七节） | ✅ M0 已豁免（见 §五） |
| `plan/RELEASE-M6.md` | 发布留档（tag 前落盘，发布后事实分栏追加） | ⬜ 待 M6 |

---

## 二、决策记录表

> 本节同时是**弃选项记录**。新增决策追加到表尾，不改历史行。

| 日期 | 决策 | 结论与理由 |
|---|---|---|
| 2026-10-27 | 选题：MIME 结构体检器 v1（不参赛，发 GitHub 公开仓库） | 解码器矩阵实测显示"解成对象"有 5 个千星级实现、"单编码算法"有成熟小库，而"整封邮件 → 带条款引用的缺陷账本"未检索到。差异化押在**条款引用 + 三值判定分类 + 位置精度**，不押"能解出来" |
| 2026-10-27 | 交付形态：**纯本地 CLI，仅标准库，零网络** | 输入只有字节文件、输出只有 JSON/MD；单形态才能给出形态化验收（退出码语义 + 字节确定性 + 零网络静态可证） |
| 2026-10-27 | **D1（本题存在理由）**：Python 标准库把 defect 记在对象上但不报告、不打分，**而且仍漏掉内层 boundary 重复** | ① 官方 `email.errors` 缺陷类覆盖边界/base64/结构，但原句只说 *"the defects are added to the message where the problem was found"* —— 挂上就完了，不打印、不计数、不退出非零；调用方不主动遍历 `msg.defects` 永远不知道。② cpython **#69914（open，6 评论）**："email parser ignores inner multipart boundary when outer message duplicates it" —— 标准库在最难的一格（内外层同 boundary）**知道得也不完整**，宽松解析会选一个答案继续走，"错"变成"看起来对"。这两点合起来构成本题的存在理由：**不是再解一遍，是把"知道而不说"变成"说出来并可复核"** |
| 2026-10-27 | **D2**：`Content-Transfer-Encoding` 声明 vs 实际不符 = **`diff`，永不 `hard`** | RFC 2045 只在 §2.7/§2.8/§6.1 定义各 CTE 的语义，**没有任何"交叉校验"条款**（逐条核对 §6.1/§6.7/§6.8）。这是**语义层**判定，必须由实现交叉判定，因此只能标 `diff`，`rfc` 字段写 `none-by-design`。把它写成 `hard` 就是编条款 |
| 2026-10-27 | **D3**：mbox `>From` 是 **mboxo 约定，不是 RFC**；mboxrd / mboxcl 变体互不相同 → M5 只出 `diff` | RFC 5322/2045/2046 均不定义 mbox 容器格式。三种变体的转义规则（`>From` 转义 / `>From ` 反转义 / `Content-Length` 前缀）互不兼容。因此同一文件在不同变体下切分结果不同**是正常的**，报告必须同时给两种读法的切分表，不得只判一种"正确"。**这是本题硬规则最弱的一格**，如实标注 |
| 2026-10-27 | **D4**：最大嵌套深度 RFC 未规定 → 只作 `--max-depth` **策略**，标 `gray` | 逐条核对 RFC 2046 §5.1.1/§5.1.2：有 boundary 唯一性要求、有 delimiter 形态要求，**没有深度上限**（也无"实现必须限制深度"的措辞）。故超限只出 `gray/note`，默认不影响退出码；`--strict-depth` 是**用户显式选择**，不是 RFC 结论 |
| 2026-10-27 | **D5**：GOVCERT-LU/eml_parser **246★ 明确排除**，不走该路线 | 该实现是**钓鱼检测 / 头部分析向**，其判定依赖认证语义（发件人身份验证相关头字段），违反本题头部切割声明。且它已占住"eml 分析"这一入口，正面撞车。本题只做结构层，不涉内容安全 |
| 2026-10-27 | **D6**：审计引擎**不得 `import email`** | 标准库 `email` 正是本题要审计其宽松行为的那一层；用它会把结论变成"照抄被测对象的判断"。引擎为自写字节级状态机；`mimeconform/devtools/stdlib_compare.py` 允许 `import email`，**仅供测试取证**，守门测试用 AST 断言报告路径无该导入 |
| 2026-10-27 | **D7**：判定分类**三值封闭**（`hard` / `diff` / `gray`），不可升级、不可增加第四值 | 三值对应三种证据强度：有逐字原句 / RFC 无条款或实现分歧 / RFC 未规定的策略项。封闭才能防止"M4 想给个 hard 显得权威"这类漂移。**语义层规则一律拿不到 `hard`**，代价是不能拿条款压人，收益是每条 `hard` 都经得起查条款 |
| 2026-10-27 | **D8**：`rfc` 字段**不得为空**；无条款时必须写 `none-by-design` 或"仅定义 X、未定义 Y" | "没有条款"本身是证据，必须显式写进账本，不能留空格让人误以为是漏填。这是防编造条款的机械约束 |
| 2026-10-27 | **D9**：内层 boundary 重复必须给**两种候选树**，不替用户选 | 字节层无法唯一确定 close-delimiter 归属（这正是 #69914 的成因）。替用户选一个等于复刻标准库的错误；只报"有问题"等于没说清问题在哪。两棵树 + 差异位置才是可复核的结论 |
| 2026-10-27 | **D10**：`filename` 取值顺序**先 RFC 2231 再 RFC 2047**，写死 | 两个解码层次叠加时顺序不同会得出不同文件名；若不写死，两位开发者会各写一套，golden 就无法逐字节验收。顺序定义在 `data/README.md` §7.5 |
| 2026-10-27 | **D11**：模块 M4（归属与引用）全部规则 `diff` / `gray`，**无 `hard`** | `Content-Disposition` 与 `multipart/related` 的规范定义不在本题核对的五部 RFC（2045/2046/2047/2231/5322）之内。按"不得编造条款"红线，宁可全降级，也不引一部没逐条读过正文的规范 |
| 2026-10-27 | **弃「头编码单独成产品」** | RFC 2047/2231 的检查面与其他模块共享"头块字节"这一输入，且 `filename*0` 跳号的证据（SO 44154520）只有在附件归属语境里才有意义；单独成产品功能面太窄 → **降为模块 M2** |
| 2026-10-27 | **弃「CTE 单独成产品」** | CTE 审计的对象是"叶节点正文"，而叶节点只能由 multipart 切分得出；脱离树就没有 `path` 可言，缺陷无法定位 → **降为模块 M3**（与树强耦合） |
| 2026-10-27 | **弃「归属/引用单独成产品」** | 同上：`cid:` 闭合、`related` 的 `start`、`message/rfc822` 归属全部依赖树结构；单独成产品只剩"读参数"这一薄层 → **降为模块 M4** |
| 2026-10-27 | **弃「mbox 容器层单独成产品」** | 硬规则最弱（`>From` 非 RFC + 三变体分歧）+ 误报率高（正文含 `From ` 的合法邮件极常见），单独成产品会把"变体差异"卖成"违规" → **降为可选模块 M5** |
| 2026-10-27 | **弃「ronomon/mime 路线」** | 63★，*"standards-compliant MIME decoder … extensive tests and fuzz tests"*，是最接近"严格解码"的实现，但 ① 它是**解码器**不是审计器（无条款引用账本）② **2020-09 后归档**。可作对照参照，不作基线 |
| 2026-10-27 | **弃「TNEF / winmail.dat 专向」** | 专有格式解码，越出"结构层"边界（本题判声明与编码，不判专有容器内部）。且无公开完整规范，无法给 `rfc` 出处 |
| 2026-10-27 | **弃「GOVCERT 式钓鱼/URL 分析」** | 见 D5：触及认证语义，且 246★ 已占位 |
| 2026-10-27 | **弃「`.eml` 查看器 / 渲染器」** | 渲染是客户端领地，且没有确定性内核，无法进入 golden 逐字节验收，会变成"好看但不可复算"的空壳 |
| 2026-10-27 | 严重度分级定为 **blocker / major / minor / note** 四档 | 与 `class` 正交（`class` 说的是"证据强度"，`severity` 说的是"影响"）。两轴混用会让"RFC 没规定但影响大"和"RFC 明令禁止但影响小"无法表达 |
| 2026-10-27 | 结构指纹分两个：`fingerprint`（缺陷集）与 `tree_digest`（树形） | 缺陷集指纹用于"改代码后账本有没有变"；树指纹用于"同一封邮件换工具解出来树一不一样"。两者混用一个摘要就无法回答"是缺陷判定变了还是解析变了" |
| 2026-10-27 | 退出码补定为 **0/1/2/3**（见 `data/README.md` §7.9） | 题面给了"有缺陷"与"无缺陷"，必须显式定义 **1 = 用法错误或输入不可读**：否则"读不了"会被误当成"干净"（静默通过的经典漏洞） |
| 2026-10-27 | 数值口径一处定义（`data/README.md` §七） | 规则编号语义、`class` 判定顺序、严重度映射、退出码、指纹算法、`--max-depth` 默认值、mbox 变体判定、filename 解码顺序只在该处定义；代码常量与文档摘录全部引用它，禁止第二套表述 |
| 2026-10-27 | 发布里程碑采用 **Release 附产物** 口径 | M6 DoD 三件套：**git tag + GitHub Release 附产物（≥1 个手工上传附件，本地留副本 + sha256）+ 发布留档文件**。不降级为"源码 zipball 即产物" |
| 2026-10-27 | 真实邮件禁入仓，`data/golden/**` 是唯一例外且只允许合成样本 | `.gitignore` 全局排除 `*.eml`，再对 `data/golden/**` 开例外。合成样本用 `example.invalid` 域 + 假附件名；提交前由生成器重跑核对逐字节一致（`data/README.md` §六） |
| 2026-10-27 | **D12**：`hard` 需要**逐字原句**，只有"节号 + 语义"不够；未录子项一律降为 `note`，且由构建期门禁机械强制 | 首稿里我把 RFC 2231 §3/§4/§4.1 与 RFC 2045 §2.7/§2.8/§6.1 的规则直接写了 `hard`，但这两行**本轮只核到节号、没留逐字原句**——这违反自己定的"不编造条款"红线。修法不是删规则，而是：① 台账加「原句留档」列逐行标注（全录 / 部分 / 未录）；② 未录子项在补齐前只能出 `note`；③ `catalog.json` 的 `rfc` 键必须在 `data/rfc-ledger.json` 存在且 `verbatim` 非空，否则构建期失败。**代价**：首版可 `hard` 的规则变少；**收益**："节号靠印象、原句靠记忆"这条最隐蔽的漂移被机械堵住 |
| 2026-10-27 | **D13**：Python 下限 **3.11**，不降到 3.9/3.10 | 需要 `dataclass(slots=True)`（3.10+）与 `tomllib`（3.11+）的稳定行为；下限写进 `pyproject.requires-python` **并落成 AST/运行时断言**（`tests/test_python_floor.py`）。本机只有 3.12.10 一条可用通道（3.8.8 低于底线，**不得用作验证通道**），3.11 / 3.13 的差异只能靠 CI 矩阵。代价：少覆盖老环境；收益：不为兼容性在引擎里写第二套语法 |
| 2026-10-27 | **D14**：布局门 / 脱敏门用 **Python 标准库重写**，不用 Node | 本项目运行时零第三方、开发者只需要 CPython；模板是 Node 版，判据集保持不变（"可直接拷用的实现"里明确允许按同一判据集重写）。收益：CI 不需要 Node 步骤、门与产品同一条工具链；判据集不因语言而改 |
| 2026-10-27 | **D15**：发布附件口径 = **手工源码包**（`git archive --format=tar --prefix=mimeconform-<ver>/ <tag> \| gzip -9n` + `SHA256SUMS`） | 本项目无构建步骤（纯标准库 CLI），sdist 的 tar 成员 mtime 会让"同 tag 建两次 sha256 不同"，破坏"sha256 可复验"。`git archive | gzip -9n` 可复算（同命令再跑一次 `cmp` 逐字节一致）。不发布 wheel：规则包与源码同树可查是本题的必要叙事 |
| 2026-10-27 | **D16**：M0 不交付任何规则判定；未实现能力**显式抛 `NotImplementedError` 并经 CLI 映射为 exit 1** | 骨架期的最大风险是"静默通过"（读不了/没实现都返回 0）。M0 的骨架必须**能跑、能红、不撒谎**：`audit` 在 M0 对任何输入返回 exit 1 + 明确文案"规则引擎尚未实现（里程碑 M2 起）"，**绝不**返回 0 |

---

## 三、承诺-证据台账

> 全项目只此一份。其他文档只可引用，不得复制表格。状态列随里程碑同一次提交翻转。

| 承诺项 | 素材来源 | 交付物内可达性 | 核验方式 | 状态 |
|---|---|---|---|---|
| 条款引用可查（11 行 RFC 条款） | 逐条读 RFC 原文（2045/2046/2047/2231/5322） | ✅ 台账在 `data/README.md` §三 + 机读镜像 `data/rfc-ledger.json` | 每条 `hard` 缺陷的 `rfc` 字段可在台账中检索到同一节号；**且该子项的「原句留档」必须覆盖它**（5 行全录 / 4 行部分 / 2 行未录；部分录与未录的子项只能出 `note`） | ✅ 台账已建（含逐行留档状态列）；✅ 机读镜像已落（M0），`tests/test_ledger_mirror.py` 逐行对账 |
| 原句门禁（机械，非口头纪律） | `data/rfc-ledger.json` + `catalog.json` 构建期校验 | ✅ 契约在 `data/README.md` §7.1；校验实现已落 `mimeconform/rules/__init__.py` | 故意把某规则的 `rfc` 指向 `verbatim=null` 的键 → 校验必须失败（`CatalogError`） | 🟡 校验逻辑与注入用例已落；**真实 `catalog.json` 待 M3**（在此之前本条只对注入数据生效） |
| 三值判定分类 `hard`/`diff`/`gray` | 自定纪律（D7 + `data/README.md` §7.1） | ✅ | `catalog.json` 中每条规则 `class` ∈ {hard,diff,gray}；语义层规则断言 ≠ `hard` | 🟡 校验逻辑与注入用例已落；**真实 catalog 待 M3** |
| `rfc` 字段无空值 | 自定纪律（D8） | ✅ | `expect.json` 逐条断言 `rfc` 非空；`none-by-design` 计数可查 | ✅ 完成（M1：51 case × 逐条断言，`selftest` 复算） |
| 复现 cpython #69914（内层 boundary 重复） | issue 原文 + 自造样本 | ✅ | `data/golden/b-inner-dup/`：MC-B06 `hard/major` + 两棵候选树 + `divergence.path="0.1"` | ✅ 完成（M2：引擎侧命中；`stdlib_compare` 实测 1 条 `StartBoundaryNotFoundDefect` 由测试重跑验证） |
| 复现 cpython #56141（折行头破坏边界检测） | issue 原文 + 自造样本 | ✅ | `data/golden/b-wrapped-header/`：负例、零缺陷、2 个子部件 | ✅ 完成（M2：引擎侧命中；标准库 3.12.10 实测 0 defect 亦由测试重跑验证） |
| 复现 cpython #93376（畸形 `From ` 行） | issue 原文 + 自造 mbox | ✅ | `data/golden/c-from-bad/`：MC-C01 + 两变体切分表 | ⬜ 待 M5 |
| 复现 SO 44154520（缺 `*0` 序号） | SO 原话 + 原样片段 | ✅ | `data/golden/h-2231-seq/`：MC-H09 `hard/major` + 修正提示文本 | ⬜ 待 M3 |
| 复现 SO 52442469（encoded-word 内换行） | SO 原话 + 原样片段 | ✅ | `data/golden/h-ew-newline/`：MC-H12 `diff/note`，且**不**同时报 MC-H03 | ⬜ 待 M3 |
| 复现 SO 79133579（QP 伪影） | SO 原话 `=ustomers` / `=o:p>` / `=ure` | ✅ | `data/golden/t-qp-artifact/`：MC-T07 `hard/major` + 字节偏移 | ⬜ 待 M4 |
| 复现 SO 6029218（base64 损坏） | SO 原话 + 自造样本 | ✅ | `data/golden/t-b64-len/`：MC-T03 `hard/major` | ⬜ 待 M4 |
| 复现 SO 6255202（文本附件被当正文） | SO 原话 | ✅ | `data/golden/a-body-attach/`：MC-A01 `diff` | ⬜ 待 M5 |
| 复现 SO 12816042（缺 filename → Noname） | SO 原话 | ✅ | `data/golden/a-noname/`：MC-A03 `diff` | ⬜ 待 M5 |
| 负例零误报（合法 QP / 合法 base64 / 合法多 encoded-word / 完好嵌套树 / 正确归属） | 自造负例 | ✅ | 各组 `expect.json` 缺陷数 = 0 | 🟡 `b-*` 侧已闭环（本轮：`b-clean-nested` / `b-wrapped-header` 引擎侧零误报，含"规则集合不被扩大"断言）；`h/t/a/c` 侧引擎零误报待后续三棒 |
| 确定性输出（同输入双跑逐字节一致） | 自定纪律 | ✅ | 双跑 `cmp`；golden 为逐字节基线 | ✅ 完成（M2：渲染与序列化层 + **引擎层**双跑逐字节一致，`tests/test_determinism.py` 对全部 `.eml` 语料逐个跑两遍） |
| 审计引擎不 `import email` | 自定纪律（D6） | ✅ | AST 守门测试：`mimeconform/` 下全部非 devtools 模块无 `email` 导入（含相对导入 / `from X import Y` / 动态导入四形态） | ✅ 守门已落（M0）；随 M2–M5 新模块自动覆盖 |
| 零网络 | 无 `socket`/`urllib`/`http` 导入 | ✅ 静态可证 | AST 守门 + CI 的 `docker run --network none` 离线作业 | ✅ 守门 + 离线 job 已落（M0）；离线 job 待首推验证 |
| 退出码 0/1/2/3 | 自定契约（`data/README.md` §7.9） | ✅ | 退出码矩阵 4 行：CLI 级 0/1/2/3 已可跑（M2 接线，`tests/test_cli_contract.py`）；函数级 0/2/3 已锁（`tests/test_exit_codes.py`） | ✅ 完成（M2：CLI 级 2 = 只有 minor、3 = 有 major/blocker，均由真命令断言） |
| 真实邮件不入仓 | `.gitignore` + 生成器复核 | ✅ | `git ls-files '*.eml'` 只出现在 `data/golden/**` 且均为合成样本 | ✅ 规则已落 |
| 开源空白论据 | `gh api` 检索快照 2026-10-27T10:56Z–11:04Z | — | 检索式与 total_count 记录在 `plan/01` §1.5、`data/README.md` §一.2 | ✅ 已记录（⬜ 软论据口径） |
| 单二进制/单包零运行时依赖（发布态） | `pipx`/`python -m` 直接可用，无第三方依赖 | ✅ | 干净环境（仅 CPython）安装运行 | ⬜ 待 M6 |
| 方法论装订（锚点 + 两道门） | `AGENTS.md` + `tools/check_sprint_layout.py` + `tools/check_desensitized.py` + 本文件顶部装订行 | ✅ | 两条门本机跑绿；布局门 ≥8 组变异全红 | ✅ 完成（M0） |
| 计划套件齐全（00–06 + data 台账） | `plan/00`–`06` + `data/README.md` | ✅ | 布局门 `LAYOUT.FILES` / `LAYOUT.SECTIONS` | ✅ 完成（M0） |
| 可运行骨架（`--version` / 退出码 0·1） | `pyproject.toml` + `mimeconform/cli.py` + `tests/` | ✅ | `mimeconform --version` = 0；用法错误 = 1；`pytest` 全绿 | ✅ 完成（M0） |
| 骨架不撒谎（未实现能力显式失败） | `mimeconform/cli.py` 的 `audit` 分支 | ✅ | M0 下任何 `audit` 输入 exit 1 + "规则引擎尚未实现" | ✅ 完成（M0） |

---

## 四、提交材料实物表

> 对应 `plan/01` §三。每一项必须能指到一个具体文件；指不出的项此刻删除，不留到评分表里。

| 承诺项 | 应存在的文件路径 | 由哪个里程碑产出 | 用哪条命令核对 |
|---|---|---|---|
| CLI 可运行入口 | `pyproject.toml`（`[project.scripts] mimeconform`）+ `mimeconform/cli.py` | M2 | `mimeconform --version`；退出码矩阵 4 条断言 |
| 源码可重建 | `mimeconform/{scan,headers,transfer,attribution,container,ledger}.py` + `mimeconform/rules/catalog.json` | 里程碑 M2–M5 | `python -m pytest -q`；AST 守门测试 |
| golden `.eml` 语料 | `data/golden/<case>/{msg.eml,expect.json,README.md}`（每类缺陷 ≥2 正例 + 1 负例） | 里程碑 M1–M5 | `py -3.12 -m mimeconform.devtools.gen_golden --check` → `N cases, 0 diff` |
| 缺陷分类表（人读） | `docs/defect-catalog.md` | M3 | 与 `catalog.json` 交叉核对（规则数一致） |
| 缺陷分类表（机读） | `mimeconform/rules/catalog.json` | M3 | `rule_id` / `class` / `severity` / `rfc` / `detector` 五字段无空值 |
| 结构指纹基线 | `data/golden/<case>/expect.json` 内 `fingerprint` + `tree_digest` | 里程碑 M1–M5 | 双跑逐字节一致；跨版本 `--diff-baseline` 可读 |
| README（三场景最小复现） | `README.md` | M2 | 三场景命令逐条跑通 |
| 发布留档 | `plan/RELEASE-M6.md` | M6（tag 前落盘） | `git cat-file -e <tag>:plan/RELEASE-M6.md` |

---

## 五、里程碑与状态

> 状态副本三处：本表 / `plan/05` §一 / `README.md` 状态表。**三处逐字一致**由布局门机器断言。
> **编号消歧（必读）**：**里程碑**用 M0–M6；**功能模块**用模块 M1–M5（`plan/01` §二）。两者编号不同，**不是同一套**：模块 M1 树与边界 ↔ 里程碑 M2；模块 M2 头编码 ↔ 里程碑 M3；模块 M3 传输编码 ↔ 里程碑 M4；模块 M4 归属与引用 / 模块 M5 容器层 ↔ 里程碑 M5。数据先行（golden 语料）= 里程碑 M1，先于全部模块。

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| **M0 计划先行 + 骨架** | 装订三件（`AGENTS.md` + `tools/` 两道门 + 本文件顶部装订行）+ `plan/00`–`06` + `data/README.md` + `.gitignore` / `.gitattributes` / `LICENSE` + 可运行骨架（`--version` / `selftest` / 退出码 0·1）+ AST 守门测试 | ✅ 完成（2026-10-27） |
| **M1 数据先行（golden `.eml` 语料 + 机读台账）** | `data/rfc-ledger.json` + 语料生成器 + `data/golden/`：**每类缺陷至少 2 个正例 + 1 个负例**；每 case 带 `expect.json`（含 `class` / `severity` / `rfc` / 指纹）与来源说明 | ✅ 完成（2026-10-27） |
| **M2 树与边界** | 字节扫描状态机 + multipart 树重建 + MC-B 系列；复现 #69914（两棵候选树）与手工"缺 final boundary"样本 | ✅ 完成（2026-10-27） |
| **M3 头编码** | RFC 2047 / 2231 检查 + MC-H 系列；复现 SO 44154520（缺 `*0`）与 SO 52442469（encoded-word 内换行）；缺陷分类表落盘 | ⬜ 未开始 |
| **M4 传输编码（CTE）** | base64 / QP 自写编解码 + MC-T 系列；复现 SO 79133579（QP 伪影）与 SO 6029218（base64 损坏） | ⬜ 未开始 |
| **M5 归属与容器** | 归属与引用审计（MC-A 系列）+ 可选容器层（MC-C 系列）；复现 SO 6255202 / 12816042 / #93376，mbox 三变体并出 | ⬜ 未开始 |
| **M6 发布** | 干净环境验证 + 发布 | ⬜ 未开始 |

> **M0 的收尾记录就是计划套件本身**（本项目已声明豁免）：M0 不写 `plan/HANDOFF-M0.md`，其 DoD 与证据即 `plan/00`–`06` 与 `AGENTS.md`。**M1 起每棒必须有交接单**（含收尾棒），由布局门断言。

**M6 DoD**：**git tag + GitHub Release 附产物（≥1 个手工上传附件，本地留副本 + sha256）+ 发布留档 `plan/RELEASE-M6.md`** 三件套齐；在只有 CPython（无第三方包）的环境安装并跑通 golden 全量；发布 GitHub **公开仓库**。

---

## 六、纪律

1. **数值口径一处定义**：规则编号语义、`class` 三值定义与判定顺序、严重度映射、退出码、指纹算法、`--max-depth` 默认值、mbox 变体判定、filename 解码顺序只在 `data/README.md` §七定义；代码与文档摘录与之同源，冲突以该处为准。
2. **不写漂移硬数字**：星数 / `total_count` 一律标注"2026-10-27 快照"，只进文档，**不写进代码或断言阈值**。
3. **不编造条款**：任何 `hard` 判定必须能在 `data/README.md` §三的原句台账里指到同一 RFC 号 + 节号；指不到就只能 `diff` / `gray`。**宁降级，不补条款。**
4. **未知即显式**：解不出的 charset 记 `decode_error`（不伪装成某条规则）；读不了的输入 exit 1；归不进已有 rule_id 的现象**不得静默丢弃**——要么新增规则并登记，要么记 `note` 并写明"未分类"。
5. **只读输入**：不写回输入文件、不产生临时目录；输出只写 `--out` 指定路径或 stdout。`--fix-plan` 只出建议文本。
6. **形态唯一**：纯本地 CLI。任何"再加个网页/桌面/服务"的提议先回本节上方决策记录表加一行弃选项。
7. **隐私红线**：真实邮件不入仓；`data/golden/**` 只允许合成样本（`example.invalid` 域 + 假附件名）。
8. **品牌隔离**：本仓库文档不提名本系列任何其他项目；涉及同类时用方向级描述（"认证语义层""解码器"）。

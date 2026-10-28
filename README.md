# mimeconform — MIME 结构体检器

> 把一封邮件的**原始字节**转成**带 RFC 条款引用的结构缺陷账本**：
> 每条缺陷 = 位置 + 严重度 + RFC 出处 + **硬规则 / 实现差异**标记，另出结构指纹供回归比对。

`mimeconform` 不是解码器。它不承诺"比别人解得更全"，只承诺**解出来的树 + 缺陷账本可复核**。

---

## 为什么需要它

一封 `.eml` 出问题时，工程现场的动作是固定的：丢进某个库解出来 → 看不出来不对 → 猜是编码问题
→ 换一个库再解一次 → 得到另一种结果。中间缺的那一步是**判定**：这段字节违反了哪一条 RFC、
在第几个字节、有多严重、是硬规则还是实现差异。

Python 标准库的 `email` 包**知道**有缺陷，但只把缺陷挂在对象上（官方原句：
*"the defects are added to the message where the problem was found"*）——不打印、不计数、
不打分、不退出非零。而且它的缺陷类清单里**没有**「`Content-Transfer-Encoding` 声明与实际不符」
这一类，还会在内层 boundary 重复时错处理（cpython issue #69914，open）。

`mimeconform` 把这些"知道而不说"变成**说出来并可复核**。

---

## 诚实口径（四条，请先读）

1. **缺陷账本不是解码器**：不承诺比别人解得更全，只承诺解出来的树 + 缺陷账本可复核。
2. **审计引擎不 `import email`**：标准库的宽松行为正是被审计对象；用它会把结论变成照抄。
   唯一例外是 `mimeconform/devtools/stdlib_compare.py`（仅测试取证，不进报告路径）。
3. **未检索到 ≠ 首创**：开源空白检索按软论据处理，本文不写"首创 / 无人做过"。
4. **节号不等于原句**：11 行条款台账里 **5 行全录 / 4 行部分录 / 2 行未录**；
   部分录与未录的子项对应的规则在补齐前**只能出 `note`**（机读门禁，见
   `mimeconform/rules/__init__.py`）。

---

## 安装

```bash
# 只装本体（零第三方运行时依赖）
pip install .

# 开发态（含 pytest）
pip install -e ".[dev]"
```

要求 Python **3.11+**。

---

## 用法

```bash
mimeconform --version
mimeconform audit sample.eml                      # 账本写 stdout（JSON + Markdown）
mimeconform audit sample.eml --out report.json    # 按扩展名挑格式
mimeconform audit sample.eml --out reports/       # 目录形态：两种格式都写
mimeconform selftest                              # 校验 golden 语料自洽性
```

### 三个可照抄的场景（当前能力：单封 `.eml` 的树与边界 + 头编码）

```bash
# 场景 1：内层 boundary 与外层重复（cpython #69914）→ 退出码 3 + 两棵候选树
mimeconform audit data/golden/b-inner-dup/msg.eml --out /tmp/dup.json
#   report 里 "'tree'.'tree_alternatives'" = 2，"'tree'.'divergence'.'path'" = "0.1"
#   —— 默认展示的树不构成判定，两棵树都要人看

# 场景 2：干净嵌套（负例）→ 退出码 0，缺陷数 0
mimeconform audit data/golden/b-clean-nested/msg.eml --format json

# 场景 3：缺 final boundary → 退出码 0（仅 diff/note 登记），报告给出"被迫闭合"的字节位置
mimeconform audit data/golden/b-no-final/msg.eml --format md
```

### 头编码（M3 起可跑）

```bash
# encoded-word 内折行（SO 52442469）→ 只报 MC-H12，被压掉的 MC-H03 进 related
mimeconform audit data/golden/h-ew-newline/msg.eml --format json

# 头行 > 998 octets → MC-H07（hard/major）→ 退出码 3
mimeconform audit data/golden/h-line-998/msg.eml --format md

# 缺 *0 序号的附件名（SO 44154520）→ MC-H09（diff/note，退出码仍 0）+ 修正提示文本
mimeconform audit data/golden/h-2231-seq/msg.eml --format json
```

> 报告里的 `"tree": {"audited_engines": [...], "not_yet_audited": [...]}` 是**覆盖面声明**：
> 一份干净的账本不等于"所有层都查过了"。未接入的层（`attribution` / `container`）
> 的规则**未**参与本次判定。

> `audit` 当前只审计**单封邮件**（`.eml`）。`.mbox` / Maildir 容器与
> `--container` / `--mbox-variant` 自里程碑 M5 起支持；此刻传目录会得到 exit 1
> 并明确说明"容器层自 M5 起支持"。

**退出码**（`data/README.md` §7.9 是唯一定义）：

| 码 | 含义 |
| --- | --- |
| `0` | 审计完成，无 `blocker`/`major` |
| `1` | **用法错误或输入不可读**（读不了 ≠ 没问题） |
| `2` | 审计完成，存在 `minor`（无 `blocker`/`major`） |
| `3` | 审计完成，存在 `major`/`blocker` |

---

## 缺陷的六元组

```json
{
  "rule_id": "MC-B06",
  "class": "hard",
  "severity": "major",
  "path": "0.1",
  "offset": 106,
  "offset_kind": "absolute",
  "rfc": "RFC 2046 §5.1.1",
  "detail": "nested multipart reuses outer boundary 'X'"
}
```

- **`class` 三值封闭**：`hard`（有逐字原句支撑）/ `diff`（RFC 无条款或实现分歧）/ `gray`（RFC 未规定的策略项）。
  **没有第四种，也不可升级**：语义层规则（归属与引用、CTE 交叉校验、mbox `>From`、嵌套深度）**拿不到 `hard`**。
- **`rfc` 不得为空**：无条款时写 `none-by-design`——**用"没有条款"本身作证据**，而不是编一个条款。
- **位置**：`offset` + `offset_kind`（`absolute` / `message-relative` / `line`），不给"大概位置"。

---

## 边界与非目标

**只做 MIME 结构层**：multipart 树、头编码、附件编码、边界与容器。

**不做**：邮件认证（认证语义层整块排除——不读取、不解析、不判定、不产出任何"可信/不可信"结论）、
TNEF / `winmail.dat` 专向、钓鱼 / URL / 内容安全分析、`.eml` 查看器 / 渲染器、
最大嵌套深度硬判（RFC 无规定 → 只作 `--max-depth` 策略项，`gray`）、自动修复 / 写回输入文件。

**隐私**：纯本地、**零网络**（无 `socket` / `urllib` / `http` 导入，AST 守门）；输入只读不写；
真实邮件**一律不入仓**，`data/golden/` 只允许程序化合成样本（`example.invalid` 域 + 假附件名）。

---

## 状态

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| M0 | 计划套件 + 方法论装订 + 可运行骨架 | ✅ 完成 |
| M1 | 数据先行（机读台账 + golden 语料生成器 + 51 case 语料） | ✅ 完成 |
| M2 | 树与边界（MC-B） | ✅ 完成 |
| M3 | 头编码（MC-H）+ 缺陷分类表（人读 + 机读） | ✅ 完成 |
| M4 | 传输编码（MC-T） | ✅ 完成 |
| M5 | 归属与容器（MC-A / MC-C） | ⬜ 未开始 |
| M6 | 发布 | ⬜ 未开始 |

> 本表与 `plan/00`、`plan/05` 逐字一致，由 `tools/check_sprint_layout.py` 断言。
> 当前 **M4 已完成**：`audit` 可对单封 `.eml` 真跑（multipart 树 + MC-B 系列 + 头编码 MC-H 系列 +
> 传输编码 MC-T 系列），退出码 0/2/3 均为审计结论。M5 的两个模块（`attribution` /
> `container`）**仍未实现**，调用即抛 `EngineNotReady` → exit 1——**未实现 ≠ 干净**，
> 报告里的 `not_yet_audited` 字段同口径声明。

---

## 文档索引

| 文档 | 内容 |
| --- | --- |
| `plan/00-README总览.md` | 索引 / 决策记录（含弃选项）/ 承诺-证据台账 / 里程碑 |
| `plan/01-题目文档.md` | 题目定稿：介绍 / 任务要求 / 提交材料 / 评分 / 锚点 / 边界 |
| `plan/02-架构与技术选型.md` | 分层与依赖方向 / 字节扫描状态机 / 退出码接线 / 确定性设计 |
| `plan/03-模块详设.md` | 六个代码模块的接口与判定条件 / CLI 契约 / 规则目录门禁 |
| `plan/04-数据计划.md` | 语料矩阵 / 生成器设计 / `expect.json` 契约 / 重建判据 |
| `plan/05-里程碑与验收.md` | M0–M6 DoD / 守门测试清单 / 固定收尾流程 / 已知未验证项 |
| `plan/06-交付对标与决策.md` | 评分维度证据 / 风险登记 / 缺口 |
| `data/README.md` | **RFC 条款原句台账** + 实现差异分界表 + **数值口径（唯一真相源）** |
| `docs/defect-catalog.md` | **缺陷分类表（人读）**：每条规则 → 判定 / `class` / `severity` / 台账行 / 正负例 / 常见误报；与 `mimeconform/rules/catalog.json` 机器对账 |
| `AGENTS.md` | 仓库锚点：方法论装订 / 强制布局 / 门命令 |

---

## 开发

```bash
py -3.12 tools/check_sprint_layout.py    # 布局门（新对话第一件事）
py -3.12 tools/check_desensitized.py     # 脱敏门
py -3.12 -m pytest -q                    # 全量测试
```

许可：MIT（见 `LICENSE`）。

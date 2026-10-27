# HANDOFF-M1 — 进入 M1（数据先行）的收尾交接单

> 产出棒：M0（计划先行 + 骨架），2026-10-27。
> 用法：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（见 `AGENTS.md`）。
> **库内一律相对路径**；绝对路径只出现在会话启动命令里。

---

## 一、当前进度 + 证据

**M0 已完成并验证**（状态以 `plan/00` 里程碑表为准；本节的数字是**当轮实测**）。

| 项 | 实测证据 |
| --- | --- |
| 布局门 | `py -3.12 tools/check_sprint_layout.py` → 9 条判据全 PASS，`这轮扫到：files 14 / sections 8 / handoffs 0 / gap_rows 7 / ledger 1 / doc_tools 2` |
| 脱敏门 | `py -3.12 tools/check_desensitized.py` → 扫 53 个文本文件，0 命中（豁免 2 份） |
| 布局门变异验证 | `py -3.12 tools/verify_layout_gate.py` → **15 组：15 符合预期 / 0 不符**（13 组该红、2 组阴性对照该绿） |
| 全量测试 | `py -3.12 -X utf8 -m pytest` → **213 passed, 2 skipped**（两条 skip 是 `data/golden` 未落地的显式"不适用"） |
| 干净 venv 双入口 | 新建 venv → `pip install -e .` 与 `pip install .`（非 editable）各一次；`mimeconform --version`=0、`python -m mimeconform --version`=0、`mimeconform audit <不存在>`=1 |
| 机读台账 | `data/rfc-ledger.json`（17 个 clause / 28 个 subclause），`tests/test_ledger_mirror.py` 与人读 §三 逐行对账通过 |

**M1 要做到的东西**：`data/golden/` 全量语料 + 生成器 + `selftest` 真正跑起来。

---

## 二、当前事实·状态不变量（下一棒动手前必须知道，否则一定会踩）

1. **`mimeconform/` 下的模块有两条不同的"未实现"契约**：
   `scan/headers/transfer/attribution/container` 的函数体抛 `EngineNotReady`；
   **`cli.py` 的 `_run_audit` 目前是不可达的接线草稿**（在 `scan_message` 之后），
   M2 接引擎时**必须整体重写这一段**，不要以为它在跑。判据：`grep -n "骨架期不可达" mimeconform/cli.py`。
2. **`container.detect_variant()` 是已实现的纯函数**（§7.7 的三条字节规则），
   但 `split_container()` 是 `EngineNotReady`；写 M5 时别把 detect 重写一遍。
3. **`mimeconform/rules/catalog.json` 不存在**，`load_catalog()` 会抛 `CatalogError`（具名异常，不是 `FileNotFoundError`）。
   `tests/test_catalog_gate.py::test_real_catalog_is_absent_and_reports_cleanly` 断言了这一点；
   **M3 落地 catalog 后该测试会 skip**（它自动退场，不要删）。
4. **`data/rfc-ledger.json` 已经存在且是判据输入**，M1 的任务是**补齐 golden 语料**，不是重做台账。
   台账的 `subclauses[].recorded` 字段是门禁的唯一输入：`recorded: true` 才允许 `verbatim` 非 null。
5. **`SEMANTIC_RULES`（`mimeconform/rules/__init__.py`）是唯一登记处**；
   `data/README` §7.1 的升级禁令列表与它必须逐项相等（有测试断言集合相等）。
   新增语义层规则时要**两处同改**，否则测试红。
6. **状态副本共 4 处**，改状态要四处一起翻：`plan/00` 里程碑表、`plan/00` 承诺-证据台账、
   `plan/05` 状态表、`README.md` 状态表。布局门会逐处断言（含每副本命中行数）。
7. **`plan/06` 的缺口表扫描面 = 表头 → 首条非表格行**；列号按**表头名**定位（`缺口` 是第 2 列，不是最后一列）。
   在缺口格里提到**已 ✅ 的里程碑号**会让 `LAYOUT.GAPS` 变红——写证据请指文件名（门会剥掉路径形态）。
8. **`tests/test_gates.py` 里的注入样本用 `_token(...)` 运行时拼接**（不是完整字面量）：
   脱敏门扫全仓，本文件自己也在扫描面内，写完整字面量会让门常驻报红。
   新增注入样本请沿用 `_token`。
9. **`mimeconform/devtools/stdlib_compare.py` 是全仓唯一允许 `import email` 的文件**；
   `tests/test_engine_guards.py` 的 `ENGINE_MODULES` 是"必须无 email 导入"的**显式清单**——
   M2–M5 新增模块（如 `report.py` 已在内）要**同步加进这个元组**，否则新模块不受守门。
10. **版本号两处必须同改**：`pyproject.toml` 的 `version` 与 `mimeconform/__init__.py` 的 `__version__`；
    `tests/test_version_and_packaging.py` 逐字断言相等。定版时（M6）还要连带重生成 golden 指纹。

---

## 三、下一棒待办（M1 数据先行）

按 `plan/04` 执行，顺序不得交换：

1. `mimeconform/devtools/gen_golden.py` 实现 `build()`：每个 case 一个纯函数返回 `(files, expect)`；
   `_self_check()` **挂在 `build()` 末尾**（不是 `__main__`——`--check` 走 `build()`）。
2. 按 `plan/04` §二的矩阵落地全部 case（每规则簇 ≥2 正例 + ≥1 负例），含题面点名的 11 个复现项。
3. `expect.json` 的 `defect_count` / `exit_code` 必须**由构造算出**（`decide_exit_code`），不手写魔数。
4. `--check` 位级一致：写盘用 `write_bytes()`；临时目录在系统 temp，不落仓库。
5. 补齐 `tests/`：`test_generator_check.py`、把 `test_fixture_hygiene.py` 里两条 skip 转成真判据、
   `selftest` 的真命令回归（`selftest` 现在对真实语料跑数据级校验，M1 后必须绿）。
6. 回写 4 处状态副本（M1 → ✅），写 `plan/HANDOFF-M2.md`，提交。

**M1 完成的判据**：`py -3.12 -m mimeconform.devtools.gen_golden --check` → `N cases, 0 diff`；
`py -3.12 -m mimeconform selftest` → 0 且 `N cases, 0 问题`；`git status --porcelain` 为空。

---

## 四、既定口径清单（K 编号 —— "动了会打挂测试"的约定）

| K | 口径 | 打挂它的测试 |
| --- | --- | --- |
| K1 | 数值口径只有一处：`data/README.md` §七；代码常量只在 `mimeconform/constants.py` | 全仓无第二处定义；新增阈值必须先进 §七 |
| K2 | `class` 三值 / `severity` 四档的代码侧来源只有 `constants.CLASSES` / `SEVERITIES` | `test_ledger_invariants.py`、`test_catalog_gate.py` |
| K3 | 指纹算法按 `data/README` §7.8 逐字实现，键序固定，**不含 `detail`** | `test_ledger_invariants.py::test_fingerprint_ignores_detail_wording` |
| K4 | 退出码 `--fail-on` **只会更严**，永不推翻 major/blocker → 3 | `test_exit_codes.py::test_fail_on_never_softens_baseline` |
| K5 | `argparse` 的用法错误一律映射为 **1**（不是 argparse 自带的 2） | `test_cli_contract.py`（未知子命令 / 缺参 / 坏枚举各一条） |
| K6 | 路径语法：`0` / `0.1` / `msg#3` / `msg#3/0.1`；`msg#n` 的 n 从 1 起 | `test_ledger_invariants.py::test_path_*` |
| K7 | 行切分只走 `scan.split_lines()`（按 `\n`，不吞 `\r`，不把 `\x0b` 当行界） | M2 起加"与 `bytes.splitlines` 差异"回归 |
| K8 | `SEMANTIC_RULES` == `data/README` §7.1 升级禁令列表 | `test_catalog_gate.py::test_semantic_rules_set_covers_the_documented_families` |
| K9 | `ENGINE_MODULES` 是守门的显式清单，新增模块必须同步 | 新增模块漏加时守门静默失效 → 检视 `test_engine_guards.py` |
| K10 | 脱敏门扫描面收编规则：`.gitignore` 声明的本地产物目录必须在 `SKIP_DIRS` 有对应项 | `test_gates.py::test_desensitized_skips_local_artifacts` |
| K11 | 布局门判据 id 集合固定（9 条），改门必须同改 `test_gates.py` 的期望集合 | `test_gates.py::test_layout_gate_reports_every_check` |
| K12 | 状态副本 4 处 + 每副本命中行数必须 > 0 | `LAYOUT.STATUS` + `test_gates.py::test_layout_gate_status_copies_all_contribute_rows` |

---

## 五、本机环境坑（实测，2026-10-27）

| 事实 | 命令与输出 | 后果 |
| --- | --- | --- |
| 解释器 | `py -0p` → `3.8-64`（3.8.8）、`3.12-64`（3.12.10） | **3.8 低于本项目下限 3.11，不得用作验证通道**；本机只有 3.12 一条可用 |
| 跑 Python | `py -3.12 -X utf8 <cmd>` | 中文控制台编码；`-X utf8` 只管"我们敲的命令"，管不到子进程与 CI |
| PyYAML | `py -3.12 -c "import yaml"` → `6.0.3` | 已装；但 CI 必须靠 `[dev]` 声明，不能靠"本机碰巧有" |
| Node | `node --version` → `v24.15.0` | 本项目**不用** Node：两道门是 Python 标准库实现（D14） |
| Git | `2.54.0.windows.1`，`git remote -v` **为空** | 无远端 → 一切"CI 绿"只能写"本地等价校验（未接远端，CI 待首推验证）" |
| 建立 venv | `py -3.12 -m venv <dir>` | **3.12 的 venv 不再自带 setuptools**：`pip install -e .` 直接报 `BackendUnavailable: Cannot import 'setuptools.build_meta'`；先装 `setuptools>=68`（本机走 `-i https://pypi.tuna.tsinghua.edu.cn/simple` + `NO_PROXY="*"`）再 `--no-build-isolation` 安装 |
| pip 代理 | 系统代理可能污染 pip | 用 `NO_PROXY="*" no_proxy="*"` + 镜像；本项目运行时零依赖，只有 dev extra 需要网络 |
| `gh` 未使用 | — | M6 才需要；注意 `gh` 是原生程序，不认 Git Bash 的 `/tmp` 路径 |

---

## 六、DoD 逐项 checklist（M1）

- [ ] `data/rfc-ledger.json` 无需改动（除非发现人读台账有误——那时**两处同改** + `test_ledger_mirror.py` 必须仍绿）
- [ ] `gen_golden.py` 的 `build()` 与 `check()` 真实现；`_self_check` 在 `build()` 内
- [ ] `data/golden/` 覆盖 `plan/04` §二 全部 case（含 #69914 / #56141 / #93376 / SO 44154520 / 52442469 / 79133579 / 6029218 / 6255202 / 12816042 / 10107788 / 39328935）
- [ ] 每个 case 目录三件齐：`msg.eml`（或 `mail.mbox`）、`expect.json`、`README.md`（来源标注 + 复现命令）
- [ ] `--check` 位级一致；`git status --porcelain` 干净
- [ ] `py -3.12 -m mimeconform selftest` → 0
- [ ] `py -3.12 -X utf8 -m pytest` 全绿；两条 skip 已转成真判据
- [ ] 布局门 + 脱敏门 + 变异验证全绿
- [ ] 状态副本 4 处同翻 M1 → ✅
- [ ] `plan/HANDOFF-M2.md` 落盘并提交

---

## 七、关键命令速查

```bash
# 续接对话第一件事
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 全量测试 + 门的变异验证
py -3.12 -X utf8 -m pytest -q
py -3.12 -X utf8 tools/verify_layout_gate.py

# 语料（M1 落地后可用）
py -3.12 -m mimeconform.devtools.gen_golden --check
py -3.12 -m mimeconform selftest

# CLI 冒烟（两条通路都要）
py -3.12 -m mimeconform --version
mimeconform --version

# 干净环境（发布级）
py -3.12 -m venv <dir> && <dir>/Scripts/python.exe -m pip install "setuptools>=68" && \
  <dir>/Scripts/python.exe -m pip install --no-build-isolation ".[dev]"
```

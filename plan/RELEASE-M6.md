# RELEASE-M6 — 发布留档（mimeconform 1.0.0）

> **两栏结构**：`§一` 是 **tag 前** 落盘的事实（**它进 tag 树**）；`§二` 是 **tag 后** 追加的事实
> （tag 树不变 → 源码包字节不变 → 里面写的 sha256 / run id 永不失效）。
> **自指纪律**：凡"写它这个动作会改变它"的值（源码包 sha256 / tag 对象 OID / tag 指向的 commit /
> 上传本次留档那笔 push 的 run 计数）**一律只写进 §二**；§一 只写结构与方法，必要时写"见 §二"。
> 判别 = "这个值是被 tag 的那棵树的摘要吗？"——是就挪出 §一。

---

## 一、tag 前事实

### 1.1 定版

| 项 | 值 |
| --- | --- |
| 版本 | `1.0.0`（首个发布版） |
| 版本真源 | `pyproject.toml` 的 `project.version`；`mimeconform.__version__` 与之逐字相等（`tests/test_version_and_packaging.py::test_package_version_matches_pyproject` 断言） |
| 版本号出现处 | `pyproject.toml` / `mimeconform/__init__.py` / `README.md`（安装节）/ 发布包名 `mimeconform-1.0.0.tar.gz` —— 四处同串 |
| Python 下限 | `>=3.11`（`requires-python`，D13） |
| 交付形态 | 纯本地 CLI、**零第三方运行时依赖**（`dependencies = []`，机器断言）；不发 PyPI、不发 wheel |

### 1.2 干净环境验证（仅 CPython 的 venv）

venv 建在仓库外（`%TEMP%` 下的新目录），**未装过 editable**，装完后 `import mimeconform`
解析到 `site-packages`（不是工作树），因此下列结论不是"照抄工作树"。

| 步骤 | 命令 | 实测 |
| --- | --- | --- |
| 纯 CPython venv | `py -3.12 -m venv <tmp>` → `pip install "setuptools>=68"` | venv 内仅 `pip` / `setuptools` |
| 安装 | `pip install --no-build-isolation ".[dev]"` | `Successfully built mimeconform` + `mimeconform-1.0.0` wheel 安装成功 |
| 裸 console script | `mimeconform --version` | `mimeconform 1.0.0`，rc=0（**裸命令首次真实可用**） |
| 模块入口 | `python -m mimeconform --version` | `mimeconform 1.0.0`，rc=0 |
| 语料自检 | `mimeconform selftest --data-dir <repo>/data/golden` | `51 cases, 0 问题`，rc=0 |
| 全量测试 | `pytest`（venv 内，仓库根） | `682 passed, 1 skipped`，rc=0 |

### 1.3 README 命令逐条实跑（干净 venv，cwd 在仓库外）

所有命令都以**绝对路径**指向 `data/golden/**` 的合成样本；全部 rc 与 README 声明一致：

| README 场景 | rc | 断言到的内容 |
| --- | --- | --- |
| `audit data/golden/b-inner-dup/msg.eml --out /tmp/dup.json` | 3 | `tree_alternatives=2`、`divergence.path="0.1"`、MC-B06 `hard/major` @ 223 |
| `audit data/golden/b-clean-nested/msg.eml --format json` | 0 | 缺陷 0（负例） |
| `audit data/golden/a-body-attach/msg.eml --format md` | 0 | MC-A01 `diff/note` @ 313（SO 6255202） |
| `audit data/golden/h-ew-newline/msg.eml --format json` | 0 | MC-H12，`related` 含被压掉的 MC-H03 |
| `audit data/golden/t-qp-artifact/msg.eml --format json` | 3 | MC-T07 `hard/major` ×3 @ 281/316/362 |
| `audit data/golden/a-cid-open/msg.eml --format json` | 0 | MC-A04（`cid:` 无对应 Content-ID） |
| `audit data/golden/c-from-unescaped/mail.mbox --format json` | 0 | MC-C02（auto→mboxcl）；三张切分表 `{mboxo:3, mboxrd:3, mboxcl:2}` |
| `audit data/golden/c-from-unescaped/mail.mbox --mbox-variant mboxo --format json` | 0 | 同一文件换成 MC-C04（读法分歧，§7.7 口径） |
| `audit data/golden/c-from-bad/mail.mbox --mbox-variant mboxo --format md` | 0 | MC-C01 @ `msg#2` offset 0（cpython #93376） |
| `audit data/golden/c-maildir-name/maildir --format json` | 0 | MC-C05（Maildir 条目缺 `:2,<flags>`） |
| `audit <eml> --out <dir>/` | 3 | 目录形态：`report.json` + `report.md` 两件同写 |

`audit <eml>`（不带 `--format`/`--out`）实测**同时**把 JSON 与 Markdown 写到 stdout，rc 依缺陷面决定。

### 1.4 质量门（本机，`py -3.12 -X utf8`）

| 门 | 命令 | 实测 |
| --- | --- | --- |
| 布局门 | `tools/check_sprint_layout.py` | 9 条判据全 PASS；`files 14 / sections 8 / handoffs 5 / gap_rows 8 / ledger 1 / doc_tools 3` |
| 布局门变异自证 | `tools/verify_layout_gate.py` | **16 组：16 符合预期 / 0 不符** |
| 脱敏门 | `tools/check_desensitized.py` | 172 个文本文件，0 命中（豁免 2 份） |
| 全量测试 | `pytest` | `682 passed, 1 skipped`（skip = `test_real_catalog_is_absent_and_reports_cleanly`，M3 后由真实门禁取代，遗留为显式 skip） |
| 生成器可重建 | `mimeconform.devtools.gen_golden --check` | `51 cases, 0 diff` |
| 语料数据级校验 | `mimeconform selftest` | `51 cases, 0 问题` |

**变异靶子的瞬态化处置（本轮修的真缺陷）**：`verify_layout_gate.py` 的 M11 / M13 / M14 原本锚在
"M6 未开始"这件事上（靠变异把 `plan/00` 的 M6 行临时翻 ✅ 来激活 `LAYOUT.RELEASE` / `LAYOUT.HANDOFFS`）。
M6 真翻 ✅ 之后，这个前提消失 → 三组会变成"期望红实际绿"。**处置不是删测试**，而是给变异脚本加
`ensure_m6_done` seam：`plan/00` 的 M6 行仍是待办态时临时翻 ✅ 再施加主编（`plan/00` 逐字节还原），
已是 ✅ 时不动。判据面一条不减，且从此与项目进度解耦。M11 的靶子同时从"翻状态行"改成"删发布留档"。

### 1.5 脱敏四步（逐项留档）

| # | 步骤 | 命令 | 结论 |
| --- | --- | --- | --- |
| 1 | 常驻门 | `tools/check_desensitized.py` | 172 文件 / **0 命中**（4 条规则：盘符路径 / MSYS 用户路径 / 本机用户名 / 回环代理端口） |
| 2 | 入库面 | `git ls-files '*.eml' '*.mbox' '*.mbx' '*.msg'` | 50 个文件，**全部落在 `data/golden/**`**；无其他路径 |
| 3 | 内容级复核 | 全跟踪文本文件扫「密钥赋值 / `.env`/私钥文件名 / 非 `example.invalid` 邮箱 / 手机号 / 身份证 / 真实盘符路径 / 内网 IP / 回环端口」 | 仅 2 处命中，均为 `tests/test_fixture_hygiene.py` 里**故意的阳性对照样本** `alice@mail.google.com`（该测试的存在理由是证明"真实域名必须被检出"），非泄漏。其余类别 0 命中 |
| 4 | 提交身份 | `git log --format='%an <%ae> \| %cn <%ce>'` 全历史去重 | 唯一身份 `yuluo554 <282769740+yuluo554@users.noreply.github.com>`（GitHub noreply 地址，不含真实邮箱） |
| 5 | 历史面 | `git rev-list --all` 全树 grep 强标记 | 命中仅 golden 的 sha256 十六进制串与上述测试样本，无语义泄漏 |
| 6 | 解包后再扫 | 源码包解包后重跑脱敏门 | 见 §二（tag 后附件的实测值） |

**姊妹项目表述**：全仓 grep `10-<两位>-<slug>` / `同系列` / `姊妹` 只命中本仓自己的目录名与
`pyproject` 的 Homepage（本项目坐标，有意公开）。**无**对其他项目的提名 → 品牌隔离成立，无需掩码。

### 1.6 名字占用核对（建仓之前）

| 面 | 命令 | 结果 |
| --- | --- | --- |
| PyPI 包名 | `curl -s -o /dev/null -w '%{http_code}' https://pypi.org/pypi/mimeconform/json` | **404**（未占用） |
| GitHub 仓库名（`mimeconform`） | `gh api "search/repositories?q=mimeconform+in:name" --jq .total_count` | **0**（来自成功响应，非限流假 0） |
| GitHub 仓库名（`10-27-mimeconform`） | `gh api "search/repositories?q=10-27-mimeconform+in:name" --jq .total_count` | **0** |

结论：**核过、未占用**；不改名。本仓**不发 PyPI**，包名核对只为"CLI 名不撞车"。

### 1.7 覆盖对账（阶段 7 出口门逐条）

> 三态语义：**实现** = 有门覆盖或本轮实测过（贴命令/输出）；**不适用** = 本项目形态不涉及（写具体理由）；
> **待首推** = 无远端期间无法本地证，首推后回填（**不得写成已实现**）。

| # | 阶段 7 出口门 | 状态 | 证据 / 不适用理由 |
| --- | --- | --- | --- |
| 1 | 发布物本体已验（真下载 + 中立目录） | 待首推 | 首推后可下载；本地已用"同 tag 重跑 `git archive` 与下载件 `cmp`"作等价证明，见 §二 |
| 2 | 名字占用核对在建仓之前 | 实现 | §1.6：PyPI 404 + 两个 `gh api` total_count = 0 |
| 3 | 入仓工具在无 `.git` 树里也要能跑 | 实现 | 布局门/脱敏门只读仓库内文件、不读 git 元数据；`tests/test_fixture_hygiene.py` 对无 `.git` 树显式 skip 而非假红。§二 在 `git archive` 解包树里复跑两道门 |
| 4 | 无网络 job 用嵌套 `docker run`（不是 job 容器 options） | 实现 | `.github/workflows/ci.yml` 的 `offline` job 是普通 runner + `docker build` + `docker run --rm --network none`（无 `container:` 块）；`tests/test_ci_workflow.py` 断言 YAML 可解析且每个 job 有 `runs-on` |
| 5 | 首推第四色·配置面（`PYTHONPATH` / 控制台编码 / 零依赖断言 / 离线镜像） | 实现（本机等价） | 扁平布局无需 `PYTHONPATH`；workflow 顶层 `PYTHONUTF8=1` + `PYTHONDONTWRITEBYTECODE=1`；零依赖断言未写进 CI（`dependencies = []` 由 `test_no_runtime_dependencies` 断言）；离线镜像 `COPY . /work` 扁平布局可直接 import。**真跑仍待首推** |
| 6 | 发布包实测 = README 每条命令在解包树里真敲 | 待首推 | 本轮已在**干净 venv + 仓库外 cwd** 逐条敲过（§1.3）；"在 `git archive` 解包树里敲"这一步在 §二 |
| 7 | 干净环境验证要连"真实输入"一起验 | 不适用 | 本项目输入是调用者自己的邮件字节，无"系统库/真实数据根"这类会被缺省值换掉的输入集合；README 每条命令都显式给出输入路径，不靠缺省 |
| 8 | "干净环境"第一分支 = 无本地数据缓存 | 不适用 | 全部语料 `data/golden/**` **入仓**（50 个 `.eml`/`.mbox` 均在 `data/golden/` 下），无"不入仓的下载件"；干净 clone 即完整 |
| 9 | tag 树内留档的自指约束（只写结构、字面值挪到 tag 后） | 实现 | 本文件两栏结构；§一 零 sha256 / 零 tag OID；§二 承接字面值 |
| 10 | 附件与 tag 树逐字节同源 | 实现（构造即同源） | 附件由 `git archive <tag>` 直接产出（D15：无构建步骤、无 sdist 中间层），因此"附件 ↔ tag 树"不存在派生偏差；§二 记录两次 archive 的 `cmp` |
| 11 | 内容寻址的随包数据行尾归一 | 不适用 | 本项目无"随包数据快照 + 运行期校验摘要"的形态（golden 是测试语料，`expect.json` 里的 sha256 是**输入邮件**的摘要，由生成器逐字节核对，`--check` 覆盖） |
| 12 | 源码包自足 | 实现 | `MANIFEST.in` 白名单 `include LICENSE/README.md/pyproject.toml/AGENTS.md` + `recursive-include mimeconform *.py *.json` + `recursive-include data *.json`；`tests/test_packaging.py` 反查实物（每条 `include` 真存在、每条 `recursive-include` 至少命中一个文件） |
| 13 | 构建必须晚于交付面定稿 | 实现 | 发布物是 `git archive`（无构建步骤），其内容恒等于 tag 树的 blob；版本号与 README 状态表在本笔提交里定稿，tag 打在这笔之后 |
| 14 | README 提到的附件名必须真在 Release 里 | 实现（待首推核） | README 安装节写的附件名 `mimeconform-1.0.0.tar.gz` 与 §二 上传的名一致；Release 附件在首推后上传 |
| 15 | 发布附件口径 = 手工源码包而非 GitHub 自动 Source code | 实现 | D15 + `plan/02` §十一；§二 记录 `git archive --format=tar --prefix=mimeconform-1.0.0/ <tag> \| gzip -9n` 与 `SHA256SUMS` |
| 16 | 附件 sha256 只写进 tag 后 / Release 正文 | 实现 | §一 不写哈希；§二 + Release 正文 |
| 17 | 版本号"四处一致"由机器断言 | 实现 | `tests/test_version_and_packaging.py`（两处逐字相等 + 形态正则）；`tests/test_readme_gate.py`（README 写了下限与 extras）；本文件 §1.1 列出全部出现处 |
| 18 | DoD 打勾只在事实落地后 | 实现 | 本文件 §一 只写本轮实测；未跑项标 `待首推`，不预填 |
| 19 | 随包 README 的状态行不承载"发布到哪一步" | 实现 | README 状态表只有里程碑 M0–M6 的完成态，不写"已 Release / 已上传" |
| 20 | 定版会改变参与摘要的指纹字段 → 样例同轮重生成 | 实现 | `fingerprint` / `tree_digest` 只由缺陷集与树形决定，**不含工具版本**；定版后 `gen_golden --check` 仍 `51 cases, 0 diff` |
| 21 | `POST_TAG` 处置 = 声明 + 可核对 | 实现 | tag 之后只允许文档面提交：§二 回填、状态行不复改代码。tag 后那笔提交只动 `plan/` |
| 22 | annotated tag 两端一致 = 对象哈希一致 | 实现 | 用 annotated tag；§二 记录 `git rev-parse v1.0.0` 与 `^{commit}` 的**结构**（字面值在 tag 后提交里，避免自指） |
| 23 | tag 之后只允许文档面提交 | 实现 | `git diff --stat v1.0.0..HEAD` 在 §二 记录"只涉及 `plan/`" |
| 24 | push 数 = run 数对账 | 待首推 | 首推后按 `gh run list` 计数回填 §二 |
| 25 | 四矩阵同点全红 = CI 接线缺陷 | 待首推 | 矩阵为 **2 OS × 3 Python = 6 格** + 1 个 `offline` job；本地无法证 |
| 26 | 每条已交付命令都有一条离线 CI 冒烟 | 待首推 | workflow 内已有 `mimeconform --version` / `python -m mimeconform --version` / 契约退出码 1 三条冒烟；真跑待首推 |
| 27 | tag push 与 branch push 各一条 run | 待首推 | 首推后回填 §二 |
| 28 | CI 检出形态会让"标注 tag 对象"整类不存在 | 不适用 | 本项目 CI 不做 tag 对象校验（布局门不读 git 元数据，这是设计选择） |
| 29 | 推送前先在本地 `yaml.safe_load` 解析 workflow | 实现 | `tests/test_ci_workflow.py`（YAML 可解析、job/step 结构、`set +e` 契约、step name 是 str、退出码 ∈ {0,1,2,3}） |
| 30 | 发布终态自检门可复跑 | 实现 | 布局门 `LAYOUT.RELEASE` 判据（两栏标题 + 覆盖对账小节 + ≥3 条三态行）；`tools/verify_layout_gate.py` 的 M11 打它 |
| 31 | 产物必须包含"能核对自身"的判据 | 实现 | `tools/` 随源码包发布；§二 在 `git archive` 解包树里重跑布局门 + 脱敏门 + 变异自证 |
| 32 | 离线模式报 SKIP 不报 PASS | 不适用 | 本项目无"离线模式"开关（零网络是常态，无 `--online` 分支） |
| 33 | 发布门输入全部不可信（tag 名白名单 / SHA256SUMS 文件名防穿越 / 归档成员防 zip-slip） | 不适用 | 本项目无发布门脚本（布局门只读仓库内固定路径，不回显外部输入；附件由 `git archive` 产出，无解包逻辑） |
| 34 | 门的结果会被"为满足它而写入的产物"改变 | 实现 | §一 不写"门全绿"的结论进任何被门读取的位置；`plan/06` 缺口行只描述不点文件名（假门族 ⑧） |

**覆盖结论**：34 条出口门逐条有归宿——**实现 21 / 不适用 6 / 待首推 7**。`待首推` 的 7 条全部与"无远端"
相关，首推后回填 §二；**没有一条是"暂不/后续"**。

---

## 二、tag 后追加

> **本节在 tag 树里是骨架**（tag 那一刻这些值还不存在）。字面值由 tag 之后那笔**只动 `plan/`** 的提交回填。
> 回填纪律：只写实测到的；未拿到就保留 `⬜ 待回填` 并写明原因，不留空、不预填。

### 2.1 源码包与校验和

| 项 | 值 |
| --- | --- |
| 产物名 | `mimeconform-1.0.0.tar.gz`（310,267 bytes） |
| 生成命令 | `git archive --format=tar --prefix=mimeconform-1.0.0/ v1.0.0 \| gzip -9n > mimeconform-1.0.0.tar.gz` |
| **sha256（源码包）** | `e43737e501ec5d880ac15bf30483062eedaa3f054347e8624d88ff78fceb0da0` |
| **sha256（SHA256SUMS）** | `32326fbcaf383bd787e92ffe750387dc14767e5bfcfcde34e1fe13ce05a8cc07` |
| 复算证明（两次 archive） | 同命令连跑两次 → `cmp` **逐字节一致** ✓ |
| 真下载复核 | `gh release download v1.0.0` 取回的附件与本地副本 `cmp` **逐字节一致** ✓ |
| 第三路证明 | 从 tag **重新** `git archive \| gzip -9n` → 与下载件 `cmp` **逐字节一致** ✓（不依赖任何写死的值） |
| 解包树复跑 | 解包（224 个文件、**无 `.git`**）后：布局门 9/9 PASS（handoffs 6、RELEASE 两栏 True / 三态行 35）、脱敏门 173 文件 0 命中、变异自证 **16 组 16 符合预期**、`selftest` `51 cases, 0 问题`、`gen_golden --check` `51 cases, 0 diff`、`pytest` **682 passed / 2 skipped**（多出的 1 个 skip = `test_golden_files_are_committed_only_under_golden` 对无 `.git` 树显式跳过，是设计意图） |

### 2.2 tag 与 run

| 项 | 值 |
| --- | --- |
| tag | `v1.0.0`（**annotated**） |
| 远端 tag 对象 | 远端 `refs/tags/v1.0.0` = `6cc3cb4e81245d5bf649ba6b4dbad4ce0222dfff` |
| tag 指向的 commit | `716046c794e8bf64d90945ca74af58dd5c297f35`（= 翻 ✅ 那笔；`git cat-file -e v1.0.0:plan/RELEASE-M6.md` 通过） |
| 分支 | `main` |
| 仓库 | `https://github.com/yuluo554/10-27-mimeconform`（**公开**，`private=false`，默认分支 `main`） |
| 首推 run（branch，交付面定稿笔） | `40632187803` — **success**；7 个 job 全绿：`py3.11/3.12/3.13` × `ubuntu/windows` 六格 + `offline (no network at runtime, no third-party imports)` |
| 第二笔 run（branch，翻 ✅ 笔） | `40632496863` — **success**；同样 7 个 job 全绿 |
| **tag push run** | `40633183415`（event=`push`, branch=`v1.0.0`）— **success**，47s |
| push 数 = run 数对账 | **截至 tag push：3 笔 push → 3 个 run**（`40632187803` 交付面定稿 / `40632496863` 翻 ✅ / `40633183415` tag push）= 相等，均 success。**自指声明**：此后每笔 `plan/` 回填提交都会再添一笔 push 与一个 run，"/ 最后一个 run 数"这类值**永远写不稳**，故本表只对账到 tag push 为止；回填笔的 run 不登记（写了也会因为"写它"这个动作而再次失效） |
| tag 后提交面 | `git diff --stat v1.0.0..HEAD` = 4 个文件、全部以 `plan/` 开头（`00-README总览` / `05-里程碑与验收` / `06-交付对标与决策` / `RELEASE-M6`），**代码面与交付面零改动** ✓ |
| Release | `https://github.com/yuluo554/10-27-mimeconform/releases/tag/v1.0.0`；附件 **2 个**：`mimeconform-1.0.0.tar.gz` + `SHA256SUMS` |

### 2.3 回填时的实测记录

- **`POST_TAG` 声明**：tag `v1.0.0` 建立后，本仓库**没有**再改代码面——tag 之后只提交 `plan/` 下的
  文档回填（本节 + §一 的 `待首推` → 实测值）。核验方式 = `git diff --stat v1.0.0..HEAD`
  的文件清单全部以 `plan/` 开头（2.2 表已记实测清单）。本笔回填自身的 run 为
  `40633503969`（success），**仅作过程事实登记**：它不参与 2.2 的"push 数 = run 数"对账
  （那条只对账到 tag push），因为每写一次都会再添一笔。
- **覆盖对账的 7 条 `待首推` 归宿**（对应 §1.7 的 #1 / #6 / #23 / #24 / #25 / #26 / #27）：
  首推与 tag push 均全绿（run id 见 2.2），逐条已由真实 run 证；#6 的"解包树里逐条敲 README"
  与 #1 的"真下载 + 中立目录"在 2.1 的"解包树复跑 / 真下载复核 / 第三路证明"三行里完成。
  因此 §1.7 的**待首推 7 条全部关闭**，无一遗留。
- **tag 树内那两栏是骨架**这一点已兑现：§一 全文零 sha256、零 tag OID（本轮回填把它们只写进本节）。
- **诚实口径**：本轮没有在 `py3.11` / `py3.13` 的**本机**跑过任何东西（本机只有 3.12.10）；
  跨版本结论的唯一来源是 CI 矩阵（run id 见 2.2）。本机离线闭环（无 docker）仍未做——
  `offline` job 的证据来自 CI，本机仅有"零网络 import 的 AST 守门"作等价证明。

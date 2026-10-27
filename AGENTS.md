# AGENTS.md

本仓库遵循 **`ai-tool-project-sprint`** 方法论（装订日期：2026-10-27）。

## 任何新对话的第一件事

```bash
python tools/check_sprint_layout.py    # 布局门；必须绿，红了先修布局再干活
python tools/check_desensitized.py     # 脱敏门；命中本机路径/用户名/回环代理即红
```

- 续接对话：读 `plan/HANDOFF-M<k>.md`（那是第 k 棒的收尾交接单），**先跑上面两条门**。
- 接手对话（无 HANDOFF）：先读 `plan/00`、`plan/05`、`plan/06` 与各 HANDOFF，重建"当前状态 + K 口径清单"再动手。
- **门不存在 = 本项目没装订** → 先补第零步（`AGENTS.md` + `tools/check_sprint_layout.py` + `plan/00` 顶部一行），再做别的。

## 强制布局（布局门逐条断言，改动前先看这里）

| 项 | 位置 | 判据 |
| --- | --- | --- |
| 计划套件 | `plan/00`–`06` + `data/README.md` | 存在且各含必需小节（标题关键词） |
| 数据台账 | `data/README.md` + `data/rfc-ledger.json` | 台账在位（来源 + 三态 + 原句留档状态） |
| 交接单 | `plan/HANDOFF-M<k>.md` | 每个 ✅ 里程碑一份（M0 为声明豁免：其收尾记录即计划套件本身）；七节齐 |
| 里程碑状态副本 | `plan/00` 里程碑表 + `plan/00` 台账行 + `plan/05` 状态表 + `README` 状态表 | **逐处一致**，枚举式断言；每份副本的命中行数打进结论 |
| 发布留档 | `plan/RELEASE-M6.md`（两栏）或 `plan/WRAPUP-M6.md` | 发布里程碑 M6 翻 ✅ 后才要求；未翻时本项报 PASS 并写明不适用 |
| 发布门覆盖对账 | `plan/RELEASE-M6.md` §覆盖对账 | 阶段 7 出口门逐条：实现 / 不适用+理由 / 待首推 |
| 文档点名的工具 | `tools/*.py` | 文档里出现的 `tools/...` 必须存在；未到里程碑的登记在 `PENDING_TOOLS` |

## 环境事实与禁忌（实测日期 2026-10-27）

- 本机解释器：`py -3.12`（3.12.10）可用；`py -3.8`（3.8.8）存在但**低于本项目底线 3.11**，不可用于验证。
- 本机 Node：`v24.15.0`（本项目门槛不依赖 Node，门一律用 Python 标准库写）。
- 本机 Git：`2.54.0.windows.1`。**尚无远端**（`git remote -v` 为空）→ 任何"CI 绿"只能写"本地等价校验（未接远端，CI 待首推验证）"。
- 跑 Python 一律 `py -3.12 -X utf8`；Git Bash 下 `/tmp` 与 Windows Python 路径不通，临时文件用工作区外目录或 `tempfile`。
- 禁止：把"未执行"写成已完成；在 tag 之后改代码面；用 `import email` 实现审计引擎（只允许 `mimeconform/devtools/`）；在任何源码/测试/示例里写入可用凭据字面量。

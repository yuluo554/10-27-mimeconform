# golden case: a-name-mismatch

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造归属样本（无外部来源）
- 输入：`msg.eml`（458 bytes；sha256 `37396b2180a5cafb05f0a28ebdba8e8f5d5f355b146b0f9962fc5cf53efc7ebf`）
- 期望指纹：`da86e761d857494a471ba575df0302b1c29ee39356267315d2b0a3209adb13f7`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/a-name-mismatch/msg.eml`

## 说明

filename 取值顺序（先 2231 后 2047）与多字段弥合的记录口径见 `data/README.md` §7.5。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-A02 | diff | note | 0.2 | 341 | absolute | none-by-design | Content-Type 的 name="a.pdf" 与 Content-Disposition 的 filename="report.pdf" 不一致（下游按不同字段取名会得到两个名字） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


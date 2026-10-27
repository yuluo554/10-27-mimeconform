# golden case: a-noname

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：SO 12816042——原话：PDF attachment is called Noname（缺 filename 参数）
- 输入：`msg.eml`（410 bytes；sha256 `7122503588005159dc390264719a3f15db328921e6b568ea02c4b15c779283d9`）
- 期望指纹：`fc16c0b18624d381bf0c944a599250068ac07c8920a9d54611a1abc6d3d6f724`
- 树指纹：`5a123b34fc028d734bdd1604aca5cf6b15e11d908dae499a8fd2a407c53cd74d`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/a-noname/msg.eml`

## 说明

`plan/03` §四 原写 minor，与 §7.1 原句门禁冲突 → M1 落 note（同轮修正摘录）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-A03 | diff | note | 0.2 | 316 | absolute | none-by-design | attachment 没有任何 filename / name 参数：下游把附件显示成 Noname（SO 12816042 的形状） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


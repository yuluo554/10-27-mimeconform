# golden case: t-b64-foreign

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（261 bytes；sha256 `f96a4da0a7c61b20d0e7d5207a9a2c458a96a0d31935d3717a4c675fff344931`）
- 期望指纹：`98fe37492eba18b840a6eca24c11b9ac42ca1e3edd37ac8760e92fac4447cb60`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-b64-foreign/msg.eml`

## 说明

§7.1：本条子项原句**全录** → 证据强度是 hard；但现象不构成违规 → severity 只能是 `note`。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T04 | hard | note | 0 | 254 | absolute | RFC 2045 §6.8 | base64 出现字母表外字符 `*`（RFC 2045 §6.8 原句要求忽略它 → 出现本身不是违规，只登记并计入 foreign_chars） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


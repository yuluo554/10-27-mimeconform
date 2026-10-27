# golden case: t-qp-soft

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 2
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（308 bytes；sha256 `bd835ed2244080612a7788960772b440bf8cbdc9e66d4ffea93126497b273dc0`）
- 期望指纹：`f1d5b0b0180acf709b6394bf6f7a17929f0658324e7be51aa87a53c4e17eff3f`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-qp-soft/msg.eml`

## 说明

R8 全录原句：An equal sign as the last character on an encoded line indicates such a non-significant (soft) line break。判定按字节：行末 `=` 紧邻线性空白的情形按 §M3 纪律视为 `diff` 而非 `hard`，本 case 只钉「软换行之后无内容」这一硬形态。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T06 | hard | minor | 0 | 305 | absolute | RFC 2045 §6.7 | 行末 `=` 之后已无下一行（部件在此结束）：软换行无法接续，`=` 成了悬空转义 |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


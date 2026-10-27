# golden case: h-ew-line-long

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 2
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（275 bytes；sha256 `9d3bb0ed92af61e4d3e4e7af5afaf6a8d39950ecc8d9b3715b73cd6fe79ea252`）
- 期望指纹：`b48d98f8b409ae06918120a1ae696e7a0110c4efee2b978f0df8b1b5b063bc1e`
- 树指纹：`5c7d2edfce79ff71b63546792e45936677d2edb888760b007f0f563b76f0d5fd`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-ew-line-long/msg.eml`

## 说明

R2 全录原句；本 case 只超行宽（不超 encoded-word 长度），与 MC-H01 正交。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H02 | hard | minor | 0 | 3 | line | RFC 2047 §2 | 含 encoded-word 的头行 106 > 76 字符（encoded-word 本身 36 ≤ 75） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


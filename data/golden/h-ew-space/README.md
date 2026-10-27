# golden case: h-ew-space

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 2
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（197 bytes；sha256 `c3bdf1ef01c021a7389babd870a9952815b1bc67b328cf4e248b464d0b261f3f`）
- 期望指纹：`8581b408158738c083d43d2c9dc2cbe1433946f02917fb4b9e18fe81ace9ad8c`
- 树指纹：`5c7d2edfce79ff71b63546792e45936677d2edb888760b007f0f563b76f0d5fd`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-ew-space/msg.eml`

## 说明

与 MC-H12 互斥（§7.5 第 2 条）：无折行时只报本规则。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H03 | hard | minor | 0 | 63 | absolute | RFC 2047 §2 | encoded-word 内部出现空白（形态定义排除 LWSP；本样本无折行，不与 MC-H12 互斥） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


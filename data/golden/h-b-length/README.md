# golden case: h-b-length

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（201 bytes；sha256 `75435ef2791a24c0d703e40aa7b75c47234a29ed8241ff482c7c88c01d14fe84`）
- 期望指纹：`b084b813c816931413fcb51af7fe51dbe7443995586e4c99a1043d04c5c5d239`
- 树指纹：`5c7d2edfce79ff71b63546792e45936677d2edb888760b007f0f563b76f0d5fd`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-b-length/msg.eml`

## 说明

R4 §4.2 子项原句未录 → 只登记（§7.1）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H05 | diff | note | 0 | 63 | absolute | RFC 2047 §4.2（R4 该子项未录原句 → 门禁降级，只登记） | B 编码 base64 长度 11 不是 4 的倍数 |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


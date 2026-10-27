# golden case: h-q-invalid

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（196 bytes；sha256 `73a37c3f0a7b36109321109f116a7d370fec74f7db733ae84dc5f29cc9e15b9a`）
- 期望指纹：`32fb10a0f2f51a86c5e2284e0f46062f8f924897fc058848b84d8c2793e5aa09`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-q-invalid/msg.eml`

## 说明

R4 §4.1 子项原句未录 → 只登记（§7.1 门禁降级）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H04 | diff | note | 0 | 63 | absolute | RFC 2047 §4.1（R4 该子项未录原句 → 门禁降级，只登记） | Q 编码里 `=zz` 不是合法的 =HH 转义 |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


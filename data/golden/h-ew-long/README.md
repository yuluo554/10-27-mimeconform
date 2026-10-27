# golden case: h-ew-long

- 期望：正例（缺陷集非空）；缺陷数 2；退出码 2
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（270 bytes；sha256 `9b1d5ff8eaf5144078a4145220482073994d70b4df116f32dcf65bb384a6de3a`）
- 期望指纹：`34f2ffa40f62cbfaccd5af54fea3c789a0a5ad365d36ef5eef8af094b64d9efb`
- 树指纹：`5c7d2edfce79ff71b63546792e45936677d2edb888760b007f0f563b76f0d5fd`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-ew-long/msg.eml`

## 说明

R1 全录原句；长度按编码后 ASCII 字节计（本题保守口径）。**H01 与 H02 各自成账**：encoded-word 超 75 时其所在行必超 76 —— 不算双记（§7.5 的互斥只约束 H12/H03）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H01 | hard | minor | 0 | 63 | absolute | RFC 2047 §2 | encoded-word 长度 92 > 75（按编码后 ASCII 字节计） |
| MC-H02 | hard | minor | 0 | 3 | line | RFC 2047 §2 | 含 encoded-word 的头行 101 > 76 字符（H01 的必然连带：encoded-word 自身超长时其所在行必超行宽） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


# golden case: t-b64-pad

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（246 bytes；sha256 `c70e6b0c07911153c1f4355df3053680cab25f53c95cf80c129457dfaba1bc48`）
- 期望指纹：`fb7c1db10759155cf404acce311b9054ba1f430e0fe7a293d79a731d16eb1a04`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-b64-pad/msg.eml`

## 说明

R9 的填充子项原句未录 → 只登记（§7.1 门禁降级）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T02 | diff | note | 0 | 238 | absolute | RFC 2045 §6.8（R9 的填充/长度子项未录原句 → 门禁降级，只登记） | base64 填充非法：`=` 之后仍有数据字符（填充只允许出现在末尾，且最多两个） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


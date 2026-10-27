# golden case: t-undeclared-8bit

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（210 bytes；sha256 `8f6f0992dbbb968b5546f5144082cb008055fb480722a94699642986021e73d4`）
- 期望指纹：`69ce2418508dfe5b7c4cfe70df62ebd303fae0c0f17309c77dbfc6d866112276`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-undeclared-8bit/msg.eml`

## 说明

缺省 7bit 的口径来自 R11 的 §6.1 子项（未录原句）→ 本条也只能出 `note`；补齐后提为 hard。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T10 | diff | note | 0 | 200 | absolute | RFC 2045 §2.7/§2.8/§6.1（R11 整行未录原句 → 门禁降级，只登记） | 未声明 Content-Transfer-Encoding（缺省为 7bit），但正文含 8bit 字节（R11 整行未录 → 只登记） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


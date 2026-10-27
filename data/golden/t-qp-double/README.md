# golden case: t-qp-double

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（307 bytes；sha256 `4142bdb08748133d269ba0c23608cd39aab1aa1bb08a85b77624d5a394c5ff09`）
- 期望指纹：`d724d49352e2eb6c5ebe42cff287c59b6b7b058d20790ab116747506695d6383`
- 树指纹：`bf476e46c71f4fb28f89d75cc98dc9920d37c0366fa217b69d276b4456592589`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-qp-double/msg.eml`

## 说明

`=3D` 在**编码态**正文里合法；本规则只在**解码后**仍见字面 `=3D` 时触发。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T11 | diff | note | 0 | 271 | absolute | none-by-design | QP 解码一遍之后正文里仍出现字面 `=3D`：上游疑似被编码了两次（只登记，不猜责任方） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


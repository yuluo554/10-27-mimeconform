# golden case: t-clean-b64

- 期望：负例（零缺陷）；缺陷数 0；退出码 0
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（326 bytes；sha256 `be4bb3df03bbf0b574fe0cfb94116b0eac570207b60fac42d7c52f3759effc9d`）
- 期望指纹：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-clean-b64/msg.eml`

## 说明

零缺陷基线：数据字符数 80（4 的倍数）、填充只在末尾且数量正确、无字母表外字符、行宽 ≤76。这条正是「合法 base64 折行」负例 —— 任何 T 簇误报都会打挂它。

## 期望缺陷

无缺陷（负例）。

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


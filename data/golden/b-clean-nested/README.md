# golden case: b-clean-nested

- 期望：负例（零缺陷）；缺陷数 0；退出码 0
- 来源：自造边界样本（无外部来源）
- 输入：`msg.eml`（610 bytes；sha256 `8a03ce7d352d3b66d250279d4cf40aed89170ea902a1abcbdfbc77a128dcec01`）
- 期望指纹：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-clean-nested/msg.eml`

## 说明

零缺陷基线：合法嵌套 + 合法 base64 附件；任何 B 簇误报都会打挂本 case。

## 期望缺陷

无缺陷（负例）。

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


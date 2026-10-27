# golden case: h-clean-folded

- 期望：负例（零缺陷）；缺陷数 0；退出码 0
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（239 bytes；sha256 `c82c95541579854959bf9859506947b4d87e7e903d076e9ee39060c1efb1fc16`）
- 期望指纹：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- 树指纹：`5c7d2edfce79ff71b63546792e45936677d2edb888760b007f0f563b76f0d5fd`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-clean-folded/msg.eml`

## 说明

零缺陷基线：两个 encoded-word 各自 ≤75、行 ≤76、之间有 FWS，且**每个 encoded-word 自身完整**（不跨行）→ 不构成 MC-H12。

## 期望缺陷

无缺陷（负例）。

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


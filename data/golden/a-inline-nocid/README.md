# golden case: a-inline-nocid

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造归属样本（无外部来源）
- 输入：`msg.eml`（438 bytes；sha256 `e1532c766f71148ba651f33893d6c58dd4df33e0e1df03d3a96a835078aed13a`）
- 期望指纹：`d5d5fb37306cd1734959d4864a18594245c9f6dd3e219a6d4bcc468f742dd7dc`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/a-inline-nocid/msg.eml`

## 说明

与 MC-A04 互不依赖：这里正文不引用 cid:，缺的是被引用的资格（Content-ID 本身）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-A07 | diff | note | 0.2 | 325 | absolute | none-by-design | disposition 是 `inline` 却没有 Content-ID：正文无法用 cid: 引用它（内嵌图不显示的一类成因） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


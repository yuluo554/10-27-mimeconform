# golden case: b-wrapped-header

- 期望：负例（零缺陷）；缺陷数 0；退出码 0
- 来源：cpython #56141（closed）—— issue 原话：Email multipart boundary detection fails on a wrapped header
- 输入：`msg.eml`（366 bytes；sha256 `fdd66dc9b8cab1766a82ff543e24fbed68a991bced0569b136765a4d6b098a82`）
- 期望指纹：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- 树指纹：`6e67a65899521c75ebb2a37577aac34d2c4df97ed334749455d840f772e96717`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-wrapped-header/msg.eml`

## 说明

头折叠（RFC 5322 §2.2.3 的 FWS）是**合法**形态：boundary 参数被折到续行上，本工具必须照常切出两棵子部件、零缺陷。历史 bug（#56141）正是折行头破坏边界检测。

## 期望缺陷

无缺陷（负例）。

## 标准库对照（实测留证）

```json
{
  "defects": 0,
  "note": "3.12.10 实测标准库已修复（解析正常、0 defect）——本 case 现钉住「折叠头必须被正确读成 multipart」这一回归面。",
  "types": []
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


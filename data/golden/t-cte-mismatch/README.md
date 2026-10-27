# golden case: t-cte-mismatch

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（297 bytes；sha256 `c29e4b50ff9db1563e0706870bebf2d44b9aac9d0df2bbb3c80f7a272ad89a1b`）
- 期望指纹：`4af3b03eba31ec3c1e8a225de5efe19c376fcee4aeaedcd265333858f23627cd`
- 树指纹：`03046992a7835f2c4e3a531a5ccd5a22bcd94abece4a9f8d578b54b480013854`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-cte-mismatch/msg.eml`

## 说明

D2 / §四.3：MC-T01 永远 `diff`，`rfc` 写 none-by-design —— 本题最需要克制的一格；退出码不变（note）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T01 | diff | note | 0 | 249 | absolute | none-by-design | 声明 base64、实际形态为明文（语义层判定，不是条款判定；不硬判 → 退出码不受影响） |

## 附加期望

```json
{
  "suppressed": [
    "MC-T02",
    "MC-T03",
    "MC-T04"
  ],
  "suppression_note": "observed 完全不是 base64 形态时不逐条登记字母表外字符/长度子项（否则同一段字节会出几十条 note 账）—— M4 以此为准"
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


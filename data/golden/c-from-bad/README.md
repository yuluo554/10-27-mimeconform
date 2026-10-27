# golden case: c-from-bad

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：cpython #93376（open）—— issue 原话：mailbox.mbox malformed From lines not being detected/handled
- 输入：`mail.mbox`（366 bytes；sha256 `b368d57224ca1f7013462161b5e300720dd56eb2858871a48ba26955da03e999`）
- 期望指纹：`2d574621be2fd2828bfd8ba1af403085693166ed127b7f16a39794763d2b5615`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/c-from-bad/mail.mbox`

## 说明

该行仍被当作消息边界（片段自身可解析）→ 唯一的问题是分隔行形态，不再叠报其他容器规则。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-C01 | diff | note | msg#2 | 0 | message-relative | none-by-design | 分隔行 `From alice@example.invalid` 缺日期字段（envelope 无法解析）：mbox 约定是 `From <地址> <日期>`，它不是 RFC（D3）→ 只登记（文件内位置见 expect_extra.file_offset） |

## 附加期望

```json
{
  "auto": "mboxo",
  "file_offset": 180,
  "variant_split_counts": {
    "mboxcl": 2,
    "mboxo": 2,
    "mboxrd": 2
  }
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


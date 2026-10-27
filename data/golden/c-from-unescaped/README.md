# golden case: c-from-unescaped

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：HN 32979369 / HN 6855700（mbox 转义问题；逐字原话见 data/README.md §1.4，本 case 只引编号、不改写引文）
- 输入：`mail.mbox`（486 bytes；sha256 `a761ad35bff399a14c4b7d49345905b76c05eae8398b3c8f1f1c2958565ac439`）
- 期望指纹：`942597257ea7c7c52d4f4221ae7e0d02d4bdcb5475e92b85e217663921b6f235`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/c-from-unescaped/mail.mbox`

## 说明

`auto` 按 §7.7 的纯字节规则：出现 `Content-Length:` 头 → mboxcl（本 case 的主表）。变体差异即本规则的证据。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-C02 | diff | note | msg#1 | 229 | message-relative | none-by-design | 正文里的 `From ` 行未转义（mboxo 约定应写成 `>From `）：mboxo/mboxrd 读法在此误切一条消息，mboxcl 按 Content-Length 不受影响 → 各变体切分表不一致，全部要输出 |

## 附加期望

```json
{
  "auto": "mboxcl",
  "content_length": 82,
  "variant_split_counts": {
    "mboxcl": 2,
    "mboxo": 3,
    "mboxrd": 3
  }
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


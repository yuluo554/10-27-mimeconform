# golden case: c-clean-mbox

- 期望：负例（零缺陷）；缺陷数 0；退出码 0
- 来源：自造容器样本（无外部来源）
- 输入：`mail.mbox`（587 bytes；sha256 `a01b3207881f22d32079d80b283078da80c45388b11d9d0f233a94cf33fff761`）
- 期望指纹：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- 树指纹：`None`（容器输入，自 M5 起回填）
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/c-clean-mbox/mail.mbox`

## 说明

零缺陷基线：`>From ` 行是**正确转义**（原正文行以 `From ` 开头）。它的读法差异（mboxo 保留 / mboxrd 反转义）属变体行为、不构成违规；MC-C02 只在「未转义（裸 `From ` 行被误当分隔行）」时触发。

## 期望缺陷

无缺陷（负例）。

## 附加期望

```json
{
  "auto": "mboxo",
  "variant_split_counts": {
    "mboxcl": 3,
    "mboxo": 3,
    "mboxrd": 3
  }
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


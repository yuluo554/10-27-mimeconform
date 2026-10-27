# golden case: a-cid-open

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：SO 10107788——原话：how to set a name of the embedded image（related / cid 归属）
- 输入：`msg.eml`（530 bytes；sha256 `2fb26410998164e932f1ea45b65eac06d9c3a10e3c32ada05cf7721e6c9c6ce8`）
- 期望指纹：`7591bd820d014ee611e4af7c4fd9370fa7576a30ade53f4706316b83aecd0373`
- 树指纹：`9251613d9186e9c3ea8c5462d8be9ed6c40894166a06ba013fb183395ee3dbed`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/a-cid-open/msg.eml`

## 说明

偏移锚在正文里的 cid: 引用本身（绝对字节偏移），报告能一眼回答「引用了谁、谁没到」。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-A04 | diff | note | 0.1 | 293 | absolute | none-by-design | 正文引用 `cid:img002@example.invalid`，但没有任何部件的 Content-ID 与之对应（img001 存在但没人引用）——比较按尖括号内字面值、不 URL 解码 |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


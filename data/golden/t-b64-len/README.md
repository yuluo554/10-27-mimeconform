# golden case: t-b64-len

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：SO 6029218——原话：sending zip as base64-encoded attachment corrupts archive
- 输入：`msg.eml`（254 bytes；sha256 `4a7dd2c4b6f30f4c8fedbb0608c2a4ec81346d31f9b162240b18b52fd1815897`）
- 期望指纹：`50164db2313ad6b1695faebd8fbde13d638075a8787f64cc7e2a8b4faf07264a`
- 树指纹：`2ddc6b0d6b01d893e4b5e0a062a5ca268c01171bdc978fceef8f4c61046a3018`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-b64-len/msg.eml`

## 说明

R9 的长度子项原句未录 → 现在只出 `note`；**补齐 §6.8 原句后提为 hard/major**（`plan/01` §M3 验收）——届时须同轮改 golden 与 catalog，不得只改一处。验收不依赖 severity：只断言「报了 MC-T03 且偏移精确」。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T03 | diff | note | 0 | 246 | absolute | RFC 2045 §6.8（R9 的填充/长度子项未录原句 → 门禁降级，只登记） | base64 数据字符数 6 不是 4 的倍数（末组被截断，解码会丢字节） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


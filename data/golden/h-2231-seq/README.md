# golden case: h-2231-seq

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：SO 44154520——原话：attachment file names arrive are in gibberish；实样含 name*="UTF-8''%D7%A2...（缺 *0 序号）
- 输入：`msg.eml`（473 bytes；sha256 `f556793f7c493d7a2d3a2943ea1b112c7359bd122147800f703b4f3543da62b7`）
- 期望指纹：`76208a3874843cf0a967d179775a577ff14b3619f19bc5b5b2ea07de6b5a2f25`
- 树指纹：`0791580e081ed284cc53fdd1e25626b95083a36eca6f5132eeeb6b55de9c6e7f`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-2231-seq/msg.eml`

## 说明

验收不依赖 severity：只断言「报了 MC-H09 且路径 `0.2` 精确」。R10 整行原句未录 → 补齐摘录前只能出 `note`。SO 实样里 `name*="UTF-8''…"`（带引号的扩展值）与 `filename*=UTF-8''…` 都缺 `*0`；本样本只保留 `filename*` 一处（同一 case 出两条账会稀释定位精度），另一处形状在本说明里记述。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H09 | diff | note | 0.2 | 381 | absolute | RFC 2231 §3/§4/§4.1（R10 整行未录原句 → 门禁降级，只登记） | RFC 2231 参数缺 `*0` 序号：`filename*=` 应写成 `filename*0*=`（SO 44154520 的形状；修正提示是文本，不自动改文件） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。


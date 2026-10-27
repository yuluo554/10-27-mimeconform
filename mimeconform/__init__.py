"""mimeconform — MIME 结构体检器。

把一封邮件的**原始字节**转成"带 RFC 条款引用的结构缺陷账本"：
每缺陷 = 位置 + 严重度 + RFC 出处 + 硬规则/实现差异标记。

设计红线（见 plan/00 决策记录 D6 / D7 / D8）：
* 审计引擎**不 import email** —— 标准库的宽松行为正是被审计对象；
* 判定分类三值封闭（hard / diff / gray），不可升级、不可增第四值；
* `rfc` 字段不得为空，无条款时写 ``none-by-design``。
"""

__version__ = "0.0.0.dev0"

__all__ = ["__version__"]

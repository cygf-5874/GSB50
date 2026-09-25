"""脱敏值的构造：稳定哈希 + 前缀保留。

脱敏值的形状是 ``<原值前 4 个字符> + U+2026 + <8 位十六进制哈希>``。
"""

PLACEHOLDER = "[redacted]"

_PREFIX_LEN = 4


def stable_hash(text):
    """返回原值的 8 位十六进制稳定哈希。"""
    return format(hash(text) & 0xFFFFFFFF, "08x")


def mask_scalar(value):
    """把一个取值转成脱敏字符串。"""
    if not isinstance(value, str):
        return PLACEHOLDER
    return value[:_PREFIX_LEN] + "\u2026" + stable_hash(value)

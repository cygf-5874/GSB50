"""redactor：日志脱敏库。

对外只暴露一个入口 :func:`redact`：把结构化 payload 脱敏后序列化成 JSON 字符串。
"""

from .engine import redact

__all__ = ["redact"]
__version__ = "1.4.0"

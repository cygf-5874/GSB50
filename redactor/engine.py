"""redact 引擎：结构遍历与 JSON 拼装。"""

import json

from . import rules
from .hashid import mask_scalar

CIRCULAR = "[circular]"
DEPTH_LIMIT = "[depth-limit]"


def redact(obj, fields):
    """把 ``obj`` 按 ``fields`` 脱敏后序列化成一段 JSON 字符串。"""
    patterns = rules.parse_fields(fields)
    out = []
    _render(obj, (), patterns, out)
    return "".join(out)


def _render(value, path, patterns, out):
    if isinstance(value, dict):
        _render_object(value, path, patterns, out)
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(", ")
            _render(item, path, patterns, out)
        out.append("]")
    else:
        out.append(_render_scalar(value))


def _render_object(mapping, path, patterns, out):
    out.append("{")
    first = True
    for key in sorted(mapping):
        if not first:
            out.append(", ")
        first = False
        out.append(_quote(str(key)))
        out.append(": ")
        if rules.is_marked(path, key, patterns):
            _emit_masked(mapping[key], out)
        else:
            _render(mapping[key], path + (key,), patterns, out)
    out.append("}")


def _emit_masked(value, out):
    out.append('"')
    out.append(mask_scalar(value))
    out.append('"')


def _render_scalar(value):
    if isinstance(value, str):
        return _quote(value)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, (bytes, bytearray)):
        return _quote(bytes(value).decode("utf-8", "replace"))
    return _quote(str(value))


def _quote(text):
    return json.dumps(text, ensure_ascii=True)

"""标记字段的匹配规则：路径解析与命中判定。

``fields`` 里的每一项有两种写法：

* 裸名字，如 ``"token"``：任意层级上只要出现同名 key 就算命中；
* 点分路径，如 ``"user.password"``：只有 ``user`` 子树下的 ``password`` 才算命中。
"""

_SEP = "."


def parse_fields(fields):
    """把 ``fields`` 归一化成「路径段元组」列表。非字符串项忽略。"""
    patterns = []
    for item in fields or ():
        if not isinstance(item, str):
            continue
        parts = tuple(part for part in item.split(_SEP) if part)
        if parts:
            patterns.append(parts)
    return tuple(patterns)


def is_marked(path, key, patterns):
    """判断 ``path`` 之下的键 ``key`` 是否命中任一标记。

    ``path`` 是当前键的祖先键元组（从根开始、不含 ``key`` 自己）。
    """
    name = str(key)
    for spec in patterns:
        if spec[-1] != name:
            continue
        if len(spec) == 1:
            return True
        depth = len(spec) - 1
        tail = path[len(path) - depth:] if depth <= len(path) else path
        if tuple(str(part) for part in tail) == spec[:-1]:
            return True
    return False

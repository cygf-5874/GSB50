# 代码审查结论 · redactor

> 按 `review/CHECKLIST.md` 的格式逐条填写；**每条结论都要能照抄复现**。
> 本文件是本次任务的交付物，只写「违反了哪条保证」与证据，不写修复建议。

## 结论清单

### 结论 1

- 保证编号：1
- 缺陷位置：redactor/rules.py:31
- 复现命令：python3 repro.py
- 实际输出：redacted = {"headers": {"Accept": "application/json", "Authorization": "Bearer sk-live-9f8e7d6c5b4a"}, "method": "POST", "user": {"name": "ada", "token": "tok_…db66546f"}} —— 期望 `Authorization` 命中标记 `authorization` 被脱敏，实际原值 `Bearer sk-live-9f8e7d6c5b4a` 原样出现在输出里（同行的 `token` 因大小写一致被正常脱敏）。
- 违反说明：保证 1 要求标记匹配「一律不分大小写」，但 `is_marked` 在 rules.py:31 用 `spec[-1] != name` 做大小写敏感比较（rules.py:37 的路径段比较同样未做大小写归一），导致 `Authorization` 与 `authorization` 判为不命中。

### 结论 2

- 保证编号：2
- 缺陷位置：redactor/hashid.py:13
- 复现命令：python3 -c "import os,subprocess; cmd=['python3','-c','from redactor.hashid import stable_hash; print(stable_hash(\"Bearer sk-live-9f8e7d6c5b4a\"))']; [print('PYTHONHASHSEED=%s ->'%s, subprocess.run(cmd, env=dict(os.environ, PYTHONHASHSEED=s), capture_output=True, text=True).stdout.strip()) for s in ('0','1')]"
- 实际输出：PYTHONHASHSEED=0 -> 596f5a40 与 PYTHONHASHSEED=1 -> 0daec7c2 —— 同一个原值在不同 `PYTHONHASHSEED` 下得到不同的哈希段，期望两次逐字符相同。
- 违反说明：保证 2 要求哈希段在任何进程、任何 `PYTHONHASHSEED` 下稳定，但 hashid.py:13 直接使用内置 `hash(text)`，而 CPython 对 `str` 的 `hash()` 默认按进程随机加盐，结果随 `PYTHONHASHSEED` 变化。

### 结论 3

- 保证编号：3
- 缺陷位置：redactor/hashid.py:20
- 复现命令：python3 -c "from redactor import redact; print(redact({'token': 'abc12345'}, ['token']))"
- 实际输出：{"token": "abc1…ac9a969c"}（哈希段随进程变化）—— 原值 `abc12345` 长度为 8（≤ 8），期望整体替换为 "[redacted]"，实际仍保留原值前 4 个字符 `abc1`。
- 违反说明：保证 3 要求原值长度 ≤ 8 时整体替换为定长串 `[redacted]`、不得保留原值任何字符，但 hashid.py:20 的 `mask_scalar` 对任意长度的字符串都无条件拼接 `value[:4]` 前缀，没有长度分支。

### 结论 4

- 保证编号：4
- 缺陷位置：redactor/engine.py:37
- 复现命令：python3 -c "from redactor import redact; print(redact({'b': 1, 'a': 2}, []))"
- 实际输出：{"a": 2, "b": 1} —— 输入 dict 的插入顺序是 `b` 在前、`a` 在后，期望输出保持 `{"b": 1, "a": 2}`，实际 key 被重排成字典序。
- 违反说明：保证 4(a) 要求 `dict` 的 key 保持插入顺序、不得重排，但 engine.py:37 用 `for key in sorted(mapping)` 遍历，把 key 按字典序重新排序后才输出。

### 结论 5

- 保证编号：4
- 缺陷位置：redactor/engine.py:71
- 复现命令：python3 -c "from redactor import redact; print(redact({'msg': '中文'}, []))"
- 实际输出：{"msg": "\u4e2d\u6587"} —— 期望非 ASCII 字符 `中文` 原样输出为字符本身，实际被转义成 `\uXXXX` 形式。
- 违反说明：保证 4(b) 要求非 ASCII 字符原样输出、不得转义成 `\uXXXX`，但 engine.py:71 的 `_quote` 调用 `json.dumps(text, ensure_ascii=True)`，强制把所有非 ASCII 字符转义。

### 结论 6

- 保证编号：5
- 缺陷位置：redactor/engine.py:20
- 复现命令：python3 -c "from redactor import redact; d={}; d['self']=d; print(redact(d, []))"
- 实际输出：抛出 RecursionError: maximum recursion depth exceeded（进程以非零码退出，无任何 JSON 输出）—— 期望正常返回且循环处输出 "[circular]"。
- 违反说明：保证 5 要求输入出现自引用时不得抛 `RecursionError`、循环处输出定长串 `"[circular]"`，但 engine.py:20 的 `_render` 递归遍历时不携带任何已访问容器集合（engine.py:8 的 `CIRCULAR` 常量定义后从未被引用），自引用输入导致无限递归。

### 结论 7

- 保证编号：5
- 缺陷位置：redactor/engine.py:28
- 复现命令：python3 -c "from redactor import redact; from functools import reduce; d=reduce(lambda acc,_: {'k': acc}, range(70), {}); out=redact(d, []); print('depth-limit count:', out.count('[depth-limit]')); print('prefix:', out[:50])"
- 实际输出：depth-limit count: 0，prefix: {"k": {"k": {"k": {"k": {"k": {"k": {"k": {"k": {" —— 70 层嵌套期望从第 65 层起输出 "[depth-limit]"，实际整个 70 层结构被完整展开，输出中一次 "[depth-limit]" 都没有。
- 违反说明：保证 5 要求嵌套深度上限为 64、超过的子树输出定长串 `"[depth-limit]"`，但 engine.py:28 的递归调用只传 `path` 不传深度计数、也没有任何深度判断（engine.py:9 的 `DEPTH_LIMIT` 常量定义后从未被引用），深度上限完全未实现。

### 结论 8

- 保证编号：7
- 缺陷位置：redactor/engine.py:52
- 复现命令：python3 -c "import json; from redactor import redact; out=redact({'token': 'ab\"cd efghij'}, ['token']); print('redact 输出:', out); json.loads(out)"
- 实际输出：redact 输出: {"token": "ab"c…5a8d57cb"}（哈希段随进程变化），随后 json.loads 抛 json.decoder.JSONDecodeError: Expecting ',' delimiter: line 1 column 15 (char 14) —— 期望返回值能被 `json.loads` 解析，实际是非法 JSON。
- 违反说明：保证 7 要求输出是合法 JSON、被脱敏值里出现 `"` 等字符时仍转义正确，但 engine.py:52 的 `_emit_masked` 把 `mask_scalar(value)` 的结果直接拼进一对裸引号之间，保留前缀里含有的 `"`（以及换行、反斜杠、控制字符）不做任何 JSON 转义，破坏了输出结构。

## 为什么 tests/test_redactor.py 没抓到

既有 12 个用例只覆盖 ASCII、单层结构的正常路径，逐条对盲区说明如下：

- 结论 1（大小写）：所有用例里 `fields` 与 JSON key 都是全小写且逐字符相同（`authorization`/`token`），没有任何「标记与 key 大小写不一致」的用例，大小写敏感比较永远不会暴露。
- 结论 2（稳定哈希）：`test_same_value_masked_same_way_within_process` 只在同一进程内比较两次输出，同一进程 `PYTHONHASHSEED` 固定，内置 `hash()` 的加盐行为不可见；没有任何跨进程/跨 seed 的对照。
- 结论 3（短值前缀）：所有被脱敏的字符串取值都是 `LONG_SECRET`（长度 28 > 8），没有长度 ≤ 8 的字符串用例，长度分支缺失不会被触发。
- 结论 4（key 顺序）：`test_key_order_preserved` 用的输入是 `{"a": 1, "b": 2}`，插入顺序恰好等于字典序，`sorted()` 的重排效果被输入巧合掩盖；没有插入顺序与字典序不一致的用例。
- 结论 5（非 ASCII）：全部用例输入都是纯 ASCII（README 亦注明），没有非 ASCII 字符用例，`ensure_ascii=True` 的转义行为无从暴露。
- 结论 6（循环引用）：没有任何自引用输入的用例，`_render` 缺少已访问集合的事实不会被触发。
- 结论 7（深度上限）：用例最深只有一层嵌套（`{"a": 1, "b": [...]}`），没有接近或超过 64 层的输入，深度计数缺失不会被发现。
- 结论 8（脱敏值转义）：被脱敏的取值都是字母数字串（`sk-live-...`），保留的前 4 个字符不含引号、换行或控制字符，`_emit_masked` 不转义的缺陷不会显现；`test_output_is_valid_json` 的输入里也没有任何标记字段。

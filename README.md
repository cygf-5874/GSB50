# redactor

一个**日志脱敏**小库：给定一段结构化 payload（`dict` / `list` / 标量）与一组「标记字段」，
`redact()` 把它序列化成一段 JSON，其中命中标记字段的取值被替换成脱敏值。

```python
from redactor import redact

log = {"method": "POST", "headers": {"authorization": "Bearer sk-live-0123456789abcdef"}}
print(redact(log, ["authorization"]))
# {"method": "POST", "headers": {"authorization": "Bear…c0ffee42"}}
```

## 目录

```
redactor/__init__.py   对外入口（redact）
redactor/rules.py      标记字段的匹配规则（路径解析与命中判定）
redactor/hashid.py     脱敏值构造（稳定哈希 + 前缀保留）
redactor/engine.py     结构遍历与 JSON 拼装
tests/test_redactor.py 既有用例（12 个；只覆盖 ASCII 与单层结构的正常路径）
repro.py               线上抓到的一段最小输入
scripts/check.sh       固定验收入口（勿改）
check/check.py         固定验收程序（勿改）
review/CHECKLIST.md    审查核对表（勿改）
review/REVIEW.md       审查结论（待填；本任务的交付物）
```

## 语言版本前提

- Python 3（开发与验证用 3.13）。
- **只用标准库**（`json` / `hashlib` / `unittest`），不引入任何第三方依赖。

## 怎么跑

```bash
python3 -m unittest discover -s tests   # 既有用例，当前 12/12 全绿
python3 repro.py                        # 线上最小复现
bash scripts/check.sh                   # 固定验收；支持 -list 与 --only <组名>
```

`tests/test_redactor.py` 只覆盖 ASCII 输入与单层结构的正常路径。

## 对外保证

下面 7 条是 `redactor` 的**对外契约**，实现必须全部守住；它们是本题验收点的唯一出处。

1. **标记匹配不分大小写，且覆盖嵌套结构与路径写法**：`fields` 里的名字与 JSON 里任意层级
   （嵌套 `dict`、`list` 元素里的 `dict`）的 key 比对时**一律不分大小写**；并且支持 `a.b.c`
   形式的路径写法——`a.b.c` 只命中「键 `a` 的子树里、键 `b` 的子树里、键 `c`」这一条链。
   命中即脱敏。
2. **稳定哈希**：脱敏值里的哈希段必须是**稳定**的——对同一个原值，在任何进程、任何
   `PYTHONHASHSEED` 下都必须得到逐字符相同的结果。
3. **前缀与长度策略**：当原值长度 > 8 时，脱敏值必须保留原值的**前 4 个字符**（按 Unicode
   码点切）作为可辨识前缀；当原值长度 ≤ 8 时，必须**整体替换**为定长串 `[redacted]`
   （不得保留原值的任何字符）。标记字段的取值若不是字符串（数字、布尔、`null`、`bytes`、
   容器），一律整体替换为 `[redacted]`。
4. **非标记字段原样保留**：输出中，除被脱敏的标记字段以外的内容必须与输入一致——具体地：
   (a) `dict` 的 key 必须保持**插入顺序**，不得重排；(b) 非 ASCII 字符必须**原样**输出为
   字符本身（UTF-8），不得转义成 `\uXXXX`；字符串值里原有的空白字符也一律保留。
5. **循环引用与深度上限**：输入出现自引用（某个容器直接或间接包含自身）时不得抛
   `RecursionError`，必须正常返回，循环处输出定长串 `"[circular]"`；嵌套深度上限为 64，
   深度超过 64 的子树输出定长串 `"[depth-limit]"`，同样不得崩。
6. **任何输入都返回结构化结果**：`redact(obj, fields)` 对任意 `obj` 都返回 `str`，不抛异常：
   `obj is None` → `"null"`；`obj` 是空串 → `""`；非 `str` 标量（`int` / `bool` / `float`）
   原样输出；`bytes` 按 UTF-8 容错解码后再处理；超长字符串按普通字符串处理。
7. **输出是合法 JSON**：返回的字符串必须能被 `json.loads` 解析；被脱敏值里出现 `"`、
   换行、控制字符时，输出仍必须转义正确。

## 固定验收

`bash scripts/check.sh` 是固定验收入口，只校验 `review/REVIEW.md` 的交付格式、可执行证据、
对上述 7 条保证的覆盖，以及不可改文件的 SHA-256 基线与文件清单。
**`check/`、`scripts/`、`redactor/`、`tests/`、`repro.py`、`review/CHECKLIST.md` 一律勿改。**

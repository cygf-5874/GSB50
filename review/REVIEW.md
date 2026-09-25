# 代码审查结论 · redactor

> 按 `review/CHECKLIST.md` 的格式逐条填写；每条结论都可照抄复现。
> 本文件只写「违反了哪条保证」与证据，不写修复建议。

## 结论清单

### 结论 1

- 保证编号：1
- 缺陷位置：redactor/rules.py:31
- 复现命令：python3 repro.py
- 实际输出：redacted = {"headers": {"Accept": "application/json", "Authorization": "Bearer sk-live-9f8e7d6c5b4a"}, "method": "POST", "user": {"name": "ada", "token": "tok_…649e5557"}} —— 标记列表写了 authorization，但 JSON 里的 Authorization（大写 A）原样保留，密钥 Bearer sk-live-9f8e7d6c5b4a 完整泄露；期望它被脱敏。
- 违反说明：is_marked 用 spec[-1] != name 做大小写敏感的精确比对，违反保证 1「标记匹配不分大小写」。

### 结论 2

- 保证编号：2
- 缺陷位置：redactor/hashid.py:13
- 复现命令：python3 -c "import os,subprocess,sys; code='from redactor.hashid import stable_hash; print(stable_hash(\"sk-live-0123456789abcdef\"))'; [print('PYTHONHASHSEED=%s ->' % s, subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,env={**os.environ,'PYTHONHASHSEED':s}).stdout.strip()) for s in ('1','2')]"
- 实际输出：PYTHONHASHSEED=1 -> 869c3120 与 PYTHONHASHSEED=2 -> 68084430 —— 同一个原值在不同 PYTHONHASHSEED 下哈希段不同；期望任何进程、任何种子下逐字符相同。
- 违反说明：stable_hash 直接用内置 hash()，其结果受 PYTHONHASHSEED 随机化影响，违反保证 2「稳定哈希」。

### 结论 3

- 保证编号：3
- 缺陷位置：redactor/hashid.py:20
- 复现命令：python3 -c "from redactor import redact; print(redact({'token': 'abc'}, ['token']))"
- 实际输出：{"token": "abc…6763e8ae"} —— 原值 abc 长度 3 ≤ 8，却被保留前缀后输出，原值 3 个字符全部泄露；期望整体替换为定长串 "[redacted]"。
- 违反说明：mask_scalar 对任意长度字符串都保留前 4 个字符，没有「长度 ≤ 8 整体替换为 [redacted]」的分支，违反保证 3。

### 结论 4

- 保证编号：4
- 缺陷位置：redactor/engine.py:37
- 复现命令：python3 -c "from redactor import redact; print(redact({'b': 1, 'a': 2}, []))"
- 实际输出：{"a": 2, "b": 1} —— 输入插入顺序是 b 在前 a 在后，输出被重排成 a 在前；期望保持插入顺序 {"b": 1, "a": 2}。
- 违反说明：_render_object 用 sorted(mapping) 遍历键，破坏了 dict 的插入顺序，违反保证 4(a)「key 必须保持插入顺序，不得重排」。

### 结论 5

- 保证编号：4
- 缺陷位置：redactor/engine.py:71
- 复现命令：python3 -c "from redactor import redact; print(redact({'name': '张三'}, []))"
- 实际输出：{"name": "\u5f20\u4e09"} —— 两个汉字被转义成 \uXXXX 序列；期望原样输出字符本身，即 {"name": "张三"}。
- 违反说明：_quote 用 json.dumps(text, ensure_ascii=True)，把非 ASCII 字符转义成 \uXXXX，违反保证 4(b)「非 ASCII 字符必须原样输出」。

### 结论 6

- 保证编号：5
- 缺陷位置：redactor/engine.py:28
- 复现命令：python3 -c "from redactor import redact; d={}; d['self']=d; print(redact(d, []))"
- 实际输出：Traceback（最末一行）RecursionError: maximum recursion depth exceeded —— 自引用输入直接崩溃；期望正常返回且循环处输出 "[circular]"。同理嵌套超过 64 层也抛 RecursionError 而非输出 "[depth-limit]"。
- 违反说明：_render 递归遍历没有任何循环检测与深度计数（CIRCULAR/DEPTH_LIMIT 常量定义了却从未使用），违反保证 5。

### 结论 7

- 保证编号：7
- 缺陷位置：redactor/engine.py:52
- 复现命令：python3 -c "from redactor import redact; import json; s=redact({'token': 'ab\"cdefghij'}, ['token']); print(s); json.loads(s)"
- 实际输出：先打印 {"token": "ab"c…a9f52029"}，随后 json.loads 抛 json.decoder.JSONDecodeError: Expecting ',' delimiter: line 1 column 15 (char 14) —— 脱敏值里保留的前 4 个字符含未转义的英文双引号，输出不是合法 JSON；期望 json.loads 能解析。
- 违反说明：_emit_masked 把 mask_scalar 的结果原样包进引号、不做 JSON 转义，被脱敏值含引号或控制字符时输出非法 JSON，违反保证 7。

## 为什么 tests/test_redactor.py 没抓到

既有 12 个用例只走 ASCII、单层结构的正常路径，每个缺陷都落在它的盲区上：

- 结论 1（大小写）：用例里标记名与 JSON 键永远同形小写（authorization 对 authorization），从未出现 Authorization 这类大小写变体，大小写敏感比对不会暴露。
- 结论 2（稳定哈希）：test_same_value_masked_same_way_within_process 只在同一进程内比较两次输出，PYTHONHASHSEED 相同，内置 hash() 的跨进程不稳定根本测不到。
- 结论 3（短值整体替换）：所有被脱敏的字符串都是 LONG_SECRET（26 个字符，> 8），没有任何长度 ≤ 8 的标记取值，「整体替换为 [redacted]」分支从未被断言。
- 结论 4（键序）：test_key_order_preserved 用的输入 {"a": 1, "b": 2} 本身就是字典序，sorted() 的重排恰好不可见；没有乱序插入的用例。
- 结论 5（非 ASCII 转义）：全部用例都是 ASCII 输入，ensure_ascii=True 与 False 输出完全一致，转义缺陷无从显现。
- 结论 6（循环与深度）：用例没有任何自引用结构，也没有超过 64 层的嵌套，递归缺失保护不会被触发。
- 结论 7（脱敏值转义）：被脱敏的取值 LONG_SECRET 只含字母、数字与连字符，不含引号、换行或控制字符，_emit_masked 不转义的问题不会显现。

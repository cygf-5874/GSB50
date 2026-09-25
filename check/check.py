#!/usr/bin/env python3
"""redactor 审查题的固定验收入口。**别改这个文件。**

只校验 ``review/REVIEW.md`` 的交付格式、可执行证据、对 7 条对外保证的覆盖，
以及不可改文件的 SHA-256 基线与文件清单；结论是否正确由人按 README 逐条复核。

用法::

    python3 check/check.py                  # 跑全部 10 个场景
    python3 check/check.py -list            # 列出全部场景
    python3 check/check.py --only format    # 只跑一组（可逗号分隔多组）
"""

import hashlib
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW_REL = "review/REVIEW.md"

GUARANTEE_COUNT = 7
MIN_CONCLUSIONS = 6
COMMAND_TIMEOUT = 60

# 不可改文件的 SHA-256 基线（先把行尾统一成 LF 再算）。建仓时生成。
BASELINE = {
    "README.md": "c9a9ff47bd7bf792713501a9b6647e8995b2873b322a8283b66863eaf1296fe8",
    "repro.py": "f03ed5209dc2a3fc6876cdfe5174d8c748fac982e5582ad6b157a4d363a98914",
    "redactor/__init__.py": "ac77ca3af0ec912900438ab3fc07c0b0dff284316ecefdf181e7915d15ea3f68",
    "redactor/engine.py": "1efd475defb5e27336eb58517f7f47942a145d019da4c3fb3b3c30c14fb173e6",
    "redactor/hashid.py": "7109c822eb66fdccdebff8319689aba8a85ee65d4116e7189fa294c6e5e9ddfb",
    "redactor/rules.py": "2f6f77f41a60965939ff32525a4893d7e6a83393ec80942289cb006caa588698",
    "review/CHECKLIST.md": "a138393990b2022530e7ca7a9d5070da0ecc81acb5e8268d3319fa55dcfe7bed",
    "scripts/check.sh": "a8e809226e1c85c440642b337f6147d1dd18c48d30f8c344f21f2e76b4afd072",
    "tests/test_redactor.py": "72cba6ccf69e2e8da2a7eaeba5ca0b5fdc94e9874207a832bcf2f920b67e5ede",
}

# 仓库应有的文件清单（不含 .git 与 Python 字节码缓存）。
EXPECTED_FILES = [
    ".gitignore",
    "README.md",
    "check/check.py",
    "redactor/__init__.py",
    "redactor/engine.py",
    "redactor/hashid.py",
    "redactor/rules.py",
    "repro.py",
    "review/CHECKLIST.md",
    "review/REVIEW.md",
    "scripts/check.sh",
    "tests/test_redactor.py",
]

FIELDS = ("保证编号", "缺陷位置", "复现命令", "实际输出", "违反说明")
PLACEHOLDERS = ("TODO", "todo", "FIXME", "待补", "待填", "待定")

SCENARIOS = []


def fail(expected, actual):
    return "期望=%s 实际=%s" % (expected, actual)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def file_sha256(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    return hashlib.sha256(raw.replace(b"\r", b"")).hexdigest()


def scenario(name):
    def decorate(function):
        SCENARIOS.append((name, function))
        return function

    return decorate


# ---------------------------------------------------------------------------
# REVIEW.md 解析
# ---------------------------------------------------------------------------


def parse_review(text):
    sections = {}
    conclusions = []
    current_top = None
    current = None
    label = None
    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("## ") and not stripped.startswith("### "):
            current_top = stripped[3:].strip()
            sections.setdefault(current_top, [])
            current = None
            label = None
            continue
        if stripped.startswith("#"):
            if stripped.startswith("### "):
                current = {"title": stripped.lstrip("#").strip()}
                for name in FIELDS:
                    current[name] = ""
                conclusions.append(current)
            label = None
            continue

        if current_top is not None:
            sections[current_top].append(line)

        match = re.match(
            r"^\s*[-*]?\s*(保证编号|缺陷位置|复现命令|实际输出|违反说明)\s*[:：]\s*(.*)$",
            line,
        )
        if match is not None and current is not None:
            label = match.group(1)
            value = match.group(2).strip()
            current[label] = (current[label] + "\n" + value).strip() if current[label] else value
            continue
        if current is not None and label is not None and stripped and stripped != "```":
            current[label] = (current[label] + "\n" + stripped).strip()

    return conclusions, {key: "\n".join(value) for key, value in sections.items()}


REVIEW_TEXT = read_text(os.path.join(ROOT, REVIEW_REL))
if REVIEW_TEXT is None:
    CONCLUSIONS, SECTIONS = [], {}
else:
    CONCLUSIONS, SECTIONS = parse_review(REVIEW_TEXT)


# ---------------------------------------------------------------------------
# format 3
# ---------------------------------------------------------------------------


@scenario("format/sections")
def check_sections():
    if REVIEW_TEXT is None:
        return fail("review/REVIEW.md 存在且含「结论清单」与「为什么…没抓到」两节", "文件不存在")
    has_list = any("结论" in key for key in SECTIONS)
    has_why = any("没抓到" in key or "为什么" in key for key in SECTIONS)
    if not has_list:
        return fail("REVIEW.md 含「结论清单」一节", "未找到")
    if not has_why:
        return fail("REVIEW.md 含「为什么…没抓到」一节", "未找到")
    if len(REVIEW_TEXT.strip()) < 80:
        return fail("REVIEW.md 是填好的结论", "去空白后仅 %d 字" % len(REVIEW_TEXT.strip()))
    why = "".join(value for key, value in SECTIONS.items() if "没抓到" in key or "为什么" in key)
    squeezed = re.sub(r"\s+", "", why)
    if len(squeezed) < 40:
        return fail("说明节逐条说明既有用例的盲区（≥ 40 字）", "去空白后仅 %d 字" % len(squeezed))
    return None


@scenario("format/fields")
def check_fields():
    if not CONCLUSIONS:
        return fail("至少 1 条结论（`### 结论 N` 小节）", "0 条")
    for index, item in enumerate(CONCLUSIONS, 1):
        for name in FIELDS[:4]:
            if not item[name].strip():
                return fail("结论 %d 的「%s」非空" % (index, name), "空")
        blob = " ".join(item.values())
        for word in PLACEHOLDERS:
            if word in blob:
                return fail("结论 %d 不含占位词" % index, "出现「%s」" % word)
    return None


@scenario("format/count")
def check_count():
    if len(CONCLUSIONS) < MIN_CONCLUSIONS:
        return fail("结论条数 ≥ %d" % MIN_CONCLUSIONS, "只有 %d 条" % len(CONCLUSIONS))
    return None


# ---------------------------------------------------------------------------
# evidence 3
# ---------------------------------------------------------------------------


@scenario("evidence/files")
def check_evidence_files():
    if not CONCLUSIONS:
        return fail("至少 1 条结论", "0 条")
    for index, item in enumerate(CONCLUSIONS, 1):
        match = re.match(r"^(.+?)\s*[:：]\s*(\d+)\s*$", item["缺陷位置"].strip())
        if match is None:
            return fail("结论 %d 的「缺陷位置」写成 文件:行号" % index, "「%s」" % item["缺陷位置"])
        rel = match.group(1).strip().replace("\\", "/")
        number = int(match.group(2))
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            return fail("结论 %d 的缺陷文件存在" % index, "找不到 %s" % rel)
        lines = (read_text(path) or "").count("\n") + 1
        if not 1 <= number <= lines:
            return fail("结论 %d 的行号落在 %s 的 1~%d 行内" % (index, rel, lines), "第 %d 行" % number)
        for token in re.findall(r"[A-Za-z0-9_./\\-]+\.(?:py|sh|md)", item["复现命令"]):
            candidate = token.replace("\\", "/")
            if candidate.startswith("/") or ":" in candidate:
                continue
            if not os.path.exists(os.path.join(ROOT, candidate)):
                return fail("结论 %d 复现命令引用的文件存在" % index, "找不到 %s" % candidate)
    return None


@scenario("evidence/runs")
def check_evidence_runs():
    if not CONCLUSIONS:
        return fail("至少 1 条结论", "0 条")
    for index, item in enumerate(CONCLUSIONS, 1):
        command = item["复现命令"].strip().strip("`").strip()
        if not command:
            return fail("结论 %d 的「复现命令」非空" % index, "空")
        if re.match(r"^([A-Za-z_][A-Za-z0-9_]*=\S*\s+)*(python3|python)\b", command) is None:
            return fail("结论 %d 的复现命令以 python3 起头" % index, "「%s」" % command.split()[0])
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                timeout=COMMAND_TIMEOUT,
            )
        except FileNotFoundError:
            return fail("能找到 bash 执行复现命令", "PATH 里没有 bash")
        except subprocess.TimeoutExpired:
            return fail("结论 %d 的复现命令在 %ds 内结束" % (index, COMMAND_TIMEOUT), "超时")
        output = (result.stdout or "") + (result.stderr or "")
        if not output.strip():
            return fail("结论 %d 的复现命令产生输出" % index, "无输出")
    return None


@scenario("evidence/observable")
def check_evidence_observable():
    if not CONCLUSIONS:
        return fail("至少 1 条结论", "0 条")
    for index, item in enumerate(CONCLUSIONS, 1):
        raw = item["保证编号"].strip()
        if not raw.isdigit() or not 1 <= int(raw) <= GUARANTEE_COUNT:
            return fail("结论 %d 的「保证编号」是 1~%d 的整数" % (index, GUARANTEE_COUNT), "「%s」" % raw)
        if len(re.sub(r"\s+", "", item["实际输出"])) < 8:
            return fail("结论 %d 的「实际输出」给出具体现象" % index, "去空白后过短")
    return None


# ---------------------------------------------------------------------------
# coverage 2
# ---------------------------------------------------------------------------


@scenario("coverage/guarantees")
def check_coverage_guarantees():
    ids = set()
    for item in CONCLUSIONS:
        raw = item["保证编号"].strip()
        if raw.isdigit() and 1 <= int(raw) <= GUARANTEE_COUNT:
            ids.add(int(raw))
    if len(ids) < MIN_CONCLUSIONS:
        return fail(
            "至少引用 %d 条不同的对外保证" % MIN_CONCLUSIONS,
            "只引用 %d 条：%s" % (len(ids), sorted(ids) if ids else "无"),
        )
    return None


@scenario("coverage/distinct")
def check_coverage_distinct():
    if len(CONCLUSIONS) < MIN_CONCLUSIONS:
        return fail("结论条数 ≥ %d 才能核对去重" % MIN_CONCLUSIONS, "只有 %d 条" % len(CONCLUSIONS))
    seen = {}
    for index, item in enumerate(CONCLUSIONS, 1):
        key = re.sub(r"\s+", "", item["缺陷位置"]).lower()
        if not key:
            return fail("结论 %d 的「缺陷位置」非空" % index, "空")
        if key in seen:
            return fail(
                "每条结论指向不同的缺陷位置",
                "结论 %d 与结论 %d 都指向 %s" % (seen[key], index, item["缺陷位置"].strip()),
            )
        seen[key] = index
    return None


# ---------------------------------------------------------------------------
# integrity 2
# ---------------------------------------------------------------------------


def review_delivered():
    """REVIEW.md 是否已经是「填好的交付物」——至少一条结论的四个字段都非空。"""
    for item in CONCLUSIONS:
        if all(item[name].strip() for name in FIELDS[:4]):
            return True
    return False


@scenario("integrity/hash")
def check_integrity_hash():
    if not review_delivered():
        return fail(
            "REVIEW.md 已填写（至少一条结论的四个字段齐全），此后不可改文件须与基线一致",
            "REVIEW.md 仍是空模板",
        )
    for rel in sorted(BASELINE):
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            return fail("%s 存在" % rel, "缺失")
        if file_sha256(path) != BASELINE[rel]:
            return fail("%s 保持原样（SHA-256 与基线一致）" % rel, "内容已被改动")
    return None


@scenario("integrity/files")
def check_integrity_files():
    if not review_delivered():
        return fail(
            "REVIEW.md 已填写（至少一条结论的四个字段齐全），此后文件清单须与基线一致",
            "REVIEW.md 仍是空模板",
        )
    present = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in (".git", "__pycache__", ".pytest_cache", ".mypy_cache")
        ]
        for name in filenames:
            if name.endswith((".pyc", ".pyo")):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), ROOT).replace("\\", "/")
            if rel.startswith(".git/"):
                continue
            present.add(rel)
    expected = set(EXPECTED_FILES)
    added = sorted(present - expected)
    missing = sorted(expected - present)
    if added:
        return fail("没有新增文件", "多出 %d 个：%s" % (len(added), ", ".join(added[:3])))
    if missing:
        return fail("没有删除文件", "缺少 %d 个：%s" % (len(missing), ", ".join(missing[:3])))
    return None


# ---------------------------------------------------------------------------
# 运行器
# ---------------------------------------------------------------------------


def main(argv):
    only = []
    do_list = False
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "-list":
            do_list = True
        elif arg == "--only":
            index += 1
            if index >= len(argv):
                print("--only 需要一个组名", file=sys.stderr)
                return 2
            only.extend(part for part in argv[index].split(",") if part)
        else:
            print("未知参数：%s" % arg, file=sys.stderr)
            return 2
        index += 1

    if do_list:
        for name, _function in SCENARIOS:
            print(name)
        return 0

    total = 0
    passed = 0
    for name, function in SCENARIOS:
        group = name.split("/", 1)[0]
        if only and group not in only:
            continue
        total += 1
        try:
            problem = function()
        except Exception as exc:  # noqa: BLE001
            problem = fail("检查正常完成", "检查过程抛异常：%s: %s" % (type(exc).__name__, exc))
        if problem is None:
            passed += 1
            print("PASS " + name)
        else:
            print("FAIL " + name + "  " + problem)

    if total == 0:
        print("没有匹配的场景（--only %s）" % ",".join(only))
        return 2

    print("结果：通过 %d/%d" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

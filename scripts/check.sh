#!/usr/bin/env bash
# 固定验收入口：校验 review/REVIEW.md 的格式、可执行证据、对 7 条对外保证的覆盖，
# 并核对不可改文件的 SHA-256 基线与文件清单。**别改这个文件。**
# 用法：bash scripts/check.sh [-list] [--only <组名>]
set -uo pipefail

cd "$(dirname "$0")/.."

PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
      PY="$cand"
      break
    fi
  done
fi
if [ -z "$PY" ]; then
  echo "找不到 python3，请在 PATH 里提供 Python 3。" >&2
  exit 2
fi

exec "$PY" check/check.py "$@"

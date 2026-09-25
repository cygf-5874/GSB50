#!/usr/bin/env python3
"""线上抓到的一段最小输入。

标记列表里写了 ``authorization``，但脱敏输出里 ``Authorization`` 原样还在。

跑法::

    python3 repro.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from redactor import redact  # noqa: E402

PAYLOAD = {
    "headers": {
        "Accept": "application/json",
        "Authorization": "Bearer sk-live-9f8e7d6c5b4a",
    },
    "method": "POST",
    "user": {"name": "ada", "token": "tok_5f4e3d2c1b0a"},
}

FIELDS = ["authorization", "token"]


def main():
    print("payload  =", json.dumps(PAYLOAD, ensure_ascii=False))
    print("fields   =", FIELDS)
    print("redacted =", redact(PAYLOAD, FIELDS))


if __name__ == "__main__":
    main()

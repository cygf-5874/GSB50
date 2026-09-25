"""redactor 的既有用例（起点全绿）。

只覆盖 ASCII 输入与单层结构的正常路径，不依赖任何内部结构。
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redactor import redact  # noqa: E402

LONG_SECRET = "sk-live-0123456789abcdef"


class RedactorTest(unittest.TestCase):
    def test_marked_field_is_masked(self):
        text = redact({"authorization": LONG_SECRET}, ["authorization"])
        self.assertNotIn(LONG_SECRET, text)
        self.assertNotIn("0123456789", text)

    def test_unmarked_field_is_untouched(self):
        text = redact({"name": "ada"}, [])
        self.assertIn('"ada"', text)
        self.assertEqual(json.loads(text), {"name": "ada"})

    def test_output_is_valid_json(self):
        text = redact({"a": 1, "b": [True, None, "x"]}, [])
        self.assertEqual(json.loads(text), {"a": 1, "b": [True, None, "x"]})

    def test_long_value_keeps_first_four_chars(self):
        masked = json.loads(redact({"authorization": LONG_SECRET}, ["authorization"]))
        self.assertTrue(masked["authorization"].startswith(LONG_SECRET[:4]))

    def test_masked_value_shape(self):
        masked = json.loads(redact({"authorization": LONG_SECRET}, ["authorization"]))
        self.assertRegex(masked["authorization"], r"^sk-l\u2026[0-9a-f]{8}$")

    def test_same_value_masked_same_way_within_process(self):
        first = redact({"authorization": LONG_SECRET}, ["authorization"])
        second = redact({"authorization": LONG_SECRET}, ["authorization"])
        self.assertEqual(first, second)

    def test_none_input(self):
        self.assertEqual(redact(None, []), "null")

    def test_empty_mapping(self):
        self.assertEqual(redact({}, []), "{}")

    def test_empty_string_input(self):
        self.assertEqual(redact("", []), '""')

    def test_key_order_preserved(self):
        self.assertEqual(redact({"a": 1, "b": 2}, []), '{"a": 1, "b": 2}')

    def test_non_string_marked_value_replaced(self):
        self.assertEqual(redact({"token": 123456}, ["token"]), '{"token": "[redacted]"}')

    def test_list_of_scalars(self):
        self.assertEqual(json.loads(redact([1, "x", None], [])), [1, "x", None])


if __name__ == "__main__":
    unittest.main()

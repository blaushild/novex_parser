import unittest
import os
import sys

# flake8: noqabu
sys.path.append(os.getcwd())
from handlers import (
    build_sku_category,
    prepare_string,
    prepare_row,
)


class TestBuildSkuCategory(unittest.TestCase):
    def test_build_sku_category_no_parent(self) -> None:
        product = {
            "categories": [
                {"title": "Корма для кошек"},
            ]
        }
        expected_result = "Корма для кошек"

        result = build_sku_category(product)

        self.assertEqual(result, expected_result)

    def test_build_sku_category_with_parents(self) -> None:
        product = {
            "categories": [
                {
                    "title": "Корма для кошек",
                    "parent": {
                        "title": "Корма для животных",
                        "parent": {
                            "title": "Для животных",
                            "parent": {"title": "Товары"},
                        },
                    },
                }
            ]
        }
        expected_result = (
            "Товары|Для животных|Корма для животных|Корма для кошек"
        )

        result = build_sku_category(product)

        self.assertEqual(result, expected_result)


class TestPrepareString(unittest.TestCase):
    def test_prepare_string_empty_text(self):
        text = ""
        expected_result = None

        result = prepare_string(text)

        self.assertEqual(result, expected_result)

    def test_prepare_string_no_special_characters(self):
        text = "Hello World"
        expected_result = "Hello World"

        result = prepare_string(text)

        self.assertEqual(result, expected_result)

    def test_prepare_string_with_special_characters(self):
        text = "Hello\nWorld\t\r\xa0"
        expected_result = "HelloWorld"

        result = prepare_string(text)

        self.assertEqual(result, expected_result)

    def test_prepare_string_with_quotes(self):
        text = 'Hello "World"'
        expected_result = 'Hello ""World""'

        result = prepare_string(text)

        self.assertEqual(result, expected_result)


class TestPrepareRow(unittest.TestCase):
    def test_prepare_row_with_strings(self):
        row = ["Hello", "World", "123"]
        expected_result = ["Hello", "World", "123"]

        result = prepare_row(row)

        self.assertEqual(result, expected_result)

    def test_prepare_row_with_empty_strings(self):
        row = ["", "", ""]
        expected_result = [None, None, None]

        result = prepare_row(row)

        self.assertEqual(result, expected_result)

    def test_prepare_row_with_mixed_values(self):
        row = ["Hello", 123, "World"]
        expected_result = ["Hello", 123, "World"]

        result = prepare_row(row)

        self.assertEqual(result, expected_result)

    def test_prepare_row_with_special_characters(self):
        row = ["Hello\nWorld", "\t123\r", ""]
        expected_result = ["HelloWorld", "123", None]

        result = prepare_row(row)

        self.assertEqual(result, expected_result)


if __name__ == "__main__":
    unittest.main()

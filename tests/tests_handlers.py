import unittest
import os
import sys

# flake8: noqa
sys.path.append(os.getcwd())
from handlers import (
    build_sku_category,
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
                            "parent": {
                                "title": "Товары"
                            }
                        }
                    }
                }
            ]
        }
        expected_result = "Товары|Для животных|Корма для животных|Корма для кошек"

        result = build_sku_category(product)

        self.assertEqual(result, expected_result)


if __name__ == '__main__':
    unittest.main()

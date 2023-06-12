"""Запуск всех тестов"""
import os
import unittest


def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.join(current_dir, "tests")

    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(tests_dir, pattern="tests_*.py")
    test_runner = unittest.TextTestRunner()
    test_runner.run(test_suite)


if __name__ == "__main__":
    main()

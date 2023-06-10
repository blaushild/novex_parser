import unittest
import sys, os

sys.path.append(os.getcwd())
from stuff import calculate_delay


class TestCalculateDelay(unittest.TestCase):
    def test_calculate_delay_returns_seconds(self):
        self.assertEqual(calculate_delay(1, 1, 0.5), 1)
        self.assertEqual(calculate_delay(2, 1, 0.5), 1.5)
        self.assertEqual(calculate_delay(3, 1, 0.5), 2.25)

    def test_calculate_delay_returns_float(self):
        self.assertIsInstance(calculate_delay(1, 1, 0.5), float)


if __name__ == '__main__':
    unittest.main()

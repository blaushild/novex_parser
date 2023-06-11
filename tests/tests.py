import unittest
import sys
import os

"""Комментарий '# flake8: noqa' указывает линтеру Flake8 игнорировать
проверку на импорт на уровне модуля. Таким образом,
линтер не будет ругаться на данную конструкцию."""
# flake8: noqa
# добавляем в пути системного окружения текущую директорию
sys.path.append(os.getcwd())
from stuff import calculate_delay, get_time_to_sleep


class TestCalculateDelay(unittest.TestCase):
    def test_calculate_delay_returns_seconds(self):
        self.assertEqual(calculate_delay(1, 1, 0.5), 1)
        self.assertEqual(calculate_delay(2, 1, 0.5), 1.5)
        self.assertEqual(calculate_delay(3, 1, 0.5), 2.25)


class TestGetTimeToSleep(unittest.TestCase):
    def test_get_time_to_sleep_receives_list_in_range(self):
        # всегда в пределах заданного диапазона
        for _ in range(1000):
            result = get_time_to_sleep([0, 10])
            self.assertGreaterEqual(result, 0)
            self.assertLessEqual(result, 10)

        # результат всегда равен входному значению, если на входе int
        self.assertEqual(get_time_to_sleep(0), 0)
        self.assertEqual(get_time_to_sleep(65), 65)
    
    def test_get_time_to_sleep_returns_int(self):
        self.assertIsInstance(get_time_to_sleep([3, 5]), int)
        self.assertIsInstance(get_time_to_sleep(95), int)


if __name__ == '__main__':
    unittest.main()

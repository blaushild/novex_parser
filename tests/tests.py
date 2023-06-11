import sys
import os
import logging
import unittest
from unittest.mock import patch

"""Комментарий '# flake8: noqa' указывает линтеру Flake8 игнорировать
проверку на импорт на уровне модуля. Таким образом,
линтер не будет ругаться на данную конструкцию."""
# flake8: noqa
# добавляем в пути системного окружения текущую директорию
sys.path.append(os.getcwd())
from stuff import (
    logger,
    calculate_delay,
    get_time_to_sleep,
    sleep_between_requests,
)


class TestCalculateDelay(unittest.TestCase):
    def test_calculate_delay_returns_seconds(self):
        self.assertEqual(calculate_delay(1, 1, 0.5), 1)
        self.assertEqual(calculate_delay(2, 1, 0.5), 1.5)
        self.assertEqual(calculate_delay(3, 1, 0.5), 2.25)


class TestGetTimeToSleep(unittest.TestCase):
    def test_get_time_to_sleep_with_list(self):
        # всегда в пределах заданного диапазона
        time_range = [2, 10]
        for _ in range(1000):
            result = get_time_to_sleep(time_range)
            self.assertTrue(time_range[0] <= result <= time_range[1])

        # результат всегда равен входному значению, если на входе int
        self.assertEqual(get_time_to_sleep(0), 0)
        self.assertEqual(get_time_to_sleep(65), 65)
    
    def test_get_time_to_sleep_returns_int(self):
        self.assertIsInstance(get_time_to_sleep([3, 5]), int)
        self.assertIsInstance(get_time_to_sleep(95), int)

    def test_invalid_input(self):
        invalid_range = []
        with self.assertRaises(TypeError):
            get_time_to_sleep(invalid_range)

        invalid_range = [2, 4, 6]
        with self.assertRaises(TypeError):
            get_time_to_sleep(invalid_range)

        invalid_range = "invalid"
        with self.assertRaises(TypeError):
            get_time_to_sleep(invalid_range)


class TestSleepBetweenRequests(unittest.TestCase):
    def setUp(self):
        # ставим уровень логгирования выше, чтобы не получать вывод от логгера
        # функции при тесте
        logger.setLevel(level=logging.WARNING)

    def test_sleep_with_int(self):
        with patch('stuff.sleep') as mock_sleep:
            sleep_between_requests(5)
            mock_sleep.assert_called_once_with(5)

    def test_sleep_with_list(self):
        for _ in range(100):
            with patch('stuff.sleep') as mock_sleep:
                time_range = [3, 5]
                sleep_between_requests(time_range)

                # Получаем переданный параметр при вызове sleep
                sleep_time = mock_sleep.call_args[0][0]

                self.assertTrue(time_range[0] <= sleep_time <= time_range[1])

    def test_sleep_with_empty_zero(self):
        with patch('stuff.sleep') as mock_sleep:
            sleep_between_requests(0)
            mock_sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()

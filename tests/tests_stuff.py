import sys
import os
import logging
import unittest
from unittest.mock import patch
from time import sleep
from typing import Any

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
    timer,
    request_repeater,
    restarter,
)


class TestCalculateDelay(unittest.TestCase):
    def test_calculate_delay_returns_seconds(self) -> None:
        self.assertEqual(calculate_delay(1, 1, 0.5), 1)
        self.assertEqual(calculate_delay(2, 1, 0.5), 1.5)
        self.assertEqual(calculate_delay(3, 1, 0.5), 2.25)


class TestGetTimeToSleep(unittest.TestCase):
    def test_get_time_to_sleep_with_list(self) -> None:
        # всегда в пределах заданного диапазона
        time_range = [2, 10]
        for _ in range(100):
            result = get_time_to_sleep(time_range)
            self.assertTrue(time_range[0] <= result <= time_range[1])

        # результат всегда равен входному значению, если на входе int
        self.assertEqual(get_time_to_sleep(0), 0)
        self.assertEqual(get_time_to_sleep(65), 65)

    def test_get_time_to_sleep_returns_int(self) -> None:
        self.assertIsInstance(get_time_to_sleep([3, 5]), int)
        self.assertIsInstance(get_time_to_sleep(95), int)

    def test_invalid_input(self) -> None:
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
    def setUp(self) -> None:
        # ставим уровень логгирования выше, чтобы не получать вывод от логгера
        # функции при тесте
        logger.setLevel(level=logging.WARNING)

    def test_sleep_with_int(self) -> None:
        with patch("stuff.sleep") as mock_sleep:
            sleep_between_requests(1)
            mock_sleep.assert_called_once_with(1)

    def test_sleep_with_list(self) -> None:
        for _ in range(100):
            with patch("stuff.sleep") as mock_sleep:
                time_range = [3, 5]
                sleep_between_requests(time_range)

                # Получаем переданный параметр при вызове sleep
                sleep_time = mock_sleep.call_args[0][0]

                self.assertTrue(time_range[0] <= sleep_time <= time_range[1])

    def test_sleep_with_empty_zero(self) -> None:
        with patch("stuff.sleep") as mock_sleep:
            sleep_between_requests(0)
            mock_sleep.assert_not_called()


class TestTimerDecorator(unittest.TestCase):
    def setUp(self) -> None:
        logger.setLevel(level=logging.INFO)

    def test_execution_time(self) -> None:
        @timer
        def func() -> None:
            sleep(1)

        # Захватываем вывод логгера для проверки времени выполнения
        with self.assertLogs(level="INFO") as logs:
            func()

        # Проверяем, что сообщение логгера содержит время выполнения
        log_message = logs.output[0]
        self.assertIn("execution time", log_message)
        self.assertIn("1.0sec", log_message)


class TestRequestRepeaterDecorator(unittest.TestCase):
    def setUp(self) -> None:
        logger.setLevel(level=logging.CRITICAL)

    def test_successful_execution(self) -> None:
        class DummyObject:
            config = {
                "delay_range_s": [0, 1],
                "backoff_factor": 2,
                "max_retries": 3,
            }

            @request_repeater
            def func(self) -> Any:
                return 89

        obj = DummyObject()

        with patch("stuff.get_time_to_sleep", return_value=0):
            result = obj.func()

        self.assertEqual(result, 89)

    def test_max_retries_exceeded(self) -> None:
        class DummyObject:
            config = {
                "delay_range_s": [0, 1],
                "backoff_factor": 2,
                "max_retries": 3,
            }

            @request_repeater
            def func(self) -> Any:
                # Эмулирем эксепшн в функции, чтобы набрать макс. кол-во
                # перезапусков
                raise ValueError("TestError")

        obj = DummyObject()

        with patch("stuff.sleep_between_requests", return_value=0), \
                patch("stuff.get_time_to_sleep", return_value=0), \
                patch("stuff.logger.info") as mock_logger_info:
            result = obj.func()

        self.assertFalse(result)
        mock_logger_info.assert_called_with("Max retries exceeded. Continue.")

    def test_exception_handling(self) -> None:
        class DummyObject:
            config = {
                "delay_range_s": [0, 1],
                "backoff_factor": 0.5,
                "max_retries": 3,
            }

            @request_repeater
            def func(self) -> Any:
                raise ValueError("Something went wrong")

        obj = DummyObject()

        with patch("stuff.get_time_to_sleep", return_value=0), \
                patch("stuff.logger.error") as mock_logger_error:
            result = obj.func()

        self.assertFalse(result)
        mock_logger_error.assert_called_with(
            "Exception in: func: Something went wrong"
        )


class TestRestarterDecorator(unittest.TestCase):
    def setUp(self) -> None:
        logger.setLevel(level=logging.CRITICAL)

    def test_restart_function_successfully(self) -> None:
        class DummyObject:
            config = {
                "restart": {"restart_interval_min": 1, "restart_count": 20}
            }

            def __init__(self):
                self.counter = 0

            @restarter
            def func(self):
                self.counter += 1
                if self.counter <= 3:
                    raise ValueError("TestError")
                return True

        obj = DummyObject()

        with patch("stuff.sleep_between_requests", return_value=0), \
                patch("stuff.logger.critical") as mock_logger_critical, \
                patch("stuff.logger.info") as mock_logger_info:
            result = obj.func()

        self.assertFalse(result)
        self.assertEqual(
            mock_logger_critical.call_count,
            obj.config["restart"]["restart_count"],
        )
        self.assertEqual(
            mock_logger_info.call_count,
            obj.config["restart"]["restart_count"] - 1,
        )

    def test_restart_function_max_restarts_exceeded(self) -> None:
        class DummyObject:
            config = {
                "restart": {"restart_interval_min": 1, "restart_count": 20}
            }

            def __init__(self):
                self.counter = 0

            @restarter
            def func(self):
                self.counter += 1
                raise ValueError("TestError")

        obj = DummyObject()

        with patch("stuff.sleep_between_requests", return_value=0), \
                patch("stuff.logger.critical") as mock_logger_critical:
            result = obj.func()

        self.assertFalse(result)
        self.assertEqual(
            mock_logger_critical.call_count,
            obj.config["restart"]["restart_count"],
        )


if __name__ == "__main__":
    unittest.main()

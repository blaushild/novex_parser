import logging
import logging.config

import re

import random

import os

from time import time, sleep

from typing import Any, Union


logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)


def calculate_delay(restarts: int, initial_delay: int, increase_factor: float) -> float:
    """рассчитывает задержку с учетом повторений и коэффициента увеличения задержки"""
    return (initial_delay + initial_delay * increase_factor) ** (restarts - 1)


def timer(func: Any) -> Any:
    """simple timer decorator"""

    def wrapper(*args, **kwargs):
        start_time = time()
        result = func(*args, **kwargs)
        end_time = time()
        execution_time = end_time - start_time
        logger.info(f"{func.__name__}'s execution time: {round(execution_time, 2)}sec.")
        return result

    return wrapper


def request_repeater(func: Any) -> Any:
    """Декоратор. Повторяет исполнение функции, если в результате её исполнения
    вылетел Exception. Увеличивает время между повторами на коэффициент backoff_factor"""

    def wrapper(obj, *args, **kwargs):
        time_range = obj.config["delay_range_s"]
        backoff_factor = obj.config["backoff_factor"]
        starts = 0
        while True:
            starts += 1
            time_to_sleep = get_time_to_sleep(time_range)
            if starts > obj.config["max_retries"]:
                logger.info(f"Max retries exceeded. Continue.")
                return False
            elif starts > 1:  # с какого повтора начинаем показывать номер попытки
                if time_range == 0:
                    time_range = [1, 1]
                time_to_sleep = calculate_delay(starts, time_range[1], backoff_factor)
                logger.info(f"Trying to get data again. Attempt {starts}")

            sleep_between_requests(time_to_sleep)

            try:
                result = func(obj, *args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Exception in: {func.__name__}: {e}")
        
    return wrapper


def restarter(func: Any) -> Any:
    """Декоратор. перезапускает функцию через заданный интервал заданное кол-во раз"""
    def wrapper(obj, *args, **kwargs):
        counter = 0
        while True:
            counter += 1
            time_to_sleep = obj.config["restart"]["restart_interval_min"] * 60

            if 1 < counter <= obj.config["restart"]["restart_count"]:
                logger.critical("Parser will be restarted after sleep.")
                sleep_between_requests(time_to_sleep)
                obj.__init__() # для сброса устаревших данных

                logger.info(f"Restart #{counter}")

            elif counter > obj.config["restart"]["restart_count"]:
                logger.critical("Parser reached max times of restarts. Exiting.")
                return False
            
            try:
                result = func(obj, *args, **kwargs)
                logger.info("Success.\n")
                return result
            except Exception as e:
                logger.error(f"Exception in: {func.__name__}: {e}")          

    return wrapper


def prepare_string(text: str) -> str:
    """подготовка текстового поля для записи в CSV"""
    # Удаление непечатаемых символов
    printable_text = "".join(filter(lambda x: x.isprintable(), text))

    # Замена специальных символов
    replaced_text = re.sub(r"\n|\t|\r|\xc2\xa0", "", printable_text)

    # Экранирование кавычек внутри текстовых полей
    escaped_text = replaced_text.replace('"', '""')

    # Оборачивание текстового поля в кавычки
    final_text = f'"{escaped_text}"'

    return final_text


def prepare_row(row=list) -> list:
    """готовит строку для записи в CSV"""
    return [prepare_string(el) if isinstance(el, str) else el for el in row]


def get_time_to_sleep(time_range: Union[list, int]) -> int:
    """Выбирает время сна перед очередным запросом"""
    if isinstance(time_range, list):
        min_seconds, max_seconds = time_range
        return random.randint(min_seconds, max_seconds)
    else:
        return 0


def sleep_between_requests(time_range: Union[list, int]) -> None:
    """Делает паузу между запросами"""
    if time_range == 0:
        return

    if isinstance(time_range, (int, float)):
        time_to_sleep = time_range
    else:
        time_to_sleep = get_time_to_sleep(time_range)

    logger.info(f"Sleep {time_to_sleep} seconds.")
    sleep(time_to_sleep)


def create_dirs(directories: list) -> None:
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Directory '{directory}' has been created.")

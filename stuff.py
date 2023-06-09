"""Supporting funcs"""
import logging
import logging.config
import random
from time import time, sleep
from typing import Union, Callable


logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)


def calculate_delay(
    restarts: int, initial_delay: int, increase_factor: float
) -> float:
    """рассчитывает задержку с учетом повторений
    и коэффициента увеличения задержки"""
    return (initial_delay + initial_delay * increase_factor) ** (restarts - 1)


def timer(func: Callable) -> Callable:
    """Декоратор. Измеряет время работы функции"""

    def wrapper(*args, **kwargs):
        start_time = time()
        result = func(*args, **kwargs)
        end_time = time()
        execution_time = end_time - start_time
        logger.info(
            f"{func.__name__}'s execution time: {round(execution_time, 2)}sec."
        )
        return result

    return wrapper


def request_repeater(func: Callable) -> Callable:
    """Декоратор. Повторяет исполнение функции,
    если в результате её исполнения вылетел Exception.
    Увеличивает время между повторами на коэффициент backoff_factor
    """

    def wrapper(obj, *args, **kwargs):
        time_range = obj.config["delay_range_s"]
        backoff_factor = obj.config["backoff_factor"]
        starts = 0
        while True:
            starts += 1
            time_to_sleep = get_time_to_sleep(time_range)
            if starts > obj.config["max_retries"]:
                logger.info("Max retries exceeded. Continue.")
                return False

            # с какого повтора начинаем показывать номер попытки
            elif starts > 1:
                if time_range == 0:
                    time_range = [1, 1]
                time_to_sleep = calculate_delay(
                    starts, time_range[1], backoff_factor
                )
                logger.info(f"Trying to get data again. Attempt {starts}")

            sleep_between_requests(time_to_sleep)

            try:
                result = func(obj, *args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Exception in: {func.__name__}: {e}")

    return wrapper


def restarter(func: Callable) -> Callable:
    """Декоратор. перезапускает функцию через заданный интервал времени
    заданное кол-во раз
    """

    def wrapper(obj, *args, **kwargs):
        counter = 0
        while True:
            counter += 1
            time_to_sleep = obj.config["restart"]["restart_interval_min"] * 60

            if 1 < counter <= obj.config["restart"]["restart_count"]:
                logger.critical("Parser will be restarted after sleep.")
                sleep_between_requests(time_to_sleep)
                obj.__init__()  # для сброса устаревших данных при перезапуске

                logger.info(f"Restart #{counter}")

            elif counter > obj.config["restart"]["restart_count"]:
                logger.critical(
                    "Parser reached max times of restarts. Exiting."
                )
                return False

            try:
                result = func(obj, *args, **kwargs)
                logger.info(
                    f"Function '{func.__name__}' successfully finished."
                )
                return result
            except Exception as e:
                logger.error(f"Exception in: {func.__name__}: {e}")

    return wrapper


def get_time_to_sleep(time_range: Union[list[int], int]) -> int:
    """Выбирает время сна перед очередным запросом"""
    if isinstance(time_range, list):
        min_seconds, max_seconds = time_range
        return random.randint(min_seconds, max_seconds)
    elif isinstance(time_range, int):
        return time_range
    raise TypeError(
        f"time_range must be list of 2 elements or int. {type(time_range)=}"
    )


def sleep_between_requests(time_range: Union[list[int], int]) -> None:
    """Делает паузу между запросами"""
    if time_range == 0:
        return

    if isinstance(time_range, (int, float)):
        time_to_sleep = time_range
    else:
        time_to_sleep = get_time_to_sleep(time_range)

    logger.info(f"Sleep {time_to_sleep} seconds.")
    sleep(time_to_sleep)

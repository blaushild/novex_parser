"""Data handlers"""
import re


def build_sku_category(product: dict) -> str:
    """Создаёт sku_category - Название категории товара в каталоге.
    По иерархии сверху вниз, от родительских категорий к дочерним.
    Например: ”Для животных|Корма для животных|Корма для кошек”."""

    sku_category = product["categories"][0]["title"]
    if "parent" in product["categories"][0]:
        parent = product["categories"][0]["parent"]
        while True:
            sku_category = parent["title"] + "|" + sku_category
            if not parent["parent"]:
                return sku_category

            parent = parent["parent"]


def prepare_string(text: str) -> str:
    """подготовка текстового поля для записи в CSV"""
    if not text:
        return None

    # Удаление непечатаемых символов
    printable_text = "".join(filter(lambda x: x.isprintable(), text))

    # Замена специальных символов
    replaced_text = re.sub(r"\n|\t|\r|\xc2\xa0", "", printable_text)

    # Экранирование кавычек внутри текстовых полей
    escaped_text = replaced_text.replace('"', '""')

    # Оборачивание текстового поля в кавычки

    final_text = f'"{escaped_text}"'

    return final_text


def prepare_row(row: list[str]) -> list:
    """готовит строку для записи в CSV"""
    return [prepare_string(el) if isinstance(el, str) else el for el in row]

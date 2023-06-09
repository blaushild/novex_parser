import threading
import json
import requests
import csv
from datetime import datetime
from typing import Callable

from handlers import build_sku_category
from handlers import prepare_row

from stuff import (
    logger,
    timer,
    request_repeater,
    restarter,
)


RESULT_DIR = "results/"
# файлы для сохранения результатов
STRUCTURE_FILE = RESULT_DIR + "categories.csv"
CATEGORIES_TO_PARSE = RESULT_DIR + "categories_to_parse.csv"
PRODUCTS_FILE = RESULT_DIR + "products.csv"

CONFIG_FILE = "config.json"

# endpoints and urls
BASE_URL = "https://novex.ru/"
CATALOG_URL = BASE_URL + "api/catalog/"
CATEGORIES_ENDPOINT = CATALOG_URL + "categories"
PRODUCTS_ENDPOINT = CATALOG_URL + "products"


class Parser:
    def __init__(self):
        self.config = self.__get_settings_from_config()
        self.config["categories"] = [
            c.replace("/", "") for c in self.config["categories"]
        ]
        self.config["categories_black_list"] = [
            c.replace("/", "") for c in self.config["categories_black_list"]
        ]

        self.all_categories = []  # Все категории и подкатегории
        # список всех slug категорий для парсинга
        self.categories_to_parse = []
        self.products = []  # спаршенные продукты
        # почищенные от продуктов, входящих в категории в black_list
        self.filtered_products = []
        self.processed_products = []
        self.data_to_save = []  # данные, подготовленные для сохранения в CSV

        self.max_threads = self.config["max_threads"]
        self.lock = threading.Lock()
        self.threads = []

    def __get_settings_from_config(self) -> dict:
        """Получает настройки из конфигурационного файла"""
        try:
            with open(CONFIG_FILE, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(
                f"Error reading config file '{CONFIG_FILE}': {str(e)}"
            )
            raise

    @request_repeater
    def fetch_json_data(self, url: str) -> dict:
        """Получает данные из источника"""
        try:
            response = requests.get(
                url=url,
                headers=self.config["headers"],
                timeout=self.config["request_timeout"],
            )
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to {url}: {e}")
            raise

    def _get_categories(self) -> None:
        """Получает все категории и все подкатегории"""
        logger.info("Getting all categories and subcategories.")

        url = CATEGORIES_ENDPOINT + "?withChildren=true"
        response = requests.get(url=url, headers=self.config["headers"])
        response.raise_for_status()

        self.all_categories = response.json()

    def _filter_category(self, category: dict) -> bool:
        """Фильтруем только нужные категории"""
        if category["slug"] in self.config["categories"]:
            self.categories_to_parse.append(category)
            return True

    def _parse_category(self, category: dict) -> None:
        """Проход по категории рекурсивно в случае прохода фильтра добавляет
        в список категорий для парсинга
        """
        if not self.config["categories"]:
            self.categories_to_parse.append(category)
            return

        if self._filter_category(category):
            return

        if "children" in category:
            for child in category["children"]:
                self._parse_category(child)

    def _bypass_categories(self) -> None:
        """Обходит все корневые категории"""
        for category in self.all_categories:
            self._parse_category(category)

    def filter_product(self, product: dict) -> bool:
        """рекурсивный обход всех предков товара(категорий).
        если один из предков в blacklist,
        то товар не попадает в filtered_products
        """
        if "categories" in product and any(
            category["slug"] in self.config["categories_black_list"]
            for category in product["categories"]
        ):
            return True

        if "categories" in product:
            return self.filter_product(product["categories"][0]["parent"])

        if "slug" in product:
            logger.debug(f"{product['slug']=}")

        if (
            "slug" in product
            and product["slug"] in self.config["categories_black_list"]
        ):
            logger.debug(f"Catched {product['slug']=}")
            return True

        if "parent" in product and product["parent"]:
            return self.filter_product(product["parent"])

        return False

    def _filter_products(self) -> None:
        """Чистим от продуктов, находящихся в категориях из
        categories_black_list
        """
        for product in self.products:
            is_blacklisted = self.filter_product(product)
            logger.debug(f"{is_blacklisted=}")
            if is_blacklisted:
                logger.debug(f"Black listed: {product['slug']}")
            else:
                self.filtered_products.append(product)
                logger.debug(f"Added to filtered_products: {product['slug']}")

    def get_product_info(self, product: dict) -> dict:
        """Получает инфу о продукте"""
        url = (
            PRODUCTS_ENDPOINT
            + "/"
            + product["slug"]
            + "?"
            + f"deliveryType={self.config['method']}"
            + f"&shopIds[]={self.config['shop_id']}"
        )

        return self.fetch_json_data(url)

    def _get_products_thread(self) -> None:
        """
        Получаем продукты из категорий categories.
        Для многопоточности.

        https://novex.ru/api/catalog/products?categoryIdOrSlug=dlya-krasoty&contextCityId=463573&deliveryType=pickup&shopIds[]=104&page=1&limit=100

        без параметра limit выдаётся 50 товаров
        ограничений на limit не видел, но увеличивается вероятность
        "кривого" json.
        без параметра page выдаются только товары

        с параметром page выдаёт два ключа:
        items -- здесь товары
        pagination : {
            page : int,
            pages : int,
            total : int, # items in this category
        }
        """

        while True:
            self.lock.acquire()
            if not self.categories_to_parse:
                self.lock.release()
                break

            category = self.categories_to_parse.pop(0)
            self.lock.release()

            logger.info(f"Getting products for '{category['slug']}'")

            page = 0
            while True:
                page += 1

                logger.info(
                    f"Request #{page} for {self.config['products_limit']} "
                    + f"products from {category['slug']}."
                )

                url = (
                    f"{PRODUCTS_ENDPOINT}?"
                    + f"categoryIdOrSlug={category['slug']}"
                    + f"&contextCityId={self.config['city_id']}"
                    + f"&deliveryType={self.config['method']}"
                    + f"&shopIds[]={self.config['shop_id']}"
                    + f"&page={page}"
                    + f"&limit={self.config['products_limit']}"
                )
                logger.debug(f"{url=}")
                response = self.fetch_json_data(url)

                self.products.extend(response["items"])

                if page == 1:
                    logger.info(
                        f"Total items: {response['pagination']['total']}"
                    )
                    logger.info(
                        f"Total pages: {response['pagination']['pages']}"
                    )

                if (
                    response["pagination"]["page"]
                    == response["pagination"]["pages"]
                ):
                    break

    def _enrich_product(self, product: dict) -> None:
        """Обогощает данные о продукте.
        В данном случае добавляется только страна производства товара.
        """
        product["country"] = None

        response = self.get_product_info(product)
        if "characteristics" not in response:
            logger.warning(f"characteristics not found for {product['slug']}")
            return

        for characteristic in response["characteristics"]:
            if characteristic["productProp"]["code"] == "country":
                product["country"] = characteristic["value"]
                logger.info(
                    f"Product '{product['slug']}' has been updated. "
                    + f"Added country: '{product['country']}'."
                )
                break

        self.processed_products.append(product)

    def _enrich_products_thread(self) -> None:
        """Отдельный поток обогощения данных о продукте"""
        while True:
            self.lock.acquire()
            if not self.filtered_products:
                self.lock.release()
                break
            product = self.filtered_products.pop(0)
            self.lock.release()

            self._enrich_product(product)

    def _create_categories_for_csv(
        self, categories: list, respect_black_list: bool = True
    ) -> None:
        """Подготавливает данные для заданных категорий перед записью в файл.
        рекурсивно обходит все подкатегории.
        """
        if not self.data_to_save:
            self.data_to_save.append(
                ["original_id", "title", "id", "parent_id"]
            )

        for category in categories:
            if (
                respect_black_list
                and category["slug"] in self.config["categories_black_list"]
            ):
                continue

            row = []
            row.append(category["id"])  # original_id
            row.append(category["title"])  # name
            row.append(category["slug"])  # id
            if "parent" in category:  # parent_id
                row.append(category["parent"]["slug"])
            else:
                row.append("")

            row = prepare_row(row)

            self.data_to_save.append(row)

            if "children" in category:
                data = self._create_categories_for_csv(category["children"])
                if data:
                    self.data_to_save.append(data)

    def prepare_product_for_csv(self, product: list) -> list:
        """подготавливает данные о товаре для сохранения в CSV"""
        sku_category = build_sku_category(product)
        product_url = "https://novex.ru/catalog/product/" + product["slug"]

        try:
            product_image_link = (
                "https://novex.ru" + product["gallery"][0]["file"]["url"]
            )
        except (TypeError, IndexError) as e:
            logger.warning(
                f"{product['slug']} Image isn't presented. Error: {e}"
            )

            product_image_link = None

        if "productBranchStocks" in product:
            sku_instock = product["productBranchStocks"]
            sku_status = 1 if product["productBranchStocks"] else 0
        else:
            sku_instock = None
            sku_status = None

        sku_country = product["country"] if "country" in product else None

        product = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            float(product["price"]["basePrice"]),
            float(product["price"]["price"]),
            sku_status,
            sku_instock,
            product["sku"],
            product["title"],
            sku_category,
            product["tradeMark"] if product["tradeMark"] else None,
            sku_country,
            product_url,
            product_image_link,
        ]
        product = prepare_row(product)

        return product

    def _prepare_products_for_csv(self, products: list[list]) -> None:
        """подготавливает данные о товарах для сохранения в CSV"""
        self.data_to_save = [
            [
                # Тип данных - текст. Формат: “2023-06-01 08:17:33”
                "price_datetime",
                # Регулярная цена. число, 2 десятичных знака. Пример: 134.99
                "price",
                "price_promo",  # Акционная цена. число, 2 десятичных знака.
                "sku_status",  # наличие товара. 1(0) - (не) в наличии. число.
                "sku_instock",  # остаток товара в выбранной торговой точке
                "sku_article",  # Артикул товара. текст. Пример: 4100242804
                "sku_name",  # Наименование товара.
                "sku_category",
                "sku_brand",
                "sku_country",
                "sku_link",
                "sku_images",  # Прямая ссылка на фотографию товара.
            ],
        ]

        for product in products:
            prepared_product = self.prepare_product_for_csv(product)
            self.data_to_save.append(prepared_product)

        return

    def _save_to_csv(self, filename: str) -> None:
        """Сохраняет данные, хранящиеся в self.data_to_save в формате CSV
        в файл
        """
        logger.info(f"Saving data to '{filename}'.")

        with open(filename, "w", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerows(self.data_to_save)

    def start_multithreading(self, func: Callable) -> None:
        """Запускает функцию в многопоточном режиме.
        Функция должна иметь обеспечение синхронизации
        доступа к общим ресурсам.
        """
        for _ in range(self.max_threads):
            thread = threading.Thread(target=func)
            thread.start()
            self.threads.append(thread)

        for thread in self.threads:
            thread.join()

    @restarter
    def run(self) -> None:
        """Запускает полный цикл парсинга."""

        logger.info("Parsing started.")

        self._get_categories()  # получает все каталоги и подкаталоги, 1 запрос

        # обход полученного дерева категорий для получения категорий,
        # которые будут парситься.
        # сделано на случай категории в целях парсинга в конфиге и
        # отсутствия в источнике
        self._bypass_categories()

        self._create_categories_for_csv(
            self.all_categories, respect_black_list=False
        )
        self._save_to_csv(STRUCTURE_FILE)  # сохраняет полный список категорий
        self.data_to_save = []

        self._create_categories_for_csv(self.categories_to_parse)
        # сохраняет категории для, категории,
        # продукты из которых будут в результатах
        self._save_to_csv(CATEGORIES_TO_PARSE)

        logger.info("Products mining is starting.")
        self.start_multithreading(self._get_products_thread)

        # отфильтровываем продукты из категорий в blacklist'е
        self._filter_products()

        logger.info(
            "Products enrich is starting for "
            + f"{len(self.filtered_products)} products."
        )
        self.start_multithreading(self._enrich_products_thread)

        self._prepare_products_for_csv(self.processed_products)
        self._save_to_csv(PRODUCTS_FILE)

        logger.info("Parsing successfully finished.")
        logger.info(f"Parsed {len(self.data_to_save)} products.")


@timer
def main():
    parser = Parser()
    parser.run()


if __name__ == "__main__":
    main()

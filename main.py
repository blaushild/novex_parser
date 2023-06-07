import json

import requests

import csv

from datetime import datetime

from stuff import (
    logger,
    timer,
    request_repeater,
    prepare_row,
    restarter,
    create_dirs,
)


CONFIG_FILE = "config.json"
BASE_URL = "https://novex.ru/"
CATALOG_URL = BASE_URL + "api/catalog/"
CATEGORIES_ENDPOINT = CATALOG_URL + "categories"
PRODUCTS_ENDPOINT = CATALOG_URL + "products"
PARAMS = {"withChildren": "true"}
REQUEST_TIMEOUT = 5

RESULT_DIR = "results/"
STRUCTURE_FILE = RESULT_DIR + "categories.csv"
CATEGORIES_TO_PARSE = RESULT_DIR + "categories_to_parse.csv"
PRODUCTS_FILE = RESULT_DIR + "products.csv"
PRODUCTS_LIMIT = 2000


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
        self.categories_to_parse = []  # список всех slug категорий для парсинга
        self.products = []  # спаршенные продукты
        # почищенные от продуктов, входящих в категории в black_list
        self.filtered_products = []
        self.data_to_save = []  # данные, подготовленные для сохранения в CSV

    def __get_settings_from_config(self) -> json:
        """получает настройки из конфигурационного файла в JSON"""
        try:
            with open(CONFIG_FILE, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error reading config file '{CONFIG_FILE}': {str(e)}")
            raise

    def _create_url_categories(self) -> str:
        """создаёт url для получения категорий с учётом заданных параметров"""
        params = [f"{key}={value}" for key, value in PARAMS.items()]
        url = CATEGORIES_ENDPOINT + "?" + "&".join(params)

        return url

    def get_categories(self) -> None:
        """Получает все категории и все подкатегории"""
        logger.info("Getting all categories and subcategories.")
        url = self._create_url_categories()
        response = requests.get(url=url, headers=self.config["headers"])
        response.raise_for_status()
        self.all_categories = response.json()

        return

    @request_repeater
    def __get_json(self, url: str) -> json:
        """получает ответ от источника данных в JSON"""
        response = requests.get(
            url=url, headers=self.config["headers"], timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()

        return response.json()

    def __filter_category(self, category: json) -> bool:
        """Фильтруем только нужные категории"""
        if category["slug"] in self.config["categories"]:
            self.categories_to_parse.append(category)
            return True

    def __build_sku_category(self, product: json) -> str:
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

    def parse_category(self, category: json) -> None:
        """Проход по категории рекурсивно в случае прохода фильтра добавляет в список категорий для парсинга"""
        if not self.config["categories"]:
            self.categories_to_parse.append(category)
            return

        if self.__filter_category(category):
            return

        if "children" in category:
            for child in category["children"]:
                self.parse_category(child)

        return

    def bypass_categories(self) -> None:
        """Обходит все корневые категории"""
        for category in self.all_categories:
            self.parse_category(category)

    def create_categories_for_csv(
        self, categories: list, respect_black_list: bool = True
    ) -> None:
        """Подготавливает данные для заданных категорий перед записью в файл.
        рекурсивно обходит все подкатегории.
        """
        if not self.data_to_save:
            self.data_to_save.append(["original_id", "title", "id", "parent_id"])

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
                data = self.create_categories_for_csv(category["children"])
                if data:
                    self.data_to_save.append(data)

        return

    def save_to_csv(self, filename: str, data: list[list] = None) -> None:
        """Сохраняет данные, либо хранящиеся в self.data_to_save в формате CSV в файл"""
        logger.info(f"Saving data to '{filename}'.")
        if not data:
            data = self.data_to_save

        with open(filename, "w", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerows(self.data_to_save)

        return

    def __filter_products(self, products: list) -> None:
        """Чистим от продуктов, находящихся в категориях categories_black_list"""
        for product in products:
            if "categories" in product and any(
                category["slug"] in self.config["categories_black_list"]
                for category in product["categories"]
            ):
                logger.debug(f"Black listed: {product['slug']}")
                continue

            self.filtered_products.append(product)
            logger.debug(f"Added to filtered_products {product['slug']}")

        return

    def get_products(self) -> None:
        """
        Получаем продукты из категорий categories.

        https://novex.ru/api/catalog/products?page=1&categoryIdOrSlug=sredstva-gigieny&contextCityId=463573&limit=2000

        https://novex.ru/api/catalog/products?categoryIdOrSlug=sredstva-gigieny&contextCityId=463573&deliveryType=pickup&shopIds[]=104&page=1&limit=10000

        https://novex.ru/api/catalog/products?categoryIdOrSlug=dlya-krasoty&contextCityId=463573&deliveryType=pickup&shopIds[]=104&page=1&limit=100

        без параметра limit выдаётся 50 товаров
        ограничений на limit не видел, но увеличивается вероятность "кривого" json
        без параметра page выдаются только товары

        с параметром page выдаёт два ключа:
        items -- здесь товары
        pagination : {
            page : int,
            pages : int,
            total : int, # items in this category
        }
        """

        for category in self.categories_to_parse:
            if category["slug"] in self.config["categories_black_list"]:
                logger.info(
                    f"Category '{category['slug']}' scipped according to black list."
                )
                continue

            logger.info(f"Getting products for '{category['slug']}'")

            page = 0
            while True:
                page += 1

                logger.info(f"Request #{page} for {PRODUCTS_LIMIT} products.")

                url = (
                    f"{PRODUCTS_ENDPOINT}?"
                    + f"categoryIdOrSlug={category['slug']}"
                    + f"&contextCityId={self.config['city_id']}"
                    + f"&deliveryType={self.config['method']}"
                    + f"&shopIds[]={self.config['shop_id']}"
                    + f"&page={page}"
                    + f"&limit={PRODUCTS_LIMIT}"
                )
                logger.debug(f"{url=}")
                response = self.__get_json(url)

                self.products.extend(response["items"])

                if page == 1:
                    logger.info(f"Total items: {response['pagination']['total']}")
                    logger.info(f"Total pages: {response['pagination']['pages']}")

                if response["pagination"]["page"] == response["pagination"]["pages"]:
                    break

        return

    def get_product_info(self, product: json) -> json:
        """Получает инфу о продукте"""
        url = (
            PRODUCTS_ENDPOINT
            + "/"
            + product["slug"]
            + "?"
            + f"deliveryType={self.config['method']}"
            + f"&shopIds[]={self.config['shop_id']}"
        )
        logger.debug(f"{url=}")

        return self.__get_json(url)

    def enrich_product(self, product: json) -> None:
        """Обогощает данные о продукте.
        В данном случае добавляется только страна производства товара.
        """
        product["country"] = None

        response = self.get_product_info(product)
        if not "characteristics" in response:
            logger.warning(f"characteristics not found for {product['slug']}")
            return

        for characteristic in response["characteristics"]:
            if characteristic["productProp"]["code"] == "country":
                product["country"] = characteristic["value"]
                logger.debug(f"Country '{product['country']}' has been added to product.")
                break
        return

    def enrich_products(self, products) -> None:
        """Обогощает данные продуктов."""
        logger.info(f"Start to enrich {len(products)} products data.")
        for i, product in enumerate(products, 1):
            logger.info(f"Enreaching product({i}/{len(products)}): {product['slug']}")
            self.enrich_product(product)

        return True

    def __prepare_product_to_csv(self, product: list) -> list:
        """подготавливает данные о товаре для сохранения в CSV"""
        sku_category = self.__build_sku_category(product)
        product_url = "https://novex.ru/catalog/product/" + product["slug"]

        try:
            product_image_link = "https://novex.ru" + product["gallery"][0]["file"]["url"]
        except (TypeError, IndexError) as e:
            logger.warning(f"{product['slug']} Image isn't presented. Error: {e}")

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
            product["tradeMark"],
            sku_country,
            product_url,
            product_image_link,
        ]
        product = prepare_row(product)

        return product

    def prepare_products_to_csv(self, products: list[list]) -> None:
        """подготавливает данные о товарах для сохранения в CSV"""
        self.data_to_save = [
            [
                "price_datetime",  # Тип данных - текст. Формат: “2023-06-01 08:17:33”
                "price",  # Регулярная цена. число, 2 десятичных знака. Пример: 134.99
                "price_promo",  # Акционная цена. число, 2 десятичных знака. Пример: 99.99
                "sku_status",  # наличие товара. 1 - в наличии. 0 - не в наличии. число.
                "sku_instock",  # остаток товара в выбранной торговой точке
                "sku_article",  # Артикул товара. Тип данных - текст. Пример: 4100242804
                "sku_name",  # Наименование товара.
                "sku_category",
                "sku_brand",
                "sku_country",
                "sku_link",
                "sku_images",  # Прямая ссылка на фотографию товара.
            ],
        ]

        for product in products:
            prepared_product = self.__prepare_product_to_csv(product)
            self.data_to_save.append(prepared_product)

        return

    @restarter
    def run(self) -> None:
        """Запускает полный цикл парсинга."""

        dirs = [RESULT_DIR, ]
        create_dirs(dirs)

        logger.info("Parsing started.")

        self.get_categories()
        self.bypass_categories()

        self.create_categories_for_csv(self.all_categories, respect_black_list=False)
        self.save_to_csv(STRUCTURE_FILE)
        self.data_to_save = []

        self.create_categories_for_csv(self.categories_to_parse)
        self.save_to_csv(CATEGORIES_TO_PARSE)

        self.get_products()
        self.__filter_products(self.products)
        self.enrich_products(self.filtered_products)

        self.prepare_products_to_csv(self.filtered_products)
        self.save_to_csv(PRODUCTS_FILE)

        logger.info("Parsing successfully finished.")


@timer
def main():
    parser = Parser()
    parser.run()


if __name__ == "__main__":
    main()

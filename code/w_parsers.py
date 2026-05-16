from abc import ABC, abstractmethod

import requests
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re

import pandas as pd

PATH: str = 'C:\\Users\\Вадимъ\\Documents\\GitHub\\CoffeePlusPlus\\'

class ParserPlusPlus(ABC):
    """
    Абстрактный класс для парсеров. В будущем он поможет нам парсить другие сайты
    """
    def __init__(self):
        self.last_page: int = 0
        self.urls: list[str] = []
    
    @abstractmethod
    def generate_url(self, num: int) -> str: pass

    def generate_urls(self) -> list[str]:

        urls: list[str] = []

        for i in range(self.last_page):

            url: str = self.generate_url(i + 1)
            urls.append(url)
        
        self.urls = urls
        
        return urls
    
    @abstractmethod
    async def parse_html(self, html: str) -> pd.DataFrame: pass

    async def parse(self):
        """
        Базовая функция для парсинга: создаёт задачи на скачивания html'ек, после парсит нужные вещи на каждой странице и сохраняет
        """
        async with aiohttp.ClientSession() as sess:
            tasks = [self.async_request(sess, url) for url in self.urls]
            htmls: list[str] = await asyncio.gather(*tasks)

            tasks = [self.parse_html(html) for html in htmls]
            dfs: list[pd.DataFrame] = await asyncio.gather(*tasks)

            df = pd.concat(dfs, ignore_index=True)

        self.df = df
        return df
    
    @staticmethod
    async def async_request(sess: aiohttp.ClientSession, url: str) -> str:
        async with sess.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:

          if response.status == 200:
            return await response.text()

          else:
            print(f"Ошибка {response.status} для {url}")
            return ""
    
    def to_csv(self, file_name: str):
        """ Сохраняем напаршенно в csv """
        self.df.to_csv(PATH + f"input/{file_name}.csv", index=False, encoding='utf-8-sig')

class MetroParser(ParserPlusPlus):

    brand_token: str = "Бренд"
    type_token: str = "Вид"

    """ Парсер для магазина METRO """
    def __init__(self, path: str, eshop_order: bool = True, in_stock: bool = True) -> None:
        """
        path — путь к странице с нужными товарами относительно https://online.metro-cc.ru/category/
        eshop_order, in_stock — флаги того, хотим ли мы 1) искать товары доступные для онлайн заказа, 2) в целом в наличии
        """
        super().__init__()

        self.path = path
        self.eshop_order: bool = eshop_order
        self.in_stock: bool = in_stock

        first_page: BeautifulSoup = BeautifulSoup( requests.get(self.generate_url(1)).text, features="html.parser")

        links = first_page.find_all('a', class_='v-pagination__item')
        self.last_page: int = int( links[-1].get_text() ) if links else 1 # предпоследний элемент в METRO — всегда ссылка на последнюю страницу

        # парсим значения бренда и типа на основе данных в поиске на сайте (вау!)
        self.brands: list[str] = self.parse_filter(first_page, self.brand_token)
        self.types: list[str] = self.parse_filter(first_page, self.type_token)

        self.generate_urls()

    def generate_url(self, num: int) -> str:
        return f'https://online.metro-cc.ru/category/{self.path}?in_stock={int(self.in_stock)}&page={num}&eshop_order={int(self.eshop_order)}'

    async def parse_html(self, html: str) -> pd.DataFrame:
        """
        Сердце парсера — по html для каждой страницы в пагинации создаёт ДатаФрейм с товарами на ней
        """
        soup: BeautifulSoup = BeautifulSoup( html, features="html.parser" )

        goods_divs = soup.find_all('div', class_="product-card__content")

        goods: pd.DataFrame = pd.DataFrame({
            'Товар': pd.Series(dtype='object'),
            'Поставщик': pd.Series(dtype='object'),
            'Цена': pd.Series(dtype='float64'),
            'Количество': pd.Series(dtype='int64'),
            'Единица': pd.Series(dtype='object'),
            'Цена за кг/л': pd.Series(dtype='float64'),
            'Рейтинг': pd.Series(dtype='float64')
        })

        for good_div in goods_divs:

            title: str = good_div.find('span', class_="product-card-name__text").get_text().lower()

            price_str: str = good_div.find('span', class_="product-price__sum-rubles").get_text()
            price_clear: float = float( re.sub(r'[^\d.]', '', price_str) )
            
            rating = good_div.find('span', class_="product-card-rating__rating")
            rating = float( rating.get_text().strip() ) if rating else None

            type, producer, quantity_int, quantity_type = self.parse_title(title, self.types, self.brands)

            if quantity_int:

                if quantity_type == 'мл' or quantity_type == 'г':
                    price_real = ( price_clear / quantity_int) * 1000

                else:
                    price_real = price_clear / quantity_int if quantity_int else None

                price_real = round( price_real, 2)

            goods.loc[len(goods)] = [type, producer, price_clear, quantity_int, quantity_type, price_real, rating]
        
        return goods

    @staticmethod
    def parse_filter(soup: BeautifulSoup, filter: str) -> list[str]:
        
        main_div = soup.find('div', attrs={'data-filter-group': filter})
        spans = main_div.find_all('span', class_="catalog-checkbox__text")

        types = [span.get_text().strip().lower() for span in spans]

        return types

    @classmethod
    def parse_title(cls, title: str, types: list[str], brands: list[str]) -> tuple[str, str, int, str]:
        """
        По наименованию товара на странице парсим его тип, производителя и единицу измерения. (Привет, любимое ДЗ4!)
        Изначальная версия хорошо подходила для молока и (неожиданно) колбасы, но для других желанных товаров нередко ошибалась.
        Для исправления этого под каждый товар были созданы свои парсеры с отличным parse_title
        """    

        print(cls)
        print(brands)
        print(types)
        producer: str = ""
        for brand in brands:

            if brand in title:

                producer = brand
                break

        name: str = ""
        for type in types:

            if type in title:
                name = type
                break

        quantity_int, quantity_type = cls.parse_quantity(title)

        return name, producer, quantity_int, quantity_type

    @staticmethod
    def parse_quantity(text: str) -> tuple[int | None, str | None]:
        """
        Парсим единицу измерения и её значение
        Паттерн: целое число (или десятичное) + возможно пробел + единица измерения
        """
        pattern = r'(\d+(?:\.\d+)?)\s*([а-я]+)$'
        match = re.search(pattern, text.strip())
        
        if match:
            quantity_int: int = int(float(match.group(1)))  # преобразуем в int
            quantity_type: str = match.group(2)
            return quantity_int, quantity_type
        else:
            print( f"Не удалось распарсить строку: {text}" )
            return None, None

# _______________ ЧАСТНЫЕ ПАРСЕРЫ ___________________

class MilkParser(MetroParser):
    def __init__(self, path: str, eshop_order: bool = True, in_stock: bool = True) -> None:
        super().__init__(path, eshop_order, in_stock)

        self.types = ["молоко"]

class ZoomerMilkParser(MetroParser):
    @classmethod
    def parse_title(cls, title: str, types: list[str], brands: list[str]) -> tuple[str, str, int, str]:
        
        cleared_title = title.replace('соев', 'соя').replace('овся', 'овес')

        return super().parse_title(cleared_title, types, brands)

    def __init__(self, path: str, eshop_order: bool = True, in_stock: bool = True) -> None:
        super().__init__(path, eshop_order, in_stock)

        self.types += ["банан", "кокос", "миндаль", "овес", "орех", "рис", "соя", "фундук"]

class DrinksParser(MetroParser):
    type_token = "Вкус"

    @classmethod
    def parse_title(cls, title: str, types: list[str], brands: list[str]) -> tuple[str, str, int, str]:
        
        cleared_title = title.replace('яблоч', 'яблоко').replace('бруснич', 'брусника').replace('яблоч', 'яблоко').replace('вишн', 'вишня').replace('яблоч', 'яблоко').replace("клюквен", "клюква").replace("ягодн", "ягода")

        return super().parse_title(cleared_title, types, brands)

class SportParser(MetroParser):
    type_token = "Тип"
    
    def __init__(self, path: str, eshop_order: bool = True, in_stock: bool = True) -> None:
        super().__init__(path, eshop_order, in_stock)

        self.brands.append('fitness shock')

class CoffeeParser(MetroParser):
    type_token = "Тип"

# _____ ФАБРИКА ПАРСЕРОВ !!! ____

class ParserFabric():
    _parsers = {
        "molochnye-prodkuty-syry-i-yayca/moloko": MilkParser,
        "rastitelnoe-moloko": ZoomerMilkParser,
        "soki-morsy-nektary": DrinksParser,
        "sportivnoe-pitanie": SportParser,
        "kofe-v-zernakh": CoffeeParser,
    }

    @classmethod
    def create(cls, path: str) -> MetroParser:

        for nick, parser in cls._parsers.items():

            if nick in path:
                return parser(path)
        
        return MetroParser(path) # стадартный возвращаем, если товар неособенный
        
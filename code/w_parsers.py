from abc import ABC, abstractmethod
import random

import requests
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re

from playwright.async_api import async_playwright

import pandas as pd

PATH: str = 'C:\\Users\\Вадимъ\\Documents\\GitHub\\CoffeePlusPlus\\'

class ParserPlusPlus(ABC):
    """
    Абстрактный класс для парсеров. В будущем он поможет нам парсить другие сайты
    """
    def __init__(self):
        self._last_page: int = 0
        self._urls: list[str] = []
    
    @abstractmethod
    def _generate_url(self, num: int) -> str: pass

    def _generate_urls(self) -> list[str]:

        urls: list[str] = []

        for i in range(self._last_page):

            url: str = self._generate_url(i + 1)
            urls.append(url)
        
        self._urls = urls
        
        return urls
    
    @abstractmethod
    async def _parse_html(self, html: str) -> pd.DataFrame: pass

    async def parse(self):
        """
        Базовая функция для парсинга: создаёт задачи на скачивания html'ек, после парсит нужные вещи на каждой странице и сохраняет
        """
        async with aiohttp.ClientSession() as sess:
            tasks = [self._async_request(sess, url) for url in self._urls]
            htmls: list[str] = await asyncio.gather(*tasks)

            tasks = [self._parse_html(html) for html in htmls]
            dfs: list[pd.DataFrame] = await asyncio.gather(*tasks)

            df = pd.concat(dfs, ignore_index=True)

        self.df = df
        return df
    
    @staticmethod
    async def _async_request(sess: aiohttp.ClientSession, url: str) -> str:
        async with sess.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:

          if response.status == 200:
            return await response.text()

          else:
            print(f"Ошибка {response.status} для {url}")
            return ""
    
    def to_csv(self, file_name: str):
        """ Сохраняем напаршенно в csv """
        self.df.to_csv(PATH + f"input/{file_name}.csv", index=False, encoding='utf-8-sig')
    
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
    
    @staticmethod
    def count_price(quantity_int: int, quantity_type: str, price: int | float) -> float:
        if quantity_int:

            price_real = price / quantity_int

            if quantity_type == 'мл' or quantity_type == 'г' or quantity_type == 'гр':
                price_real *= 1000

            return round( price_real, 2)

        return None

# __________________________ METRO _______________________________________

class MetroParser(ParserPlusPlus):

    _brand_token: str = "Бренд"
    _type_token: str = "Вид"

    """ Парсер для магазина METRO """
    def __init__(self, path: str, eshop_order: bool = True, in_stock: bool = True) -> None:
        """
        path — путь к странице с нужными товарами относительно https://online.metro-cc.ru/category/
        eshop_order, in_stock — флаги того, хотим ли мы 1) искать товары доступные для онлайн заказа, 2) в целом в наличии
        """
        super().__init__()

        self._path = path
        self._eshop_order: bool = eshop_order
        self._in_stock: bool = in_stock

        first_page: BeautifulSoup = BeautifulSoup( requests.get(self._generate_url(1)).text, features="html.parser")

        links = first_page.find_all('a', class_='v-pagination__item')
        self._last_page: int = int( links[-1].get_text() ) if links else 1 # предпоследний элемент в METRO — всегда ссылка на последнюю страницу

        # парсим значения бренда и типа на основе данных в поиске на сайте (вау!)
        self._brands: list[str] = self._parse_filter(first_page, self._brand_token)
        self._types: list[str] = self._parse_filter(first_page, self._type_token)

        self._generate_urls()

    def _generate_url(self, num: int) -> str:
        return f'https://online.metro-cc.ru/category/{self._path}?in_stock={int(self._in_stock)}&page={num}&eshop_order={int(self._eshop_order)}'

    async def _parse_html(self, html: str) -> pd.DataFrame:
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

            type, producer, quantity_int, quantity_type = self.parse_title(title, self._types, self._brands)

            price_real = self.count_price(quantity_int, quantity_type, price_clear)

            goods.loc[len(goods)] = [type, producer, price_clear, quantity_int, quantity_type, price_real, rating]
        
        return goods

    @staticmethod
    def _parse_filter(soup: BeautifulSoup, filter: str) -> list[str]:
        
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


# ___________________________ ЧАСТНЫЕ ПАРСЕРЫ ______________________________

class MilkParser(MetroParser):
    def __init__(self, path: str, eshop_order: bool = True, in_stock: bool = True) -> None:
        super().__init__(path, eshop_order, in_stock)

        self._types = ["молоко"]

class ZoomerMilkParser(MetroParser):
    @classmethod
    def parse_title(cls, title: str, types: list[str], brands: list[str]) -> tuple[str, str, int, str]:
        
        cleared_title = title.replace('соев', 'соя').replace('овся', 'овес')

        return super().parse_title(cleared_title, types, brands)

    def __init__(self, path: str, eshop_order: bool = True, in_stock: bool = True) -> None:
        super().__init__(path, eshop_order, in_stock)

        self._types += ["банан", "кокос", "миндаль", "овес", "орех", "рис", "соя", "фундук"]

class DrinksParser(MetroParser):
    _type_token = "Вкус"

    @classmethod
    def parse_title(cls, title: str, types: list[str], brands: list[str]) -> tuple[str, str, int, str]:
        
        cleared_title = title.replace('яблоч', 'яблоко').replace('бруснич', 'брусника').replace('яблоч', 'яблоко').replace('вишн', 'вишня').replace('яблоч', 'яблоко').replace("клюквен", "клюква").replace("ягодн", "ягода")

        return super().parse_title(cleared_title, types, brands)

class SportParser(MetroParser):
    _type_token = "Тип"
    
    def __init__(self, path: str, eshop_order: bool = True, in_stock: bool = True) -> None:
        super().__init__(path, eshop_order, in_stock)

        self._brands.append('fitness shock')

class CoffeeParser(MetroParser):
    _type_token = "Тип"

# _____ ФАБРИКА ПАРСЕРОВ !!! ____

class ParserFabric():
    _parsers: dict[str, object] = {
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

# __________________________ ДИНАМИЧЕСКИЙ ПАРСИНГ (PLAYWRIGHT) _______________________________________

class DynamicParser(ParserPlusPlus):
    """
    Абстрактный класс для динамического парсера
    """
    def __init__(self):
        super().__init__()

        self._headless = True

    async def parse(self):
        """
        Базовая функция для динамического парсинга: создаёт задачи на на работу в браузере и сохраняет правильный html, после парсит нужные вещи на каждой странице и сохраняет
        """
        async with async_playwright() as p:

            browser = await p.chromium.launch(headless = self._headless)

            tasks = [self._prepare_html(browser, url) for url in self._urls]
            htmls: list[str] = await asyncio.gather(*tasks)
            
            await browser.close()

            tasks = [self._parse_html(html) for html in htmls]
            dfs: list[pd.DataFrame] = await asyncio.gather(*tasks)

            df = pd.concat(dfs, ignore_index=True)

        self.df = df
        return df
    
    @abstractmethod
    async def _prepare_html(browser, url): pass

    @staticmethod
    async def block_resources(route):

        resource_type = route.request.resource_type

        if resource_type in [
            "image",
            "media",
            "font",
            "stylesheet"
        ]:
            await route.abort()

        else:
            await route.continue_()

class TastyCoffeeParser(DynamicParser):
    """
    Парсер для сайта TastyCoffee
    Используем Playwright, чтобы получить цены за 1кг зёрен (это дешевле)
    """
    def __init__(self, path: str, headless: bool = True) -> None:
        """
        path — путь к странице с нужными товарами относительно https://shop.tastycoffee.ru/
        """
        super().__init__()

        self._path = path
        self._headless = headless

        first_page: BeautifulSoup = BeautifulSoup( requests.get(self._generate_url(1)).text, features="html.parser")

        links = first_page.find_all('a', class_='pagination-btn')
        self._last_page: int = int( links[-1].get_text() ) if links else 1 # последний элемент — ссылка на последнюю страницу

        self._generate_urls()

    def _generate_url(self, num: int) -> str:
        return f'https://shop.tastycoffee.ru/{self._path}?page={num}'
    
    async def _prepare_html(self, browser, url):
        page = await browser.new_page()
        await page.route("**/*", self.block_resources)

        await page.goto(
            url,
            timeout=240000
        )
        
        try:
            await page.wait_for_selector("div[class='tc-weight']", timeout=60000)

            elements = page.locator("div[class='tc-weight']")

            count = await elements.count()
            await asyncio.sleep(
                random.uniform(2, 5)
            )

            for i in range(count):
                await elements.nth(i).click()
                await asyncio.sleep(
                    random.uniform(1, 2)
                )
            
            return await page.content()

        except TimeoutError:
            print(f"Не нашли тыкалки на {url}")
            
            return ''
        finally:
            await page.close()
    
    async def _parse_html(self, html: str) -> pd.DataFrame:
        """
        Сердце парсера — по html для каждой страницы в пагинации создаёт ДатаФрейм с товарами на ней
        """
        soup: BeautifulSoup = BeautifulSoup( html, features="html.parser" )

        goods_divs = soup.find_all('div', class_="div.tc-tile")

        goods: pd.DataFrame = pd.DataFrame({
            'Название': pd.Series(dtype='object'),
            'Способ обработки': pd.Series(dtype='object'),
            'Тип': pd.Series(dtype='object'),
            'Описание': pd.Series(dtype='object'),
            'Плотность': pd.Series(dtype='float64'),
            'Кислотность': pd.Series(dtype='float64'),
            'Количество': pd.Series(dtype='int64'),
            'Единица': pd.Series(dtype='object'),
            'Цена': pd.Series(dtype='int64'),
            'Цена за кг/шт': pd.Series(dtype='float64'),
            'Рейтинг': pd.Series(dtype='float64'),
            'Число отзывов': pd.Series(dtype='int64'),
        })

        for good_div in goods_divs:

            title: str = good_div.select_one(".tc-tile__title a").get_text().strip()
            processing: str = good_div.select_one(".tc-tooltip__btn div").get_text().strip()
            type: str = good_div.select_one(".tc-tile__top:first-child").get_text().strip()

            description: str = good_div.select_one("p[itemprop='description']").get_text(" ")
            description = re.sub(r"\s+", " ", description).strip()

            density: float = float( good_div.select_one(".tc-tile__scale:first-child .tc-progress__object")['width'].strip() )
            acidity: float = float( good_div.select_one(".tc-tile__scale:last-child .tc-progress__object")['width'].strip() )

            quantity: str = good_div.select_one("div[class='tc-weight active'] span").get_text().strip()

            quantity_int: int
            quantity_type: str
            quantity_int, quantity_type = self.parse_quantity(quantity)

            price: int = int( good_div.select_one(".tc-tile__bottom button span.text-nowrap").get_text().strip() )
            price_real: float = self.count_price(quantity_int, quantity_type, price)
            
            rating = good_div.select_one(".tc-tile-rating span")
            rating = float( rating.get_text().strip() ) if rating else None

            reviews = good_div.select_one(".tc-tile-rating a span")
            reviews = float( rating.get_text().strip() ) if rating else None

            goods.loc[len(goods)] = [title, processing, type, description, density, acidity, quantity_int, quantity_type, price, price_real, rating, reviews]
        
        return goods

if __name__ == "__main__":

    parser = TastyCoffeeParser("coffee", False)
    df = asyncio.run( parser.parse() )
    parser.to_csv("TastyCoffee")

    print(df)
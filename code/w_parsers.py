from abc import ABC, abstractmethod

import requests
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re

import pandas as pd

PATH: str = 'C:\\Users\\Вадимъ\\Documents\\GitHub\\CoffeePlusPlus\\'

class ParserPlusPlus(ABC):

    def __init__(self):
        self.last_page: int = 0
        self.urls: list[str] = []
        self.file_name: str = "good"
    
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
        async with aiohttp.ClientSession() as sess:
            tasks = [self.async_request(sess, url) for url in self.urls]
            htmls: list[str] = await asyncio.gather(*tasks)

            tasks = [self.parse_html(html) for html in htmls]
            dfs: list[pd.DataFrame] = await asyncio.gather(*tasks)

            df = pd.concat(dfs, ignore_index=True)

        df.to_csv(PATH + f"output/{self.file_name}.csv", index=False, encoding='utf-8-sig')
        return df
    
    @staticmethod
    async def async_request(sess: aiohttp.ClientSession, url: str) -> str:
        async with sess.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:

          if response.status == 200:
            return await response.text()

          else:
            print(f"Ошибка {response.status} для {url}")
            return ""

class MetroParser(ParserPlusPlus):

    def __init__(self, path: str, file_name: str = "METRO", eshop_order: bool = True, in_stock: bool = True) -> None:

        super().__init__()

        self.path = path
        self.file_name = file_name
        self.eshop_order: bool = eshop_order
        self.in_stock: bool = in_stock

        first_page: BeautifulSoup = BeautifulSoup( requests.get(self.generate_url(1)).text, features="html.parser")

        links = first_page.find_all('a', class_='v-pagination__item')
        self.last_page: int = int( links[-1].get_text() ) # предпоследний элемент в METRO — всегда ссылка на последнюю страницу

        self.generate_urls()

    def generate_url(self, num: int) -> str:
        return f'https://online.metro-cc.ru/category/{self.path}?in_stock={int(self.in_stock)}&page={num}&eshop_order={int(self.eshop_order)}'

    async def parse_html(self, html: str) -> pd.DataFrame:
        
        soup: BeautifulSoup = BeautifulSoup( html, features="html.parser" )

        goods_divs = soup.find_all('div', class_="product-card__content")

        goods: pd.DataFrame = pd.DataFrame({
            'Товар': pd.Series(dtype='object'),
            'Поставщик': pd.Series(dtype='object'),
            'Цена': pd.Series(dtype='float64'),
            'Количество': pd.Series(dtype='int64'),
            'Единица': pd.Series(dtype='object'),
            'Цена за кг/л': pd.Series(dtype='float64')
        })

        for good_div in goods_divs:

            title: str = good_div.find('span', class_="product-card-name__text").get_text()
            price_str: str = good_div.find('span', class_="product-price__sum-rubles").get_text()
            price_clear: float = float( re.sub(r'[^\d.]', '', price_str) )

            type: str = title.split()[0]
            producer: str = title.split()[1] # да, грубо, но нам важно найти самый выгодные товары, а там по первому слову можно будет их обнаружить легко

            quantity_real: None | float = None
            quantity_int: int | None
            quantity_type: str | None
            quantity_int, quantity_type = MetroParser.parse_quantity(title)

            if quantity_int:

                if quantity_type == 'мл' or quantity_type == 'г':
                    quantity_real = ( price_clear / quantity_int) * 1000
                else:
                    quantity_real = price_clear / quantity_int if quantity_int else None

                quantity_real = round( quantity_real, 2)

            

            goods.loc[len(goods)] = [type, producer, price_clear, quantity_int, quantity_type, quantity_real]
        
        return goods

    @staticmethod
    def parse_quantity(text: str) -> tuple[int | None, str | None]:
        # Паттерн: целое число (или десятичное) + возможно пробел + единица измерения
        pattern = r'(\d+(?:\.\d+)?)\s*([а-я]+)$'
        match = re.search(pattern, text.strip())
        
        if match:
            quantity_int: int = int(float(match.group(1)))  # преобразуем в int
            quantity_type: str = match.group(2)
            return quantity_int, quantity_type
        else:
            print( f"Не удалось распарсить строку: {text}" )
            return None, None
    
if __name__ == "__main__":
    milk = MetroParser("molochnye-prodkuty-syry-i-yayca/moloko", "milk")
    print( asyncio.run( milk.parse() ) )

    kolbasa = MetroParser("myasnye-delikatesy/kolbasy-vetchina", "kolbasa")
    print( asyncio.run( kolbasa.parse() ) )
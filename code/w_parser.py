from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup

class ParserPlusPlus(ABC):

    @property
    @abstractmethod
    def url(self) -> str: pass

    @abstractmethod
    def check_pagenation(self, soup: BeautifulSoup) -> bool: pass

    def get_soups(self) -> list[BeautifulSoup]:

        soups: list[BeautifulSoup] = []

        while(True):
            
            soup: BeautifulSoup = BeautifulSoup( requests.get(self.url).text, features="html.parser")
            soups.append(soup)

            if self.check_pagenation(soup): # проверяем не дошли ли мы до конца пагенации
                self.soups = soups
                print("Your delicious borshes are ready! Bon appetite!")
                break

            self.page += 1
        
        return soups

class MetroParser(ParserPlusPlus):

    def __init__(self, path: str, eshop_order: bool = False, in_stock: bool = False) -> None:

        self.page: int = 1

        self.path = path
        self.eshop_order: bool = eshop_order
        self.in_stock: bool = in_stock

        self.soups: list[BeautifulSoup] = []

    @property
    def url(self) -> str:
        return f'https://online.metro-cc.ru/category/{self.path}?in_stock={int(self.in_stock)}&page={self.page}&eshop_order={int(self.eshop_order)}'
    
    def check_pagenation(self, soup: BeautifulSoup) -> bool:
        return self.page != 1 and len( soup.find_all('a', class_='v-pagination__navigation') ) <= 1

milk = MetroParser("molochnye-prodkuty-syry-i-yayca/moloko", True, True)
print( len(milk.get_soups()) )


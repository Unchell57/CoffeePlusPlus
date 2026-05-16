import asyncio
from w_parsers import MetroParser

# парсим предложение молока
milk: MetroParser = MetroParser("molochnye-prodkuty-syry-i-yayca/moloko")
asyncio.run( milk.parse() )
milk.to_csv("milk")
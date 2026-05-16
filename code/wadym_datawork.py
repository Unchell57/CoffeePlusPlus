import asyncio
from w_parsers import MetroParser

milk = asyncio.run( MetroParser("molochnye-prodkuty-syry-i-yayca/moloko", "milk").parse() )
kolbasa = asyncio.run( MetroParser("myasnye-delikatesy/kolbasy-vetchina", "kolbasa").parse() )
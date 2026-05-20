import asyncio
from w_parsers import ParserFactory

# создаём парсеры для всех интересных нам товаров, запускаем их и сохраняем полученные данные

parsers_data: dict[str, str] = {
    "milk": "molochnye-prodkuty-syry-i-yayca/moloko",
    "zoomer_milk": "molochnye-prodkuty-syry-i-yayca/rastitelnye-produkty/rastitelnoe-moloko",
    "sport_food": "zdorovoe-pitanie/sportivnoe-pitanie",
    "drinks": "bezalkogolnye-napitki/soki-morsy-nektary",
    "coffee": "chaj-kofe-kakao/kofe/kofe-v-zernakh",
}

async def main():
    parsers = [ParserFactory.create(path) for path in parsers_data.values()]
    await asyncio.gather(*(parser.parse() for parser in parsers))
    for parser, (good, _) in zip(parsers, parsers_data.items()):
        parser.to_csv(good)

asyncio.run(main())
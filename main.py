import asyncio
import json
from typing import Any

import aiohttp
import requests
from fastapi import FastAPI

app = FastAPI()


async def f(id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://steamcommunity.com/market/',
        'X-Requested-With': 'XMLHttpRequest'
    }
    inventory_url = f'https://steamcommunity.com/inventory/{id}/730/2?l=english&count=75&preserve_bbcode=1&raw_asset_properties=1'
    response1 = requests.get(inventory_url, headers=headers).json()['descriptions']
    names_items = [response1[i]['market_hash_name'] for i in range(len(response1))]
    ids = {}
    with open('cs2.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for name in names_items:
        id = data.get(name)
        if id is not None:
            ids[name] = data.get(name)
    price_url = 'https://steamcommunity.com/market/itemordershistogram?country=RU&language=english&currency=5&item_nameid='

    async with aiohttp.ClientSession(headers=headers) as session:
        async def fetch_price(name, item_id):
            async with session.get(f'{price_url}{item_id}') as resp:
                data = await resp.json()
                return name, data['sell_order_graph'][0][0] if data.get('sell_order_graph') else 'N/A'

        tasks = [fetch_price(name, item_id) for name, item_id in ids.items()]
        results = await asyncio.gather(*tasks)

        result = dict(results)
        result['all_price'] = sum(v for v in result.values() if isinstance(v, (int, float)))
        return result


@app.get('/id/{id}')
async def get_prices(id: str):
    result = await f(id)
    return result
import asyncio
import json
import os
from typing import Any, Dict
from bs4 import BeautifulSoup
import aiohttp
import requests
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


async def f(id: str) -> Dict[str, Any]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://steamcommunity.com/market/',
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        inventory_url = f'https://steamcommunity.com/inventory/{id}/730/2?l=english&count=75&preserve_bbcode=1&raw_asset_properties=1'
        response1 = requests.get(inventory_url, headers=headers, timeout=10).json()

        if not response1 or 'descriptions' not in response1:
            return {"error": "Inventory not found or private"}

        descriptions = response1['descriptions']
        names_items = [descriptions[i]['market_hash_name'] for i in range(len(descriptions))]

        image_url = 'https://steamcommunity-a.akamaihd.net/economy/image/'
        images = [image_url + descriptions[i]['icon_url'] for i in range(len(descriptions))]

        ids = {}
        # Загружаем файл с ID предметов
        if os.path.exists('cs2.json'):
            with open('cs2.json', 'r', encoding='utf-8') as f:
                data = json.load(f)

            for name in names_items:
                item_id = data.get(name)
                if item_id is not None:
                    ids[name] = {'id': item_id, 'image': images[names_items.index(name)]}
        else:
            # Если файла нет, создаем базовую структуру
            for i, name in enumerate(names_items):
                ids[name] = {'id': '', 'image': images[i]}

        price_url = 'https://steamcommunity.com/market/itemordershistogram?country=RU&language=english&currency=5&item_nameid='

        async with aiohttp.ClientSession(headers=headers) as session:
            async def fetch_price(name: str, item_data: Dict) -> tuple:
                if not item_data['id']:
                    return name, 'N/A'

                try:
                    async with session.get(f'{price_url}{item_data["id"]}', timeout=10) as resp:
                        data = await resp.json()
                        if data.get('sell_order_graph'):
                            return name, data['sell_order_graph'][0][0]
                        else:
                            return name, 'N/A'
                except Exception:
                    return name, 'N/A'

            tasks = [fetch_price(name, item_data) for name, item_data in ids.items()]
            results = await asyncio.gather(*tasks)

            result = {}
            all_price = 0.0

            for name, price in results:
                if isinstance(price, (int, float)):
                    all_price += price

                result[name] = {
                    'price': price,
                    'image': ids[name]['image']
                }

            result['all_price'] = round(all_price, 2)

            url_account = f'https://steamcommunity.com/profiles/{id}'
            response_account = requests.get(url_account).text
            soup = BeautifulSoup(response_account, 'html.parser')

            # Получаем имя пользователя
            user_name_element = soup.find('span', class_='actual_persona_name')
            user_name = user_name_element.text if user_name_element else "Unknown User"

            # Получаем аватар
            avatar_element = soup.find('div', class_='playerAvatarAutoSizeInner')
            user_icon = None
            if avatar_element:
                img_element = avatar_element.find('img')
                if img_element and 'srcset' in img_element.attrs:
                    user_icon = img_element['srcset'].split()[0]  # Берем первый URL из srcset
                elif img_element and 'src' in img_element.attrs:
                    user_icon = img_element['src']

            if not user_icon:
                user_icon = "/static/default-avatar.png"

            return {
                'user_id': id,
                'user_name': user_name,
                'user_icon': user_icon,
                'data': result,
                'item_count': len(result) - 1  # исключаем all_price
            }

    except Exception as e:
        return {"error": str(e)}


@app.get('/', response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post('/search')
async def search_user(user_id: str = Form(...)):
    return RedirectResponse(f'/id/{user_id}', status_code=303)


@app.get('/id/{id}', response_class=HTMLResponse)
async def get_prices_html(id: str, request: Request):
    result = await f(id)
    result['request'] = request
    return templates.TemplateResponse("index.html", result)
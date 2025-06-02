import json
import httpx
import random
from urllib.parse import quote
from typing import Optional, AsyncGenerator, Dict
import asyncio

INSTAGRAM_ACCOUNT_DOCUMENT_ID = "9310670392322965"

HEADERS = {
    "cookie": (
        "csrftoken=T05ZimStD3gnOyudc3HQDHn5PxluQ8uG; "
        "datr=hPtwZ7ssBSadIZKXshqa7IIm; "
        "ds_user_id=74834442290; "
        "ig_did=1137D978-0911-451E-94E4-B75792B66D7C; "
        "ig_nrcb=1; "
        "mid=Z3D7hAALAAErVNPFlAoaWbAaDLed; "
        "ps_l=1; "
        "ps_n=1; "
        "rur=NCG\\05474834442290\\0541780173868:01fe28ff4be08404269cdbdb8f6fcf26b5272b782a36584f4a5ca074c84639e816819ce3; "
        "sessionid=74834442290%3A5Cu6briVegxCvs%3A11%3AAYffM0Z17YA3SdB59oALl6gR-37jk4zb4O0hjInTeg; "
        "wd=1366x160"
    ),
    "x-csrftoken": "T05ZimStD3gnOyudc3HQDHn5PxluQ8uG",
    "x-ig-app-id": "936619743392459",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
    "referer": "https://www.instagram.com/",
    "x-asbd-id": "198387",
    "accept-language": "en-US,en;q=0.9",
    "accept": "*/*",
    "content-type": "application/x-www-form-urlencoded"
}



async def scrape_user_posts(
    username: str,
    page_size: int = 12,
    max_pages: Optional[int] = None
) -> AsyncGenerator[Dict, None]:
    base_url = "https://www.instagram.com/graphql/query"
    variables = {
        "after": None,
        "before": None,
        "data": {
            "count": page_size,
            "include_reel_media_seen_timestamp": True,
            "include_relationship_info": True,
            "latest_besties_reel_media": True,
            "latest_reel_media": True
        },
        "first": page_size,
        "last": None,
        "username": username,
        "__relay_internal__pv__PolarisIsLoggedInrelayprovider": True,
        "__relay_internal__pv__PolarisShareSheetV3relayprovider": True
    }

    prev_cursor = None
    page_number = 1

    async with httpx.AsyncClient(headers=HEADERS, timeout=httpx.Timeout(20.0)) as session:
        while True:
            payload = f"variables={quote(json.dumps(variables, separators=(',', ':')))}&doc_id={INSTAGRAM_ACCOUNT_DOCUMENT_ID}"
            response = await session.post(base_url, data=payload)
            response.raise_for_status()
            data = response.json()

            try:
                posts = data["data"]["xdt_api__v1__feed__user_timeline_graphql_connection"]
            except KeyError:
                print(f"[{username}] Error: Unexpected response structure")
                break

            for post in posts.get("edges", []):
                yield {
                    "username": username,
                    "post": post["node"]
                }

            page_info = posts.get("page_info", {})
            if not page_info.get("has_next_page"):
                print(f"[{username}] Scraping finished at page {page_number}")
                break

            if page_info.get("end_cursor") == prev_cursor:
                print(f"[{username}] No new posts, stopping")
                break

            prev_cursor = page_info["end_cursor"]
            variables["after"] = prev_cursor
            page_number += 1

            if max_pages and page_number > max_pages:
                break

            await asyncio.sleep(random.uniform(2, 5))  # Simula tiempo de espera humana entre páginas


async def consult_profiles(usernames: list[str], max_pages: int = 2):
    all_posts = []

    for username in usernames:
        print(f"\n🔍 Consultando @{username}")
        await asyncio.sleep(random.uniform(3, 8))  # Pausa entre perfiles

        async for post in scrape_user_posts(username, max_pages=max_pages):
            all_posts.append(post)
            print(f"[{username}] Post ID: {post['post'].get('id')}")

        print(f"✅ Finalizado: {username}")

    # Guardar resultados en un archivo JSON
    with open("posts_instagram.json", "w", encoding="utf-8") as f:
        json.dump(all_posts, f, indent=2, ensure_ascii=False)

    print("\n📁 Todos los datos han sido guardados en 'posts_instagram.json'")


# Lista de perfiles a consultar
user_list = [
    "migueluribet",
    "soyvahos",
    "juluscategui",
    "patriciamosq",
    "alvarouribevelez",
    "oposicion_col",
    "andres.forerom",
    "cedemocratico",
    "mariapaz_buitrago",
    "jjuscategui",
    "sandraforeror",
    "angelcustodiocabrera"
]

# Ejecutar
if __name__ == "__main__":
    asyncio.run(consult_profiles(user_list, max_pages=2))

import os
import re
import logging
import httpx
import jmespath
import asyncio
import json
import random
import datetime
from typing import AsyncGenerator
from urllib.parse import quote
from typing import Dict, Optional
from dotenv import load_dotenv


load_dotenv()
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class InstaScraperService:
    def __init__(self,db):
        self.db = db
        self.collection = db["InstPosts"]
        self.sessionID= os.getenv("INSTASESSION")
        self.INSTAGRAM_ACCOUNT_DOCUMENT_ID = "9310670392322965"
        self.headers = {
            "x-ig-app-id": "936619743392459",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "*/*",
        }
        self.HEADERS = {
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

    def clean_post(post: dict):
        post['_id'] = str(post.get('_id')) if '_id' in post else None
        return post

    def parse_user(data: Dict) -> Dict:
        """Parse instagram user's hidden web dataset for user's data"""
        log.debug("parsing user data %s", data.get('username', 'unknown'))
        result = jmespath.search(
            """{
                name: full_name,
                username: username,
                id: id,
                category: category_name,
                business_category: business_category_name,
                phone: business_phone_number,
                email: business_email,
                bio: biography,
                bio_links: bio_links[].url,
                homepage: external_url,        
                followers: edge_followed_by.count,
                follows: edge_follow.count,
                facebook_id: fbid,
                is_private: is_private,
                is_verified: is_verified,
                profile_image: profile_pic_url_hd,
                video_count: edge_felix_video_timeline.count,
                videos: edge_felix_video_timeline.edges[].node.{
                    id: id, 
                    title: title,
                    shortcode: shortcode,
                    thumb: display_url,
                    url: video_url,
                    views: video_view_count,
                    tagged: edge_media_to_tagged_user.edges[].node.user.username,
                    captions: edge_media_to_caption.edges[].node.text,
                    comments_count: edge_media_to_comment.count,
                    comments_disabled: comments_disabled,
                    taken_at: taken_at_timestamp,
                    likes: edge_liked_by.count,
                    location: location.name,
                    duration: video_duration
                },
                image_count: edge_owner_to_timeline_media.count,
                images: edge_felix_video_timeline.edges[].node.{
                    id: id, 
                    title: title,
                    shortcode: shortcode,
                    src: display_url,
                    url: video_url,
                    views: video_view_count,
                    tagged: edge_media_to_tagged_user.edges[].node.user.username,
                    captions: edge_media_to_caption.edges[].node.text,
                    comments_count: edge_media_to_comment.count,
                    comments_disabled: comments_disabled,
                    taken_at: taken_at_timestamp,
                    likes: edge_liked_by.count,
                    location: location.name,
                    accesibility_caption: accessibility_caption,
                    duration: video_duration
                },
                saved_count: edge_saved_media.count,
                collections_count: edge_saved_media.count,
                related_profiles: edge_related_profiles.edges[].node.username
            }""",
            data,
        )
        return result
    
    async def scrape_user_posts(self, username: str, page_size: int = 12, max_pages: Optional[int] = None) -> AsyncGenerator[Dict, None]:
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

        async with httpx.AsyncClient(headers=self.HEADERS, timeout=httpx.Timeout(20.0)) as session:
            while True:
                payload = f"variables={quote(json.dumps(variables, separators=(',', ':')))}&doc_id={self.INSTAGRAM_ACCOUNT_DOCUMENT_ID}"
                response = await session.post(base_url, data=payload)
                response.raise_for_status()
                data = response.json()

                try:
                    posts = data["data"]["xdt_api__v1__feed__user_timeline_graphql_connection"]
                except KeyError:
                    log.error(f"[{username}] Error: Unexpected response structure")
                    break

                for post in posts.get("edges", []):
                    yield {
                        "username": username,
                        "post": post["node"]
                    }

                page_info = posts.get("page_info", {})
                if not page_info.get("has_next_page"):
                    log.info(f"[{username}] Scraping finished at page {page_number}")
                    break

                if page_info.get("end_cursor") == prev_cursor:
                    log.info(f"[{username}] No new posts, stopping")
                    break

                prev_cursor = page_info["end_cursor"]
                variables["after"] = prev_cursor
                page_number += 1

                if max_pages and page_number > max_pages:
                    break

                await asyncio.sleep(random.uniform(2, 5))

    async def scrape_by_profile(self,profile:str):
        all_posts =[]
        max_pages =2
        print(f"\n 🔍 Consultando @{profile}")
        await asyncio.sleep(random.uniform(3, 8))

        async for post in self.scrape_user_posts(profile,max_pages=max_pages):
            all_posts.append(post)
            print(f"[{profile}] Post ID: {post['post'].get('id')}")
            uid = post['post'].get('id')
            code_uid =  post.get('post',{}).get('code')
            
            if not code_uid:
                print(f"Error: El 'Code' de la publicacion no se encontro en el post. {uid}")

            if self.collection.find_one({'post.code':code_uid}):
                print(f"La publicación con el código '{code_uid}' ya existe en la base de datos.")
            else:
                print(f"La publicación con el código '{code_uid}' NO existe en la base de datos.")
                post = self.reestructured(post)
                self.collection.insert_one(post)

        print(f"✅ Finalizado: {profile}")
        for post in all_posts:
            post['_id'] = str(post.get('_id')) if '_id' in post else None 

        return all_posts

    def reestructured(self, post:dict)->dict:
        uid = post['post'].get('id')
        code_post = post.get('post',{}).get('code')
        created_at = datetime.datetime.utcfromtimestamp(post.get('post',{}).get('caption',{}).get('created_at'))
        parse_text = self.clean_text(post.get('post',{}).get('caption',{}).get('text'))
        user = post.get("user")
        videos = post.get("video_versions")
        coments = post.get("comment_count")
        like_counts= post.get("like_count")
        product_type =post.get("product_type")
        carousel_media_count = post.get("carousel_media_count")
        carousel_media = post.get("carousel_media")
        location = post.get("location")
        audio = post.get("has_audio")
        clips_metadata = post.get("clips_metadata")
        media_cropping_info = post.get("media_cropping_info")
        timeline_pinned_user_ids = post.get("timeline_pinned_user_ids")
        __typename = post.get("__typename")
        data = {
            "uid":uid,
            "code_post":code_post,
            "created_at":created_at,
            "parse_text":parse_text,
            "user":user,
            "videos":videos,
            "comments":coments,
            "like_counts":like_counts,
            "product_type": product_type,
            "carousel_media_count":carousel_media_count,
            "carousel_media":carousel_media,
            "location":location,
            "audio":audio,
            "clips_metadata":clips_metadata,
            "media_cropping_data":media_cropping_info,
            "timeline_pinned_user_ids":timeline_pinned_user_ids,
            "__typename":__typename
        }
        return data

    async def consult_profiles(self,usernames: list[str]):
        all_posts = []
        max_pages = 2
        for username in usernames:
            print(f"\n🔍 Consultando @{username}")
            await asyncio.sleep(random.uniform(3, 8))  # Pausa entre perfiles

            async for post in self.scrape_user_posts(username, max_pages=max_pages):
                all_posts.append(post)
                self.collection.insert_one(post)
                print(f"[{username}] Post ID: {post['post'].get('id')}")

            print(f"✅ Finalizado: {username}")

        print("\n📁 Todos los datos han sido finalizados.")
        return [self.clean_post(p) for p in all_posts]
    
    def clean_text(self,text):
        emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticonos
        "\U0001F300-\U0001F5FF"  # Símbolos y pictogramas
        "\U0001F680-\U0001F6FF"  # Transporte y mapas
        "\U0001F1E0-\U0001F1FF"  # Banderas
        "\U00002700-\U000027BF"  # Símbolos varios
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
        )
        return emoji_pattern.sub(r'', text)
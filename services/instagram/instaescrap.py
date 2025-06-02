import asyncio
import json
import httpx
import jmespath
import logging
from typing import Dict

# Configuración de logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

headers = {
    "x-ig-app-id": "936619743392459",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "*/*",
}


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


async def scrape_user(username: str) -> Dict:
    """Scrape Instagram user's data asynchronously"""
    async with httpx.AsyncClient(headers=headers, timeout=10) as client:
        response = await client.get(
            f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
        )
        raw_data = response.json()
        user_data = raw_data.get("data", {}).get("user", {})
        return parse_user(user_data)


async def main():
    parsed_user = await scrape_user("google")
    print(json.dumps(parsed_user, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

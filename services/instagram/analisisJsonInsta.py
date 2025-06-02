import json

with open("posts_instagram.json", encoding="utf-8") as f:
    data = json.load(f)

def extract_post_info(item):
    post = item.get("post", {})
    caption = post.get("caption") or {}

    return {
        "username": item.get("username"),
        "post": {
            "code": post.get("code"),
            "pk": post.get("pk"),
            "id": post.get("id"),
            "caption": {
                "pk": caption.get("pk"),
                "text": caption.get("text")
            },
            "is_paid_partnership": post.get("is_paid_partnership"),
            "sponsor_tags": post.get("sponsor_tags"),
            "affiliate_info": post.get("affiliate_info"),
            "user": post.get("user"),
            "coauthor_producers": post.get("coauthor_producers"),
            "invited_coauthor_producers": post.get("invited_coauthor_producers"),
            "comment_count": post.get("comment_count"),
            "comments_disabled": post.get("comments_disabled"),
            "disabled_for_viewer": post.get("commenting_disabled_for_viewer"),
            "top_likers": post.get("top_likers"),
            "like_count": post.get("like_count"),
            "social_context": post.get("social_context"),
            "can_viewer_reshare": post.get("can_viewer_reshare"),
            "location": post.get("location"),
            "has_audio": post.get("has_audio"),
            "clips_metadata": post.get("clips_metadata"),
            "taken_at": post.get("taken_at"),
            "caption_is_edited": post.get("caption_is_edited"),
            "video_versions": post.get("video_versions"),
            "image_versions2": post.get("image_versions2"),
        }
    }

# Aplicar la extracción a todos los elementos
extracted = [extract_post_info(item) for item in data]

# Guardar en un nuevo archivo
with open("extracted_clean.json", "w", encoding="utf-8") as f:
    json.dump(extracted, f, indent=2, ensure_ascii=False)

print("✅ Extracción completada. Archivo guardado como extracted_clean.json")

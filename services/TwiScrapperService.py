# twitter_scraper_service.py
import json
import os
import random
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from twikit import Client
from models import TwitterScreape, TweetContent

load_dotenv()

class TwitterScraperService:
    def __init__(self,db):
        self.client = Client("en-US")
        self.db = db
        self.collection = db["tweets"]


    async def login(self):
        await self.client.login(
            auth_info_1=os.getenv('TWEET_USER'),
            auth_info_2=os.getenv('TWEET_EMAIL'),
            password=os.getenv('TWEET_PASS'),
            cookies_file='cookies.json'
        )

    async def tweets_by_profile(self, profile: str):
        await self.login()
        tweets_data = []
        try:
            user = await self.client.get_user_by_screen_name(profile)
            tweets = await user.get_tweets(tweet_type="Tweets", count=100)
            now = datetime.now(timezone.utc)
            one_week_ago = now - timedelta(days=7)

            for tweet in tweets:
                await asyncio.sleep(random.uniform(1.5, 3.0))
                if tweet.created_at:
                    try:
                        created_at_dt = datetime.strptime(tweet.created_at, "%a %b %d %H:%M:%S %z %Y")
                        if created_at_dt > one_week_ago:
                            tweets_data.append(TweetContent(
                                usuario=profile,
                                fecha=created_at_dt.date().isoformat(),
                                tweet=tweet.full_text
                            ))
                    except ValueError:
                        continue
        except Exception as e:
            print(f"Error with {profile}: {e}")
        return tweets_data

    async def scrape_and_save_profiles(self, profiles: list[str]):
        tweets_list = []
        for profile in profiles:
            tweets = await self.tweets_by_profile(profile)
            if tweets:
                tweet_doc = TwitterScreape(
                    profile=profile,
                    posts=tweets,
                    Rt=str(len(tweets)),
                    scrape_date=datetime.utcnow()
                )
                tweets_list.extend(tweets)
                await self.collection.insert_one(tweet_doc.dict(by_alias=True))
                print(f"✔ Guardado: {profile} → {len(tweets)} tweets")
                await asyncio.sleep(random.uniform(8.0, 15.0))
                                    
        return tweets_list

    async def save_scrape_profile(self, profile:str):
        tweets = await self.tweets_by_profile(profile)
        if tweets:
                tweet_doc = TwitterScreape(
                    profile=profile,
                    posts=tweets,
                    Rt=str(len(tweets)),
                    scrape_date=datetime.utcnow()
                )
                await self.collection.insert_one(tweet_doc.dict(by_alias=True))
                print(f"✔ Guardado: {profile} → {len(tweets)} tweets")

        return tweets


    async def tweets_profiles(profiles:list,self):
        todos_los_tweets = []
        for username in profiles:
            if username.strip():
                tweets = await self.tweets_by_profile(username)
                todos_los_tweets.extend(tweets)
                await asyncio.sleep(random.uniform(8.0, 15.0))

        print(f"Total de tweets guardados: {len(todos_los_tweets)}")
        with open("tweets_recientes.json", "w", encoding="utf-8") as jsonfile:
            json.dump(todos_los_tweets, jsonfile, indent=2, ensure_ascii=False)

        return todos_los_tweets  # <- si quieres seguir trabajando con ellos luego

from fastapi import APIRouter, Body, Request, Response, HTTPException, status
from fastapi.encoders import jsonable_encoder
from typing import List
from fastapi.responses import JSONResponse
from models import FacebookScrape, InstagramScrape, TwitterScreape
from services import TwiScrapperService

router =  APIRouter()


@router.get("/twitter/{profile}")
async def twitterscrapper(profile:str, request:Request):
    try:
        db = request.app.database
        scraper = TwiScrapperService(db)
        tweets = await scraper.save_scrape_profile(profile)
        tweets = jsonable_encoder(tweets)
        return JSONResponse(content=tweets)
    except Exception as e:
        raise HTTPException(status_code=500, detail =str(e))
    

@router.get("/twitter/profiles")
async def accountsScrapper(profiles:List[str],request:Request):
    try:
        db = request.app.database
        scraper = TwiScrapperService(db)
        tweets = scraper.scrape_and_save_profiles(profiles)
        tweets = jsonable_encoder(tweets)
        return JSONResponse(content=tweets)

    except Exception as e:
        raise HTTPException(status_code=500, detail =str(e))

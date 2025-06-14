from fastapi import APIRouter, Body, Request, Response, HTTPException, status
from fastapi.encoders import jsonable_encoder
from typing import List
from fastapi.responses import JSONResponse
from services.TwitterScraperService import TwitterScraperService
from services.InstaScraperService import InstaScraperService
from services.FaceScraperService import FaceScraperService

router =  APIRouter()


@router.get("/twitter/{profile}")
async def twitterscrapper(profile:str, request:Request):
    try:
        db = request.app.database
        scraper = TwitterScraperService(db)
        tweets = await scraper.save_scrape_profile(profile)
        tweets = jsonable_encoder(tweets)
        return JSONResponse(content=tweets)
    except Exception as e:
        raise HTTPException(status_code=500, detail =str(e))
    

@router.post("/twitter/profiles")
async def accountsScrapper(profiles:List[str],request:Request):
    try:
        db = request.app.database
        scraper = TwitterScraperService(db)
        tweets = await scraper.scrape_and_save_profiles(profiles)
        tweets = jsonable_encoder(tweets)
        return JSONResponse(content=tweets)

    except Exception as e:
        raise HTTPException(status_code=500, detail =str(e))
    
@router.get("/instagram/{profile}")
async def instagramscraper(profile:str, request:Request):
    try:
        db = request.app.database
        scrapper = InstaScraperService(db)
        return await scrapper.scrape_by_profile(profile)

    except Exception as e:
        raise HTTPException(status_code=500, detail =str(e))
    
@router.post("/instagram/profiles")
async def instagramprofilesscr(profiles:List[str], request:Request):
    try:
        db=request.app.database
        scrapper = InstaScraperService(db)
        posts = await scrapper.consult_profiles(profiles)
        posts = jsonable_encoder(posts)
        return JSONResponse(content=posts)
        
    except Exception as e:
        raise HTTPException(status_code= 500, detail={e})


@router.get("/Facebook/{profile}")
async def faceScraper(profile:str, request:Request):
    try: 
        db= request.app.database
        cookie_file:str = "Scrappers_Proyect/services/cookiesFC.json"
        scraper = FaceScraperService(profile,db,cookie_file)
        max_posts = 30
        return await scraper.scrape_posts(max_posts)
    except Exception as e:
        raise HTTPException(status_code=500, detail =str(e))

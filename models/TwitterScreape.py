from pydantic import BaseModel, Field
from datetime import datetime
from typing import List
import uuid

class TweetContent(BaseModel):
    usuario: str
    fecha: str
    tweet: str

class TwitterScreape(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    profile: str
    posts: List[TweetContent]
    Rt: str
    scrape_date: datetime

    class Config:
        populate_by_name = True

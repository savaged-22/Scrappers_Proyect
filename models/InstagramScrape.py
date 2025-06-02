import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class InstagramScrape(BaseModel):
    id: str = Field(default_factory=uuid.uuid4, alias ="_id")
    profile:str 
    posts:dict
    scrape_date: datetime | None 
from fastapi import FastAPI
from dotenv import dotenv_values
from pymongo import MongoClient
from services.routes import router as scrape_router

#Valores de configuraciones.
app = FastAPI()
config = dotenv_values(".env")

@app.get("/")
async def root():
    return {"message": "Welcome to the PyMongo tutorial!"}

#DB stablishment. 
@app.on_event("startup")
def startup_db_client():
    app.mongodb_client = MongoClient(config["MONGO_URI"])
    app.database= app.mongodb_client[config["DB_NAME"]]
    print("Connected to the MongoDB database!")

@app.on_event("shutdown")
def shutdown_db_client():
    app.mongodb_client.close()


app.include_router(scrape_router, tags=["Scrapper"], prefix="/scrapper")
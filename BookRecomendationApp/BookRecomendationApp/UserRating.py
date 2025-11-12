import pandas as pd
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient


app = FastAPI(title="User Rated Books API")

# ---------------- Output model ----------------
class UserRatings(BaseModel):
    title: str
    author: str
    user_rating: float


# ---------------- Connect to Mongo database ----------------
MONGO_URI = "mongodb+srv://<db_username>:<db_password>@agilemtu.knrhvja.mongodb.net/?appName=AgileMTUers" # <--- Will need to update once the correct DB has been created
db = client["UserDatabase"]             # <-- Will need to update once the correct DB has been created
use_book_collection = db["book_ratings"]   


# ---------------- Get User Book Ratings ----------------
@app.get("/ratedBooks}", response_model = List[UserRatings])
def get_user_ratings(username_X: Optional[str] - Header(None)):
    if not username_X:
        raise  HTTPException(status_code=401, detail="Not authenticated")
    
    user_book_ratings = list(use_book_collection.find(
        {
            "username": username_X.lower(),
            "user_books" : {"$gte": 1, "$lte": 5}
        }
    ))

    if user_book_ratings.empty:
        raise  HTTPException(status_code=404, detail="You have no ratings yet!")
    
    return [
        {
            "title": book["title"],
            "author": book["author"],
            "user_rating": book["user_rating"]
        }
        for book in user_book_ratings
    ]
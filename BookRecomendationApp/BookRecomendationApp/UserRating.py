import pandas as pd
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="User Rated Books API")

# ---------------- Output model ----------------
class UserRatings(BaseModel):
    title: str
    author: str
    user_rating: float


# ---------------- Load database ----------------
books = pd.read_csv(r"BookRecomendationApp\books.csv")

# ---------------- Get User Book Ratings ----------------
@app.get("/ratedBooks}", response_model = List[UserRatings])
def get_user_ratings(username_X: Optional[str] - Header(None)):
    if not username_X:
        raise  HTTPException(status_code=401, detail="Not authenticated")
    
    user_book_ratings = books[
        (books["username"].str.lower() == username_X.lower()) &
        (books["user_rating"].between(1,5))
    ]

    if user_book_ratings.empty:
        raise  HTTPException(status_code=404, detail="You have no ratings yet!")
    
    return user_book_ratings.to_dict(orient="records")
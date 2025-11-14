from pymongo import MongoClient
from bson import ObjectId
from UserRating import UserRatings

# ---------------- Connect to Mongo database ----------------
MONGO_URI = "mongodb+srv://<db_username>:<db_password>@agilemtu.knrhvja.mongodb.net/?appName=AgileMTU"
client = MongoClient(MONGO_URI)
db = client["UserDatabase"]

book_db = db["Books"]
user_db = db["Users"]
user_book_collection = db["User_book_ratings"]

# ---------------- User Input ----------------
book_title = input("Please enter the title of the book: ").strip
book_author = input("Please enter the author of the book: ").strip

# ---------------- Check if the book is on the system ----------------
book = book_db.find_one({"title:" book_title, "author": book_author})
if book:
    book_id = book["_id"]
    print(f"'{book_title}' by '{book_author}' was found, please add your rating.")
else:
    print(f"'{book_title}' by '{book_author}' was not found, please try again!")
    exit(1)

# ---------------- Check if user has already rated the book ----------------
user_rating = user_book_collection.find_one({
    "book_id": book_id
})

if user_rating:
    print("You have already rated this book, to update please click on Update Rating!")
    exit(1)
else:
    print("You have not yet rated this book. Please add you rating below")

# ---------------- Ask for user rating input ----------------
while True:
    rate_input = input("Pleas enter your rating (1-5): ").strip()
    try:
        rating = float(rate_input)
        if rating < 1 or rating > 5:
            raise ValueError
        break
    except ValueError:
        print("Invalid input. Please entre a number between 1 and 5")

# ---------------- Add User Rating ----------------
user_book_collection.insert_one({
    "book_id": book_id,
    "title": book_title,
    "author": book_author,
    "rating": rate_input
})




from nicegui import ui, app
import pandas as pd
import hashlib
import os
import base64
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests
import json
import asyncio
import httpx
from collections import Counter

# ---------------- CONFIG ----------------
ITERATIONS = 100_000
SALT_SIZE = 16
MONGO_URI = "mongodb+srv://liam:admin@agilemtu.knrhvja.mongodb.net/?appName=AgileMTU"
DB_NAME = "book_rating_app"
COLLECTION_NAME = "bookModel"
# ----------------------------------------

# ---------------- PASSWORD UTILS ----------------
def hash_password(password: str) -> str:
    salt = os.urandom(SALT_SIZE)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return base64.b64encode(salt + key).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    decoded = base64.b64decode(stored_hash.encode("utf-8"))
    salt = decoded[:SALT_SIZE]
    key = decoded[SALT_SIZE:]
    new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return new_key == key
# -----------------------------------------------


# ---------------- USER DATABASE (SIMPLE DEMO) ----------------
users = {
    "admin": hash_password("admin123"),  # default login
}
# -------------------------------------------------------------


# ---------------- LOAD BOOK DATA ----------------
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    books_cursor = collection.find({})
    books_list = list(books_cursor)
    books = pd.DataFrame(books_list)
    client.close()
    # Extract year from publication_date for display consistency
    if 'publication_date' in books.columns:
        books['release_year'] = pd.to_datetime(books['publication_date'], errors='coerce').dt.year
    else:
        books['release_year'] = 'N/A'

except Exception as e:
    books = pd.DataFrame()
    print(f"Error loading data from MongoDB: {e}")
# ------------------------------------------------


# ---------------- AUTH LOGIC ----------------
def safe_navigate(path: str) -> None:
    nav = getattr(ui, 'navigate', None)
    if nav and hasattr(nav, 'to'):
        nav.to(path)
        return
    # Final fallback (works for both internal/external)
    ui.run_javascript(f"window.location.href='{path}'")

def handle_login(username, password):
    if username in users and verify_password(password, users[username]):
        app.storage.user.update({"username": username, "authenticated": True})
        ui.notify(f"Welcome, {username}", color="positive")
        safe_navigate("/dashboard")
    else:
        ui.notify("Invalid username or password", color="negative")

def handle_registration(username, password):
    if not username or not password:
        ui.notify("Username and password cannot be empty", color="negative")
        return
    if username in users:
        ui.notify("Username already exists", color="negative")
        return
    
    users[username] = hash_password(password)
    ui.notify(f"User {username} registered successfully! Please log in.", color="positive")
    safe_navigate("/")

def handle_logout():
    app.storage.user.clear()
    safe_navigate('/')
# ---------------------------------------------


# ---------------- GUI PAGES ----------------
@ui.page("/")
def login_page():
    if app.storage.user.get("authenticated"):
        safe_navigate("/dashboard")
        return
    with ui.column().classes('w-full h-screen items-center justify-center bg-gray-100'):
        with ui.card().classes('w-96 p-8 shadow-xl rounded-lg'):
            ui.label("📚 Book Recommendation Login").classes("text-3xl mb-6 font-bold text-center text-gray-700")
            
            with ui.input("Username").classes('w-full mb-4') as username:
                username.props('outlined clearable')
                with username.add_slot('prepend'):
                    ui.icon('person')

            with ui.input("Password", password=True, password_toggle_button=True).classes('w-full mb-6') as password:
                password.props('outlined clearable')
                with password.add_slot('prepend'):
                    ui.icon('lock')

            with ui.row().classes("w-full justify-center"):
                ui.button("Login", on_click=lambda: handle_login(username.value, password.value)).classes("w-28 bg-blue-600 text-white")
                ui.button("Register", on_click=lambda: safe_navigate("/register")).classes("w-28")

@ui.page("/register")
def register_page():
    with ui.column().classes('w-full h-screen items-center justify-center bg-gray-100'):
        with ui.card().classes('w-96 p-8 shadow-xl rounded-lg'):
            ui.label("📝 New User Registration").classes("text-3xl mb-6 font-bold text-center text-gray-700")
            
            with ui.input("Choose a username").classes('w-full mb-4') as username:
                username.props('outlined clearable')
                with username.add_slot('prepend'):
                    ui.icon('person_add')

            with ui.input("Choose a password", password=True, password_toggle_button=True).classes('w-full mb-6') as password:
                password.props('outlined clearable')
                with password.add_slot('prepend'):
                    ui.icon('lock')

            with ui.row().classes("w-full justify-center"):
                ui.button("Create Account", on_click=lambda: handle_registration(username.value, password.value)).classes("w-40 bg-green-600 text-white")
                ui.button("Back to Login", on_click=lambda: safe_navigate("/")).classes("w-40")


@ui.page("/dashboard")
def dashboard():
    if not app.storage.user.get("authenticated"):
        safe_navigate("/")
        return

    username = app.storage.user.get("username")

    with ui.header(elevated=True).classes('items-center justify-between bg-blue-600 text-white'):
        ui.label('📖 Book Recommendation Dashboard').classes('text-2xl font-bold')
        ui.button('Logout', on_click=handle_logout, icon='logout').props('flat color=white')

    with ui.column().classes('w-full max-w-5xl mx-auto p-4'):
        if books.empty:
            ui.label("Dataset not loaded. Please check MongoDB connection and data.")
            return

        ui.label(f"Loaded {len(books)} books").classes("text-gray-600 mb-4 text-center")

        async def submit_rating(book_id: str, rating: float):
            """Submits a user rating to the MongoDB database."""
            if rating == 0:
                ui.notify("Please select a rating first.", color="warning")
                return
            try:
                client = MongoClient(MONGO_URI)
                db = client[DB_NAME]
                collection = db[COLLECTION_NAME]
                
                # Remove any existing rating for this user on this book
                collection.update_one(
                    {"_id": ObjectId(book_id)},
                    {"$pull": {"user_ratings": {"username": username}}}
                )
                
                # Add the new rating
                collection.update_one(
                    {"_id": ObjectId(book_id)},
                    {"$push": {"user_ratings": {"username": username, "rating": rating}}}
                )
                
                client.close()
                ui.notify(f"Successfully rated {rating} stars!", color="positive")
            except Exception as e:
                print(f"Error submitting rating: {e}")
                ui.notify("Could not submit rating. Please try again.", color="negative")

        async def toggle_wishlist(book_id: str, button: ui.button):
            """Adds or removes a book from the user's wishlist."""
            try:
                client = MongoClient(MONGO_URI)
                db = client[DB_NAME]
                collection = db[COLLECTION_NAME]
                
                book = collection.find_one({"_id": ObjectId(book_id)})
                is_wishlisted = username in book.get('wishlisted_by', [])

                if is_wishlisted:
                    collection.update_one({"_id": ObjectId(book_id)}, {"$pull": {"wishlisted_by": username}})
                    ui.notify("Removed from your wishlist.", color="info")
                    button.props("icon=bookmark_border color=gray")
                else:
                    collection.update_one({"_id": ObjectId(book_id)}, {"$addToSet": {"wishlisted_by": username}})
                    ui.notify("Added to your wishlist!", color="positive")
                    button.props("icon=bookmark color=green")
                
                client.close()
            except Exception as e:
                print(f"Error updating wishlist: {e}")
                ui.notify("Could not update wishlist. Please try again.", color="negative")

        async def get_open_library_genres(isbn: str, client: httpx.AsyncClient) -> str:
            """Asynchronously fetches book genres from Open Library API with retry logic."""
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
            retries = 3
            delay = .5  # seconds
            for attempt in range(retries):
                try:
                    response = await client.get(url, timeout=10.0)
                    response.raise_for_status()
                    data = response.json()
                    book_data = data.get(f"ISBN:{isbn}", {})
                    subjects = [subject["name"] for subject in book_data.get("subjects", [])]
                    return ", ".join(subjects[:5]) if subjects else "N/A"
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in [502, 503, 504] and attempt < retries - 1:
                        print(f"Service unavailable for Open Library ISBN {isbn}, retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        delay *= .5
                    else:
                        print(f"Error fetching genres for ISBN {isbn} after {retries} retries: {e}")
                        return "N/A"
                except (httpx.RequestError, json.JSONDecodeError) as e:
                    print(f"Error fetching genres for ISBN {isbn}: {e}")
                    return "N/A"
            return "N/A"

        async def get_google_books_description(isbn: str, client: httpx.AsyncClient) -> str:
            """Asynchronously fetches a book description from the Google Books API."""
            url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
            retries = 3
            delay = .5  # seconds
            for attempt in range(retries):
                try:
                    response = await client.get(url, timeout=10.0)
                    response.raise_for_status()
                    data = response.json()
                    if "items" in data and data["items"]:
                        volume_info = data["items"][0].get("volumeInfo", {})
                        return volume_info.get("description", "No description available.")
                    return "No description found on Google Books."
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in [502, 503, 504] and attempt < retries - 1:
                        print(f"Service unavailable for Google Books ISBN {isbn}, retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        delay *= .5
                    else:
                        print(f"Error fetching description from Google Books for ISBN {isbn} after {retries} retries: {e}")
                        return "Could not retrieve description."
                except (httpx.RequestError, json.JSONDecodeError) as e:
                    print(f"Error fetching description from Google Books for ISBN {isbn}: {e}")
                    return "Could not retrieve description."
            return "Could not retrieve description."

        async def update_results(query: str):
            """Clears and repopulates the result area based on the search query."""
            result_area.clear()
            if not query:
                return

            with result_area:
                with ui.row().classes('w-full justify-center p-8'):
                    ui.spinner(size='lg', color='blue')

            search_results_df = books[books.apply(lambda r: query in str(r.get('title', '')).lower() or query in str(r.get('authors', '')).lower(), axis=1)].head(10)
            
            if search_results_df.empty:
                result_area.clear()
                with result_area:
                    ui.label("No matching books found.").classes("text-red-500 text-center w-full")
                return

            # Fetch fresh book data from MongoDB to get latest ratings
            try:
                client = MongoClient(MONGO_URI)
                db = client[DB_NAME]
                collection = db[COLLECTION_NAME]
                book_ids = [ObjectId(id) for id in search_results_df['_id']]
                fresh_books_cursor = collection.find({"_id": {"$in": book_ids}})
                fresh_books_map = {str(book['_id']): book for book in fresh_books_cursor}
                client.close()
            except Exception as e:
                print(f"Error fetching fresh book data: {e}")
                fresh_books_map = {}

            async with httpx.AsyncClient() as client:
                tasks = []
                for _, row in search_results_df.iterrows():
                    isbn = row.get('isbn')
                    if isbn:
                        tasks.append(get_open_library_genres(isbn, client))
                        tasks.append(get_google_books_description(isbn, client))
                
                results = await asyncio.gather(*tasks)

            details_map = {}
            task_index = 0
            for _, row in search_results_df.iterrows():
                isbn = row.get('isbn')
                if isbn:
                    genres = results[task_index]
                    description = results[task_index + 1]
                    details_map[isbn] = (description, genres)
                    task_index += 2

            result_area.clear()
            with result_area:
                for _, row in search_results_df.iterrows():
                    book_id_str = str(row['_id'])
                    fresh_book_data = fresh_books_map.get(book_id_str, row.to_dict())
                    
                    user_rating_info = next((r for r in fresh_book_data.get('user_ratings', []) if r['username'] == username), None)
                    current_user_rating = user_rating_info['rating'] if user_rating_info else 0
                    is_wishlisted = username in fresh_book_data.get('wishlisted_by', [])

                    isbn = fresh_book_data.get('isbn')
                    if isbn and isbn in details_map:
                        with ui.card().classes("w-full mb-4 shadow-md hover:shadow-lg transition"):
                            with ui.row().classes("w-full items-start p-4"):
                                cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false"
                                ui.image(cover_url).classes("w-24 h-36 rounded-sm mr-4").on('error', lambda e, i=isbn: e.sender.set_source(f"https://via.placeholder.com/96x144.png?text=No+Cover"))
                                
                                with ui.column().classes("flex-grow"):
                                    ui.label(f"{fresh_book_data.get('title', 'Untitled')} ({fresh_book_data.get('release_year', 'N/A')})").classes("text-lg font-bold text-gray-800")
                                    ui.label(f"by {fresh_book_data.get('authors', 'Unknown')}").classes("text-md text-gray-600")
                                    ui.label(f"Avg. Rating: {fresh_book_data.get('average_rating', 'N/A')} ⭐").classes("text-sm my-1")
                                    
                                    description, genres = details_map[isbn]
                                    ui.label(f"Genres: {genres}").classes("text-xs text-gray-500 italic")
                                    with ui.expansion("Description", icon="article").classes("w-full mt-2 text-gray-700"):
                                        ui.markdown(description).classes("text-sm p-2 bg-gray-50 rounded")

                                    with ui.row().classes('items-center mt-2'):
                                        ui.label('Your Rating:').classes('mr-2')
                                        rating_input = ui.rating(max=5, value=current_user_rating).props('color=amber')
                                        ui.button('Rate', on_click=lambda _, r=fresh_book_data, ri=rating_input: submit_rating(r['_id'], ri.value))
                                        wishlist_btn = ui.button(icon='bookmark' if is_wishlisted else 'bookmark_border', on_click=None).props('flat round')
                                        wishlist_btn.on('click', lambda _, r=fresh_book_data, b=wishlist_btn: toggle_wishlist(r['_id'], b))
                                        wishlist_btn.props(f"color={'green' if is_wishlisted else 'gray'}")

        def perform_search():
            """Wrapper to call the async update function."""
            asyncio.create_task(update_results(search_box.value.lower()))

        def show_my_ratings():
            """Displays books rated by the current user."""
            result_area.clear()
            with result_area:
                ui.label("Loading your rated books...").classes("text-center w-full")
                try:
                    client = MongoClient(MONGO_URI)
                    db = client[DB_NAME]
                    collection = db[COLLECTION_NAME]
                    
                    # Find books that the current user has rated
                    rated_books_cursor = collection.find({"user_ratings.username": username})
                    rated_books_list = list(rated_books_cursor)
                    client.close()
                    
                    result_area.clear()
                    if not rated_books_list:
                        with result_area:
                            ui.label("You have not rated any books yet.").classes("text-center w-full")
                        return

                    with result_area:
                        ui.label(f"You have rated {len(rated_books_list)} book(s):").classes("text-xl font-bold mb-4")
                        for book in rated_books_list:
                            # Find the specific rating from this user
                            user_rating_info = next((r for r in book.get('user_ratings', []) if r['username'] == username), None)
                            my_rating = user_rating_info['rating'] if user_rating_info else "N/A"

                            with ui.card().classes("w-full mb-4 shadow-md"):
                                with ui.row().classes("w-full items-center p-4"):
                                    isbn = book.get('isbn')
                                    cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false" if isbn else "https://via.placeholder.com/96x144.png?text=No+Cover"
                                    ui.image(cover_url).classes("w-24 h-36 rounded-sm mr-4").on('error', lambda e, i=isbn: e.sender.set_source(f"https://via.placeholder.com/96x144.png?text=No+Cover"))
                                    
                                    with ui.column().classes("flex-grow"):
                                        ui.label(f"{book.get('title', 'Untitled')}").classes("text-lg font-bold")
                                        ui.label(f"by {book.get('authors', 'Unknown')}").classes("text-md")
                                        ui.label(f"Your Rating: {my_rating} ⭐").classes("text-amber-500 font-bold")

                except Exception as e:
                    print(f"Error fetching rated books: {e}")
                    result_area.clear()
                    with result_area:
                        ui.label("Could not fetch your rated books. Please try again.", color="negative")

        async def show_my_wishlist():
            """Displays books on the user's wishlist."""
            result_area.clear()
            with result_area:
                ui.label("Loading your wishlist...").classes("text-center w-full")
                try:
                    client = MongoClient(MONGO_URI)
                    db = client[DB_NAME]
                    collection = db[COLLECTION_NAME]
                    
                    wishlist_cursor = collection.find({"wishlisted_by": username})
                    wishlist = list(wishlist_cursor)
                    client.close()
                    
                    result_area.clear()
                    if not wishlist:
                        with result_area:
                            ui.label("Your wishlist is empty.").classes("text-center w-full")
                        return

                    with result_area:
                        ui.label(f"You have {len(wishlist)} book(s) in your wishlist:").classes("text-xl font-bold mb-4")
                        for book in wishlist:
                            with ui.card().classes("w-full mb-4 shadow-md"):
                                with ui.row().classes("w-full items-center p-4"):
                                    isbn = book.get('isbn')
                                    cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false" if isbn else "https://via.placeholder.com/96x144.png?text=No+Cover"
                                    ui.image(cover_url).classes("w-24 h-36 rounded-sm mr-4").on('error', lambda e, i=isbn: e.sender.set_source(f"https://via.placeholder.com/96x144.png?text=No+Cover"))
                                    
                                    with ui.column().classes("flex-grow"):
                                        ui.label(f"{book.get('title', 'Untitled')}").classes("text-lg font-bold")
                                        ui.label(f"by {book.get('authors', 'Unknown')}").classes("text-md")
                                        ui.label(f"Avg. Rating: {book.get('average_rating', 'N/A')} ⭐").classes("text-sm my-1")
                except Exception as e:
                    print(f"Error fetching wishlist: {e}")
                    result_area.clear()
                    with result_area:
                        ui.label("Could not fetch your wishlist. Please try again.", color="negative")

        async def get_ai_recommendations():
            """Analyzes user ratings and provides personalized book recommendations."""
            result_area.clear()
            with result_area:
                with ui.row().classes('w-full justify-center p-8'):
                    ui.spinner(size='lg', color='blue')

            try:
                client = MongoClient(MONGO_URI)
                db = client[DB_NAME]
                collection = db[COLLECTION_NAME]
                
                # Fetch all books rated or wishlisted by the user
                user_books_cursor = collection.find({
                    "$or": [
                        {"user_ratings.username": username},
                        {"wishlisted_by": username}
                    ]
                })
                user_books_list = list(user_books_cursor)
                
                rated_books_list = [b for b in user_books_list if any(r['username'] == username for r in b.get('user_ratings', []))]
                wishlisted_book_ids = {b['_id'] for b in user_books_list if username in b.get('wishlisted_by', [])}

                if len(rated_books_list) < 3:
                    result_area.clear()
                    with result_area:
                        ui.label("Please rate at least 3 books to get personalized recommendations.").classes("text-center w-full")
                    client.close()
                    return

                # Analyze highly-rated books
                highly_rated_books = []
                for book in rated_books_list:
                    user_rating = next(r['rating'] for r in book.get('user_ratings', []) if r['username'] == username)
                    if user_rating >= 4:
                        highly_rated_books.append(book)

                if not highly_rated_books:
                    result_area.clear()
                    with result_area:
                        ui.label("Rate some books 4 or 5 stars to get recommendations!").classes("text-center w-full")
                    client.close()
                    return

                # Fetch genres for highly-rated books
                async with httpx.AsyncClient() as http_client:
                    genre_tasks = [get_open_library_genres(book['isbn'], http_client) for book in highly_rated_books if book.get('isbn')]
                    genre_results = await asyncio.gather(*genre_tasks)
                
                all_genres = [genre.strip() for genres in genre_results for genre in genres.split(',') if genre.strip() and genre != "N/A"]
                top_genres = [item[0] for item in Counter(all_genres).most_common(3)]
                
                all_authors = [author.strip() for book in highly_rated_books for author in book.get('authors', '').split(',') if author.strip()]
                top_authors = [item[0] for item in Counter(all_authors).most_common(3)]

                # Generate summary
                summary = f"Based on your high ratings, you seem to enjoy books by authors like **{', '.join(top_authors)}**."
                if top_genres:
                    summary += f" You also appear to like genres such as **{', '.join(top_genres)}**."
                
                # Find recommendations, excluding already rated or wishlisted books
                rated_book_ids = {book['_id'] for book in rated_books_list}
                exclude_ids = rated_book_ids.union(wishlisted_book_ids)

                # Fetch recommended books from the full dataset
                recommended_books_df = books[
                    (books['authors'].isin(top_authors)) &
                    (~books['_id'].isin(exclude_ids))
                ].sort_values('average_rating', ascending=False).head(10)

                if len(recommended_books_df) < 10:
                    additional_recs_df = books[
                        (~books['_id'].isin(exclude_ids)) &
                        (~books['_id'].isin(recommended_books_df['_id']))
                    ].sort_values('average_rating', ascending=False).head(10 - len(recommended_books_df))
                    recommended_books_df = pd.concat([recommended_books_df, additional_recs_df])

                result_area.clear()
                with result_area:
                    with ui.card().classes("w-full mb-4 bg-blue-50"):
                        ui.markdown(summary).classes("p-4 text-gray-800")
                    
                    ui.label("Here are some books you might like:").classes("text-xl font-bold my-4")

                    if recommended_books_df.empty:
                        ui.label("No new recommendations found at this time. Try rating more books!").classes("text-center w-full")
                        return

                    for _, book_row in recommended_books_df.iterrows():
                        book = book_row.to_dict()
                        is_wishlisted = book['_id'] in wishlisted_book_ids
                        with ui.card().classes("w-full mb-4 shadow-md"):
                            with ui.row().classes("w-full items-center p-4"):
                                isbn = book.get('isbn')
                                cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false" if isbn else "https://via.placeholder.com/96x144.png?text=No+Cover"
                                ui.image(cover_url).classes("w-24 h-36 rounded-sm mr-4").on('error', lambda e, i=isbn: e.sender.set_source(f"https://via.placeholder.com/96x144.png?text=No+Cover"))
                                
                                with ui.column().classes("flex-grow"):
                                    ui.label(f"{book.get('title', 'Untitled')}").classes("text-lg font-bold")
                                    ui.label(f"by {book.get('authors', 'Unknown')}").classes("text-md")
                                    ui.label(f"Avg. Rating: {book.get('average_rating', 'N/A')} ⭐").classes("text-sm my-1")
                                
                                with ui.row().classes('items-center mt-2'):
                                    wishlist_btn = ui.button(icon='bookmark' if is_wishlisted else 'bookmark_border', on_click=None).props('flat round')
                                    wishlist_btn.on('click', lambda _, r=book, b=wishlist_btn: toggle_wishlist(r['_id'], b))
                                    wishlist_btn.props(f"color={'green' if is_wishlisted else 'gray'}")

            except Exception as e:
                print(f"Error generating AI recommendations: {e}")
                result_area.clear()
                with result_area:
                    ui.label("Could not generate recommendations. Please try again later.", color="negative")

        with ui.row().classes("w-full items-center mb-6"):
            with ui.input(placeholder="Search by title or author...").classes("flex-grow") as search_box:
                search_box.props('outlined rounded')
                with search_box.add_slot('append'):
                    ui.icon('search')
            search_box.on("keydown.enter", perform_search)
            ui.button("Search", on_click=perform_search).classes("h-14")
            ui.button("My Rated Books", on_click=show_my_ratings, icon='star').classes("h-14")
            ui.button("My Wishlist", on_click=show_my_wishlist, icon='bookmark').classes("h-14")
            ui.button("AI Recommendations", on_click=get_ai_recommendations, icon='auto_awesome').classes("h-14 bg-purple-600 text-white")

        result_area = ui.column().classes("w-full")
# ------------------------------------------------


# ---------------- START APP ----------------
ui.run(title="Book Recommendation App", reload=False, host='0.0.0.0', port=8080, native=False, storage_secret="a_very_secret_key_for_storage")
# -------------------------------------------


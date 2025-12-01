from nicegui import ui, app, client
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
from datetime import datetime
import matplotlib
matplotlib.use('Agg')  # Set the backend before importing pyplot
import matplotlib.pyplot as plt

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
    # Load data from the CSV file
    books = pd.read_csv('BooksWithGenres.csv')
    # The CSV might have an unnamed index column if saved with one
    if 'Unnamed: 0' in books.columns:
        books = books.drop('Unnamed: 0', axis=1)
    
    # Rename columns to match existing code expectations
    books = books.rename(columns={'genre': 'genres', '  num_pages': 'num_pages'})
    
    # Create a MongoDB-like '_id' for compatibility with existing functions
    books['_id'] = [str(ObjectId()) for _ in range(len(books))]

    # Extract year from publication_date for display consistency
    if 'publication_date' in books.columns:
        books['release_year'] = pd.to_datetime(books['publication_date'], errors='coerce').dt.year
    else:
        books['release_year'] = 'N/A'

except FileNotFoundError:
    books = pd.DataFrame()
    print("Error: 'BooksWithGenres.csv' not found. Please ensure the file is in the correct directory.")
except Exception as e:
    books = pd.DataFrame()
    print(f"Error loading data from CSV: {e}")
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
        with ui.card().classes('w-96 p-8 shadow-xl rounded-lg border-t-4 border-blue-600'):
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
        with ui.card().classes('w-96 p-8 shadow-xl rounded-lg border-t-4 border-green-600'):
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


def get_all_genres() -> list[str]:
    """Extracts a sorted list of unique genres from the books DataFrame."""
    if 'genres' not in books.columns:
        return []
    
    all_genres = set()
    # The 'genres' column may contain NaN values, which should be ignored.
    # It may also contain strings of comma-separated genres.
    for _, genre_list in books['genres'].dropna().items():
        if isinstance(genre_list, str):
            for genre in genre_list.split(','):
                trimmed_genre = genre.strip()
                if trimmed_genre:
                    all_genres.add(trimmed_genre)
    
    return sorted(list(all_genres))

def format_ratings_count(num):
    """Formats a number into a more readable string (e.g., 1.2M, 3.4K)."""
    if pd.isna(num):
        return "N/A"
    num = float(num)
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(int(num))

async def get_open_library_description(isbn: str, client: httpx.AsyncClient) -> str:
    """Fetches a book description from the Open Library API."""
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        response = await client.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        book_data = data.get(f"ISBN:{isbn}", {})
        description = book_data.get("description")
        if isinstance(description, dict):
            return description.get("value", "No description available.")
        return description or "No description available."
    except (httpx.RequestError, json.JSONDecodeError) as e:
        print(f"Error fetching description from Open Library for ISBN {isbn}: {e}")
        return "No description available."

async def get_book_data(isbn: str, client: httpx.AsyncClient) -> str:
    """Fetches book description, trying Google Books first, then Open Library as a fallback."""
    # --- Google Books API (Primary) ---
    url_google = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    description = "No description available."
    retries = 3
    delay = 0.5  # seconds

    for attempt in range(retries):
        try:
            response = await client.get(url_google, timeout=5.0)
            response.raise_for_status()
            data = response.json()
            if "items" in data and data["items"]:
                volume_info = data["items"][0].get("volumeInfo", {})
                description = volume_info.get("description", "No description available.")
            break  # Success, exit the loop
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [502, 503, 504] and attempt < retries - 1:
                print(f"Service unavailable for Google Books ISBN {isbn}, retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print(f"Error fetching from Google Books for ISBN {isbn} after {retries} retries: {e}")
                break  # Failed after retries, exit loop
        except (httpx.RequestError, json.JSONDecodeError) as e:
            print(f"Error fetching from Google Books for ISBN {isbn}: {e}")
            break # Non-retryable error, exit loop

    # --- Open Library API (Fallback) ---
    if description in ["No description available.", "No description found on Google Books."]:
        description = await get_open_library_description(isbn, client)

    return description

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

@ui.page("/dashboard")
def dashboard():
    if not app.storage.user.get("authenticated"):
        safe_navigate("/")
        return

    username = app.storage.user.get("username")

    with ui.header(elevated=True).classes('items-center justify-between bg-blue-600 text-white'):
        ui.label(f"📖 {username}'s Dashboard").classes('text-2xl font-bold')
        with ui.row().classes('items-center'):
            ui.button('My Analytics', on_click=lambda: safe_navigate('/analytics'), icon='analytics').props('flat color=white')
            ui.button('Logout', on_click=handle_logout, icon='logout').props('flat color=white')

    with ui.column().classes('w-full max-w-7xl mx-auto p-4'):
        if books.empty:
            ui.label("Dataset not loaded. Please check the data source.").classes("text-center text-red-500")
            return

        # --- Helper function to create a book card ---
        def create_book_card(book_data: dict, description: str = "No description available."):
            """Creates a UI card for a single book."""
            user_rating_info = next((r for r in book_data.get('user_ratings', []) if r['username'] == username), None)
            current_user_rating = user_rating_info['rating'] if user_rating_info else 0
            is_wishlisted = username in book_data.get('wishlisted_by', [])
            
            with ui.card().classes("w-full mb-4 shadow-md hover:shadow-lg transition-shadow bg-white border border-gray-200"):
                with ui.row().classes("w-full items-start p-4"):
                    # Book Cover
                    isbn = book_data.get('isbn')
                    open_library_cover = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false"
                    google_books_cover = f"https://books.google.com/books/content?vid=isbn:{isbn}&printsec=frontcover&img=1&zoom=1&source=gbs-api"
                    placeholder_cover = "https://via.placeholder.com/128x192.png?text=No+Cover"

                    # Define error handlers
                    def handle_google_error(e):
                        e.sender.set_source(placeholder_cover)

                    def handle_open_library_error(e):
                        # First, set the new source for the image
                        e.sender.set_source(google_books_cover)
                        # Then, add the new error handler to the same image element
                        e.sender.on('error', handle_google_error)

                    # Create the image with the primary error handler
                    ui.image(open_library_cover) \
                        .classes("w-32 h-48 rounded-sm mr-6 shadow-lg") \
                        .on('error', handle_open_library_error)
                    
                    # Book Details Column
                    with ui.column().classes("flex-grow"):
                        ui.label(f"{book_data.get('title', 'Untitled')} ({book_data.get('release_year', 'N/A')})").classes("text-xl font-bold text-gray-800")
                        ui.label(f"by {book_data.get('authors', 'Unknown')}").classes("text-lg text-gray-600 mb-2")
                        
                        # Metadata grid
                        with ui.grid(columns=2).classes("text-sm text-gray-600 gap-x-4 gap-y-1"):
                            with ui.row().classes('items-center'):
                                ui.icon('star', size='sm').classes('text-amber-500 mr-1')
                                ui.label(f"Avg. Rating: {book_data.get('average_rating', 'N/A')}")
                            with ui.row().classes('items-center'):
                                ui.icon('group', size='sm').classes('text-gray-500 mr-1')
                                ratings_count = format_ratings_count(book_data.get('ratings_count'))
                                ui.label(f"{ratings_count} ratings")
                            with ui.row().classes('items-center'):
                                ui.icon('menu_book', size='sm').classes('text-gray-500 mr-1')
                                ui.label(f"{int(book_data.get('num_pages', 0))} pages")
                            with ui.row().classes('items-center'):
                                ui.icon('business', size='sm').classes('text-gray-500 mr-1')
                                ui.label(f"Publisher: {book_data.get('publisher', 'N/A')}")

                        # Genres and Description
                        ui.label(f"Genres: {book_data.get('genres', 'N/A')}").classes("text-xs italic text-gray-500 mt-2")
                        ui.markdown(description).classes("mt-2 text-sm text-gray-700 max-h-24 overflow-y-auto bg-gray-50 p-2 rounded")

                    # Actions Column
                    with ui.column().classes('items-center justify-center ml-4 gap-y-2'):
                        with ui.row().classes('items-center'):
                            rating_input = ui.rating(max=5, value=current_user_rating).props('color=amber size=1.2rem')
                            ui.button('Rate', on_click=lambda: submit_rating(book_data['_id'], rating_input.value)).classes('ml-2')
                        
                        wishlist_btn = ui.button(icon='bookmark' if is_wishlisted else 'bookmark_border', on_click=None).props('flat round')
                        wishlist_btn.on('click', lambda _, b=wishlist_btn: toggle_wishlist(book_data['_id'], b))
                        wishlist_btn.props(f"color={'green' if is_wishlisted else 'gray'}")

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
                
                # Add the new rating with a timestamp
                collection.update_one(
                    {"_id": ObjectId(book_id)},
                    {"$push": {"user_ratings": {"username": username, "rating": rating, "rated_at": datetime.utcnow()}}}
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

        async def update_results(query: str = "", genres: list = None, initial_load: bool = False):
            """Clears and repopulates the result area based on search, genres, or initial load."""
            result_area.clear()
            genres = genres or []

            with result_area:
                with ui.row().classes('w-full justify-center p-8'):
                    ui.spinner(size='lg', color='blue')

            search_base = books.copy()

            if initial_load:
                # Ensure ratings_count is numeric before filtering
                search_base['ratings_count'] = pd.to_numeric(search_base['ratings_count'], errors='coerce')
                # Filter for books with at least 50,000 ratings and sort by average_rating
                search_base = search_base[search_base['ratings_count'] >= 50000].sort_values('average_rating', ascending=False)
            else:
                if genres:
                    pattern = '|'.join(genres)
                    search_base = search_base[search_base['genres'].str.contains(pattern, case=False, na=False)]
                if query:
                    search_base = search_base[search_base.apply(lambda r: query in str(r.get('title', '')).lower() or query in str(r.get('authors', '')).lower(), axis=1)]

            search_results_df = search_base.head(10)
            
            if search_results_df.empty:
                result_area.clear()
                with result_area:
                    ui.label("No matching books found.").classes("text-red-500 text-center w-full")
                return

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
                tasks = [get_book_data(row.get('isbn'), client) for _, row in search_results_df.iterrows()]
                descriptions = await asyncio.gather(*tasks)

            result_area.clear()
            with result_area:
                if initial_load:
                    ui.label(f"Welcome, {username}! Here are some of the top-rated books to get you started:").classes("text-2xl font-bold mb-4 text-gray-700")

                for (idx, row), desc in zip(search_results_df.iterrows(), descriptions):
                    book_id_str = str(row['_id'])
                    # Combine data from CSV and MongoDB for the most complete view
                    combined_data = {**row.to_dict(), **fresh_books_map.get(book_id_str, {})}
                    create_book_card(combined_data, desc)

        def perform_search():
            """Wrapper to call the async update function."""
            asyncio.create_task(update_results(query=search_box.value.lower(), genres=genre_filter.value))

        def show_my_ratings():
            """Displays books rated by the current user."""
            result_area.clear()
            with result_area:
                ui.label("Loading your rated books...").classes("text-center w-full")
                try:
                    client = MongoClient(MONGO_URI)
                    db = client[DB_NAME]
                    collection = db[COLLECTION_NAME]
                    
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
                            create_book_card(book)

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
                            create_book_card(book)
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
                
                user_books_cursor = collection.find({"$or": [{"user_ratings.username": username}, {"wishlisted_by": username}]})
                user_books_list = list(user_books_cursor)
                
                rated_books_list = [b for b in user_books_list if any(r['username'] == username for r in b.get('user_ratings', []))]
                wishlisted_book_ids = {b['_id'] for b in user_books_list if username in b.get('wishlisted_by', [])}

                if len(rated_books_list) < 3:
                    result_area.clear()
                    with result_area:
                        ui.label("Please rate at least 3 books to get personalized recommendations.").classes("text-center w-full")
                    client.close()
                    return

                highly_rated_books = [b for b in rated_books_list if next(r['rating'] for r in b.get('user_ratings', []) if r['username'] == username) >= 4]

                if not highly_rated_books:
                    result_area.clear()
                    with result_area:
                        ui.label("Rate some books 4 or 5 stars to get recommendations!").classes("text-center w-full")
                    client.close()
                    return

                async with httpx.AsyncClient() as http_client:
                    genre_tasks = [get_open_library_genres(book['isbn'], http_client) for book in highly_rated_books if book.get('isbn')]
                    genre_results = await asyncio.gather(*genre_tasks)
                
                all_genres = [genre.strip() for genres in genre_results for genre in genres.split(',') if genre.strip() and genre != "N/A"]
                top_genres = [item[0] for item in Counter(all_genres).most_common(3)]
                
                all_authors = [author.strip() for book in highly_rated_books for author in book.get('authors', '').split(',') if author.strip()]
                top_authors = [item[0] for item in Counter(all_authors).most_common(3)]

                summary = f"Based on your high ratings, you seem to enjoy books by authors like **{', '.join(top_authors)}**."
                if top_genres:
                    summary += f" You also appear to like genres such as **{', '.join(top_genres)}**."
                
                rated_book_ids = {book['_id'] for book in rated_books_list}
                exclude_ids = rated_book_ids.union(wishlisted_book_ids)

                recommended_books_df = books[
                    (books['authors'].isin(top_authors)) &
                    (~books['_id'].isin([str(oid) for oid in exclude_ids]))
                ].sort_values('average_rating', ascending=False).head(10)

                if len(recommended_books_df) < 10:
                    additional_recs_df = books[
                        (~books['_id'].isin([str(oid) for oid in exclude_ids])) &
                        (~books['_id'].isin(recommended_books_df['_id']))
                    ].sort_values('average_rating', ascending=False).head(10 - len(recommended_books_df))
                    recommended_books_df = pd.concat([recommended_books_df, additional_recs_df])

                result_area.clear()
                with result_area:
                    with ui.card().classes("w-full mb-4 bg-blue-50"):
                        ui.markdown(summary).classes("p-4 text-gray-800")
                    
                    ui.label("Here are some books you might like:").classes("text-xl font-bold my-4")

                    if recommended_books_df.empty:
                        ui.label("No new recommendations found. Try rating more books!").classes("text-center w-full")
                        return

                    for _, book_row in recommended_books_df.iterrows():
                        create_book_card(book_row.to_dict())

            except Exception as e:
                print(f"Error generating AI recommendations: {e}")
                result_area.clear()
                with result_area:
                    ui.label("Could not generate recommendations. Please try again later.", color="negative")

        # --- Control Panel ---
        with ui.card().classes("w-full mb-6"):
            with ui.row().classes("w-full items-center p-4 gap-4"):
                with ui.input(placeholder="Search by title or author...").classes("flex-grow") as search_box:
                    search_box.props('outlined rounded')
                    with search_box.add_slot('append'):
                        ui.icon('search').on('click', perform_search)
                
                genre_options = get_all_genres()
                with ui.select(options=genre_options, label="Filter by Genre", multiple=True).classes("w-72").props('outlined rounded clearable') as genre_filter:
                    pass

                search_box.on("keydown.enter", perform_search)
                genre_filter.on("change", perform_search)

            with ui.row().classes("w-full justify-start p-4 pt-0 gap-2"):
                ui.button("My Rated Books", on_click=show_my_ratings, icon='star').props('outline')
                ui.button("My Wishlist", on_click=show_my_wishlist, icon='bookmark').props('outline')
                ui.button("AI Recommendations", on_click=get_ai_recommendations, icon='auto_awesome').classes("bg-purple-600 text-white")

        result_area = ui.column().classes("w-full")
        
        # Initial load of top-rated books
        asyncio.create_task(update_results(initial_load=True))

def create_rating_distribution_chart(chart_data: list):
    """Creates a styled bar chart for rating distribution using Matplotlib."""
    fig, ax = plt.subplots()
    fig.patch.set_alpha(0.0)  # Transparent figure background
    ax.patch.set_alpha(0.0)   # Transparent axes background

    bars = ax.bar(['1', '2', '3', '4', '5'], chart_data, color='#60A5FA') # A lighter blue

    # Add data labels on top of each bar
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.1, int(yval), ha='center', va='bottom', color='#4B5563')

    ax.set_ylabel('Number of Books', color='#4B5563')
    ax.set_xlabel('Star Rating', color='#4B5563')
    
    # Customize spines and ticks for a cleaner look
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#D1D5DB')
    ax.spines['bottom'].set_color('#D1D5DB')
    ax.tick_params(axis='x', colors='#4B5563')
    ax.tick_params(axis='y', colors='#4B5563')
    
    plt.tight_layout()

@ui.page("/analytics")
def analytics_page():
    if not app.storage.user.get("authenticated"):
        safe_navigate("/")
        return

    username = app.storage.user.get("username")

    with ui.header(elevated=True).classes('items-center justify-between bg-blue-600 text-white'):
        ui.label(f"📊 {username}'s Reading Analytics").classes('text-2xl font-bold')
        with ui.row().classes('items-center'):
            ui.button('Dashboard', on_click=lambda: safe_navigate('/dashboard'), icon='dashboard').props('flat color=white')
            ui.button('Logout', on_click=handle_logout, icon='logout').props('flat color=white')

    content = ui.column().classes('w-full max-w-7xl mx-auto p-4')

    async def build_analytics_ui():
        """Fetches data and builds the analytics UI, handling client disconnections."""
        # This check is crucial. It ensures that we don't try to update a disconnected client.
        # The 'client' attribute is None if the user has navigated away.
        if not content.client.id:
            print("Analytics UI build aborted: Client has disconnected.")
            return
            
        try:
            with content:
                content.clear()
                ui.label("Loading your analytics...").classes("text-center w-full")
            
            # --- Data Fetching (Optimized) ---
            client_mongo = MongoClient(MONGO_URI)
            db = client_mongo[DB_NAME]
            collection = db[COLLECTION_NAME]
            
            # Fetch only the books rated by the user
            rated_books_list = list(collection.find({"user_ratings.username": username}))
            
            # Fetch the average rating from all books using an aggregation pipeline for efficiency
            pipeline = [{"$group": {"_id": None, "avg_rating": {"$avg": "$average_rating"}}}]
            community_avg_result = list(collection.aggregate(pipeline))
            community_average = community_avg_result[0]['avg_rating'] if community_avg_result and community_avg_result[0]['avg_rating'] is not None else 0
            
            client_mongo.close()

            # Check again after the long operation, before building the main UI
            if not content.client.id:
                print("Analytics UI build aborted: Client disconnected after data fetch.")
                return

            if not rated_books_list:
                with content:
                    content.clear()
                    ui.label("You haven't rated any books yet. Rate some books to see your analytics!").classes("text-center w-full text-xl mt-8")
                return

            # --- Data Processing ---
            user_ratings = []
            genre_tasks = []
            books_to_process = []
            
            async with httpx.AsyncClient() as http_client:
                for book in rated_books_list:
                    rating_info = next((r for r in book.get('user_ratings', []) if r['username'] == username), None)
                    if rating_info:
                        books_to_process.append((book, rating_info))
                        # Only create a task if there is an ISBN
                        if isbn := book.get('isbn'):
                            genre_tasks.append(get_open_library_genres(isbn, http_client))
                        else:
                            # If no ISBN, append a completed future with a default value
                            genre_tasks.append(asyncio.create_task(asyncio.sleep(0, result="N/A")))
                
                genre_results = await asyncio.gather(*genre_tasks)

            # Check one more time before the final render
            if not content.client.id:
                print("Analytics UI build aborted: Client disconnected during data processing.")
                return

            for (book, rating_info), genres in zip(books_to_process, genre_results):
                user_ratings.append({
                    "title": book.get('title', 'Untitled'),
                    "authors": book.get('authors', 'Unknown'),
                    "genres": genres,
                    "rating": rating_info.get('rating'),
                    "average_rating": pd.to_numeric(book.get('average_rating'), errors='coerce')
                })

            valid_ratings = [r['rating'] for r in user_ratings if r['rating'] is not None]
            total_ratings = len(valid_ratings)
            my_average_rating = sum(valid_ratings) / total_ratings if total_ratings > 0 else 0
            
            rater_type = "Generous Rater" if my_average_rating > community_average + 0.5 else "Critical Rater" if my_average_rating < community_average - 0.5 else "Right in the Middle"

            rating_counts = Counter(int(r) for r in valid_ratings)
            chart_data = [rating_counts.get(i, 0) for i in range(1, 6)]

            top_books = sorted([r for r in user_ratings if r['rating'] == 5], key=lambda x: x.get('average_rating', 0), reverse=True)[:5]
            bottom_books = sorted([r for r in user_ratings if r['rating'] is not None and r['rating'] <= 2], key=lambda x: x.get('average_rating', 0))[:5]

            all_genres = [genre.strip() for r in user_ratings for genre in r.get('genres', '').split(',') if genre.strip() and genre != "N/A"]
            top_genres = Counter(all_genres).most_common(5)
            
            all_authors = [author.strip() for r in user_ratings for author in r.get('authors', '').split(',') if author.strip()]
            top_authors = Counter(all_authors).most_common(5)

            # --- UI Rendering ---
            # Final check before rendering the entire UI block
            if not content.client.id:
                print("Analytics UI build aborted: Client disconnected just before final render.")
                return

            with content:
                content.clear() # Clear loading message
                # --- Summary Cards ---
                with ui.grid(columns=3).classes("w-full justify-around mb-6 gap-4"):
                    with ui.card().classes("items-center p-4"):
                        with ui.row().classes('items-center no-wrap'):
                            ui.icon('library_books', size='lg').classes('text-gray-400 mr-4')
                            with ui.column().classes('gap-0'):
                                ui.label("Total Books Rated").classes("text-sm text-gray-500")
                                ui.label(f"{len(user_ratings)}").classes("text-4xl font-bold")
                    with ui.card().classes("items-center p-4"):
                        with ui.row().classes('items-center no-wrap'):
                            ui.icon('star_half', size='lg').classes('text-amber-400 mr-4')
                            with ui.column().classes('gap-0'):
                                ui.label("Your Average Rating").classes("text-sm text-gray-500")
                                ui.label(f"{my_average_rating:.2f}").classes("text-4xl font-bold")
                    with ui.card().classes("items-center p-4"):
                        with ui.row().classes('items-center no-wrap'):
                            ui.icon('psychology', size='lg').classes('text-blue-400 mr-4')
                            with ui.column().classes('gap-0'):
                                ui.label("You Are A...").classes("text-sm text-gray-500")
                                ui.label(rater_type).classes("text-2xl font-bold text-blue-600")

                # --- Main Grid ---
                with ui.grid(columns=3).classes("w-full gap-6"):
                    # --- Column 1: Rating Distribution ---
                    with ui.card().classes("w-full col-span-3 lg:col-span-1"):
                        ui.label("Rating Distribution").classes("text-xl font-bold p-4")
                        with ui.pyplot(close=True).classes('w-full h-64'):
                            create_rating_distribution_chart(chart_data)
                    
                    # --- Column 2: Reading Habits ---
                    with ui.column().classes("w-full col-span-3 lg:col-span-1 gap-6"):
                        with ui.card().classes("w-full"):
                            ui.label("Your Top Genres").classes("text-xl font-bold p-4")
                            if top_genres:
                                with ui.list().classes("w-full"):
                                    for genre, count in top_genres:
                                        with ui.item():
                                            with ui.item_section().props('side').classes('text-gray-500'):
                                                ui.icon('theater_comedy')
                                            ui.item_section(f"{genre}")
                                            ui.item_section(f"{count}").props("side")
                            else:
                                ui.label("No genre data found.").classes("p-4")
                        
                        with ui.card().classes("w-full"):
                            ui.label("Your Top Authors").classes("text-xl font-bold p-4")
                            if top_authors:
                                with ui.list().classes("w-full"):
                                    for author, count in top_authors:
                                        with ui.item():
                                            with ui.item_section().props('side').classes('text-gray-500'):
                                                ui.icon('edit')
                                            ui.item_section(f"{author}")
                                            ui.item_section(f"{count}").props("side")
                            else:
                                ui.label("No author data found.").classes("p-4")

                    # --- Column 3: Book Lists ---
                    with ui.column().classes("w-full col-span-3 lg:col-span-1 gap-6"):
                        with ui.card().classes("w-full"):
                            ui.label("Your 5-Star Books").classes("text-xl font-bold p-4 text-green-600")
                            if top_books:
                                with ui.list().classes("w-full"):
                                    for book in top_books:
                                        with ui.item():
                                            with ui.item_section().props('side').classes('text-amber-500'):
                                                ui.icon('emoji_events')
                                            ui.item_section(f"{book['title']}")
                            else:
                                ui.label("No 5-star ratings yet!").classes("p-4")

                        with ui.card().classes("w-full"):
                            ui.label("Your Lowest-Rated Books").classes("text-xl font-bold p-4 text-red-600")
                            if bottom_books:
                                with ui.list().classes("w-full"):
                                    for book in bottom_books:
                                        with ui.item():
                                            with ui.item_section().props('side').classes('text-gray-500'):
                                                ui.icon('thumb_down')
                                            ui.item_section(f"{book['title']}")
                                            ui.item_section(f"{book['rating']} ⭐").props("side")
                            else:
                                ui.label("No low ratings yet!").classes("p-4")

        except Exception as e:
            print(f"Error building analytics UI: {e}")
            # Check connection again before trying to show an error message
            if content.client.id:
                with content:
                    content.clear()
                    ui.label("Could not load your analytics. Please try again later.").classes("text-negative")
            else:
                print(f"Error building analytics UI for disconnected client: {e}")

    ui.timer(0.1, build_analytics_ui, once=True)
# ------------------------------------------------


# ---------------- START APP ----------------
ui.run(title="Book Recommendation App", reload=False, host='0.0.0.0', port=8080, native=False, storage_secret="a_very_secret_key_for_storage")
# -------------------------------------------

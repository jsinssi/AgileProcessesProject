from nicegui import ui
import pandas as pd
import hashlib
import os
import base64
from pymongo import MongoClient
import requests
import json
import asyncio
import httpx

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
        ui.notify(f"Welcome, {username}")
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
# ---------------------------------------------


# ---------------- GUI PAGES ----------------
@ui.page("/")
def login_page():
    with ui.column().classes("absolute-center items-center"):
        ui.label("📚 Book Recommendation Login").classes("text-2xl mb-4 font-bold")
        username = ui.input("Username").classes("w-64")
        password = ui.input("Password", password=True).classes("w-64")

        with ui.row():
            ui.button("Login", on_click=lambda: handle_login(username.value, password.value)).classes("bg-blue-600 text-white")
            ui.button("Register", on_click=lambda: safe_navigate("/register")).classes("bg-gray-600 text-white")
# ---------------------------------------------

@ui.page("/register")
def register_page():
    with ui.column().classes("absolute-center items-center"):
        ui.label("📝 New User Registration").classes("text-2xl mb-4 font-bold")
        username = ui.input("Choose a username").classes("w-64")
        password = ui.input("Choose a password", password=True).classes("w-64")

        with ui.row():
            ui.button("Create Account", on_click=lambda: handle_registration(username.value, password.value)).classes("bg-green-600 text-white")
            ui.button("Back to Login", on_click=lambda: safe_navigate("/")).classes("bg-gray-400 text-white")


@ui.page("/dashboard")
def dashboard():
    ui.label("📖 Book Recommendation Dashboard").classes("text-2xl mb-4 font-bold")
    
    if books.empty:
        ui.label("Dataset not loaded. Please check MongoDB connection and data.")
        return

    ui.label(f"Loaded {len(books)} books").classes("text-gray-600 mb-4")

    async def get_open_library_genres(isbn: str, client: httpx.AsyncClient) -> str:
        """Asynchronously fetches book genres from Open Library API with retry logic."""
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        retries = 3
        delay = 2  # seconds
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
                    delay *= 2
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
        delay = 2  # seconds
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
                    delay *= 2
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

        filtered = books[books.apply(lambda r: query in str(r.get('title', '')).lower() or query in str(r.get('authors', '')).lower(), axis=1)].head(10)
        
        with result_area:
            if filtered.empty:
                ui.label("No matching books found.").classes("text-red-500")
                return

            async with httpx.AsyncClient() as client:
                tasks = []
                for _, row in filtered.iterrows():
                    isbn = row.get('isbn')
                    if isbn:
                        tasks.append(get_open_library_genres(isbn, client))
                        tasks.append(get_google_books_description(isbn, client))
                
                results = await asyncio.gather(*tasks)

            details_map = {}
            task_index = 0
            for _, row in filtered.iterrows():
                isbn = row.get('isbn')
                if isbn:
                    genres = results[task_index]
                    description = results[task_index + 1]
                    if genres and genres != "N/A":
                        details_map[isbn] = (description, genres)
                    task_index += 2

            for _, row in filtered.iterrows():
                isbn = row.get('isbn')
                if isbn and isbn in details_map:
                    with ui.card().classes("p-3 mb-2 w-full max-w-2xl"):
                        with ui.row().classes("w-full items-center no-wrap"):
                            with ui.column().classes("flex-grow"):
                                ui.label(f"📘 {row.get('title', 'Untitled')} ({row.get('release_year', 'N/A')})").classes("font-semibold")
                                ui.label(f"Author: {row.get('authors', 'Unknown')}")
                                ui.label(f"Rating: {row.get('average_rating', 'N/A')} ⭐")
                                
                                description, genres = details_map[isbn]
                                ui.label(f"Genres: {genres}").classes("text-sm text-gray-500")
                                with ui.expansion("Description", icon="article").classes("w-full"):
                                    ui.label(description).classes("text-sm")
                            
                            if isbn:
                                cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
                                ui.image(cover_url).classes("w-20 h-auto ml-4").props('fit=contain')

    search_box = ui.input(
        "Search by title or author", 
        on_change=lambda e: update_results(e.value.lower())
    ).props('debounce=500') # Add this line
    result_area = ui.column().classes("mt-4")
# ------------------------------------------------


# ---------------- START APP ----------------
ui.run(title="Book Recommendation App", reload=False)
# -------------------------------------------


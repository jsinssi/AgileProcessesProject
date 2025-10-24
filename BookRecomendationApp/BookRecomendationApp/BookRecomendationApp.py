from nicegui import ui
import pandas as pd
import hashlib
import os
import base64

# ---------------- CONFIG ----------------
ITERATIONS = 100_000
SALT_SIZE = 16
DATA_PATH = r'BookRecomendationApp\books.csv'  # make sure the dataset is in the same folder
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
    books = pd.read_csv(DATA_PATH)
except Exception as e:
    books = pd.DataFrame()
    print(f"Error loading dataset: {e}")
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
        ui.label("Dataset not loaded. Please check 'books.csv'.")
        return

    ui.label(f"Loaded {len(books)} books").classes("text-gray-600")

    search_box = ui.input("Search by title or author").classes("w-80")
    result_area = ui.column().classes("mt-4")

    def search_books():
        query = (search_box.value or "").lower()
        # safe access to columns to avoid KeyError if missing
        filtered = books[books.apply(lambda r: query in str(r.get('title', '')).lower() or query in str(r.get('author', '')).lower(), axis=1)]
        result_area.clear()
        if filtered.empty:
            with result_area:
                ui.label("No matching books found.").classes("text-red-500")
            return
        for _, row in filtered.head(10).iterrows():
            with result_area:
                with ui.card().classes("p-3 mb-2 w-96"):
                    ui.label(f"📘 {row.get('title', 'Untitled')} ({row.get('release_year', 'N/A')})").classes("font-semibold")
                    ui.label(f"Author: {row.get('author', 'Unknown')}")
                    ui.label(f"Genre: {row.get('genre', 'Unknown')}")
                    ui.label(f"Rating: {row.get('average_rating', 'N/A')} ⭐")

    ui.button("Search", on_click=search_books).classes("mt-2 bg-green-600 text-white")
# ------------------------------------------------


# ---------------- START APP ----------------
ui.run(title="Book Recommendation App", reload=False)
# -------------------------------------------


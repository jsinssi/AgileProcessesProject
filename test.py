import pytest 
from unittest.mock import patch, MagicMock
import pandas as pd

# Import functions from app file
from BookRecomendationApp.BookRecomendationApp.BookRecomendationApp import(
    hash_password,
    verify_password,
    safe_navigate,
    handle_login,
    handle_registration,
    users
)

# ----------------------------------------
# PASSWORD HASHING TESTING
# ----------------------------------------
def test_hash_and_verify_password():
    pwd = "mypassword123"
    hashed = hash_password(pwd)

    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrongpass", hashed) is False


# ----------------------------------------
# LOGIN LOGIC TESTING
# ----------------------------------------
@patch("BookRecomendationApp.BookRecomendationApp.BookRecomendationApp.ui")
def test_login_success(mock_ui):
    users["Bilbo"] = hash_password("baggins1")

    handle_login("Bilbo", "baggins1")

    mock_ui.notify.assert_called_with("Welcome, Bilbo")
    mock_ui.navigate.to.assert_called_with("/dashboard")


@patch("BookRecomendationApp.BookRecomendationApp.BookRecomendationApp.ui")
def test_login_failure(mock_ui):
    handle_login("unknown", "wrong")

    mock_ui.notify.assert_called_with("Invalid username or password", color="negative")


# ----------------------------------------
# REGISTRATION TESTING
# ----------------------------------------
@patch("BookRecomendationApp.BookRecomendationApp.BookRecomendationApp.ui")
def test_registration_success(mock_ui):
    username = "harry_potter"
    if username in users:
        users.pop(username)

    handle_registration(username, "Griffindor2")

    assert username in users
    mock_ui.notify.assert_called()
    mock_ui.navigate.to.assert_called_with("/")


@patch("BookRecomendationApp.BookRecomendationApp.BookRecomendationApp.ui")
def test_registration_existing_user(mock_ui):
    users["existing_user"] = hash_password("111")

    handle_registration("existing_user", "newpass")

    mock_ui.notify.assert_called_with("This Username already exists. Please try again!", color="negative")


@patch("BookRecomendationApp.BookRecomendationApp.BookRecomendationApp.ui")
def test_registration_empty_fields(mock_ui):
    handle_registration("", "")
    mock_ui.notify.assert_called_with("Username and password cannot be empty. Please make sure all elements are filled in!", color="negative")


# ----------------------------------------
# TEST safe_navigate() function
# ----------------------------------------
@patch("BookRecomendationApp.BookRecomendationApp.BookRecomendationApp.ui")
def test_safe_navigate(mock_ui):
    mock_ui.navigate.to = MagicMock()

    safe_navigate("/dashboard")
    mock_ui.navigate.to.assert_called_with("/dashboard")


# ----------------------------------------
# SEARCH LOGIC TEST 
# ----------------------------------------
def test_book_search_logic():
    """Test filtering logic without the GUI."""

    df = pd.DataFrame([
        {"title": "The Hobbit", "author": "Tolkien"},
        {"title": "Dune", "author": "Herbert"},
        {"title": "1984", "author": "Orwell"},
    ])

    query = "dune"
    filtered = df[df.apply(
        lambda r: query in r["title"].lower() or query in r["author"].lower(), axis=1
    )]

    assert len(filtered) == 1
    assert filtered.iloc[0]["title"] == "Dune"

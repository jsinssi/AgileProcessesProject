import hashlib
import os
import base64

# You can adjust these if needed
ITERATIONS = 100_000
SALT_SIZE = 16  # bytes


def hash_password(password: str) -> str:
    """
    Hash a password with a random salt using PBKDF2-HMAC (SHA-256).
    Returns a base64-encoded string containing salt + hash.
    """
    salt = os.urandom(SALT_SIZE)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    # Store both salt and hash together
    return base64.b64encode(salt + key).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against the stored PBKDF2 hash.
    """
    # Decode from base64
    decoded = base64.b64decode(stored_hash.encode("utf-8"))
    salt = decoded[:SALT_SIZE]
    key = decoded[SALT_SIZE:]
    new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return new_key == key
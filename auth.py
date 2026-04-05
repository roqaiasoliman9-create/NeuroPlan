import hashlib
from typing import Optional
from models import User
from storage import find_user_by_email


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def authenticate_user(email: str, password: str) -> Optional[User]:
    user = find_user_by_email(email)
    if not user:
        return None
    if verify_password(password, user.password_hash):
        return user
    return None
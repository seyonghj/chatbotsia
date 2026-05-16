"""
auth_client.py
Simple username + hashed-password authentication stored in Firestore.
No Firebase Auth SDK required — just the Firestore REST API via firebase_client.
"""

import hashlib
import hmac
import os
import streamlit as st
from firebase_client import db  # reuse the same Firestore client


# ── helpers ───────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """SHA-256 hash of the password with a fixed app-level salt."""
    salt = os.environ.get("PASSWORD_SALT") or st.secrets.get("PASSWORD_SALT", "swiftiebot-salt-2024")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


# ── public API ────────────────────────────────────────────────────────────────

def register_user(username: str, password: str, display_name: str = "") -> dict:
    """
    Create a new user document in Firestore.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}.
    """
    username = username.strip().lower()
    if not username or not password:
        return {"success": False, "error": "Username and password are required."}
    if len(username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters."}
    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    user_ref = db.collection("users").document(username)
    if user_ref.get().exists:
        return {"success": False, "error": "Username already taken. Choose another."}

    user_data = {
        "username": username,
        "display_name": display_name.strip() or username,
        "password_hash": _hash_password(password),
        "is_admin": False,
        "created_at": _now_iso(),
    }
    user_ref.set(user_data)
    return {"success": True, "user": {k: v for k, v in user_data.items() if k != "password_hash"}}


def login_user(username: str, password: str) -> dict:
    """
    Verify credentials.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}.
    """
    username = username.strip().lower()
    user_ref = db.collection("users").document(username)
    doc = user_ref.get()
    if not doc.exists:
        return {"success": False, "error": "Username not found."}

    data = doc.to_dict()
    if not hmac.compare_digest(data.get("password_hash", ""), _hash_password(password)):
        return {"success": False, "error": "Incorrect password."}

    return {
        "success": True,
        "user": {
            "username": data["username"],
            "display_name": data.get("display_name", username),
            "is_admin": data.get("is_admin", False),
        },
    }


def get_user(username: str) -> dict | None:
    """Return public user dict or None."""
    doc = db.collection("users").document(username.lower()).get()
    if not doc.exists:
        return None
    d = doc.to_dict()
    return {
        "username": d["username"],
        "display_name": d.get("display_name", d["username"]),
        "is_admin": d.get("is_admin", False),
    }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
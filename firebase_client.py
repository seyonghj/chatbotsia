"""
firebase_client.py
Firebase Firestore backend for SwiftieBot.
Handles users, sessions, messages, searches, and community facts.
"""

import hashlib
import re
import uuid
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore


# ── Firebase init ─────────────────────────────────────────────────────────────
def _init_firebase():
    if firebase_admin._apps:
        return
    try:
        # Local dev: key file on disk
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
    except Exception:
        # Production: Streamlit secrets
        import json
        import streamlit as st
        key_dict = json.loads(st.secrets["FIREBASE_KEY_JSON"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)


_init_firebase()
db = firestore.client()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _is_valid_username(username: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_]{3,30}$", username))


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

def register_user(username: str, password: str, display_name: str = "") -> dict:
    """
    Register a new user.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}.
    """
    username = username.strip().lower()

    if not _is_valid_username(username):
        return {"success": False, "error": "Username must be 3-30 alphanumeric characters or underscores."}
    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    user_ref = db.collection("users").document(username)
    if user_ref.get().exists:
        return {"success": False, "error": "Username already taken. Please choose another."}

    display = display_name.strip() or username
    user_doc = {
        "username":      username,
        "display_name":  display,
        "password_hash": _hash_password(password),
        "is_admin":      False,
        "created_at":    _now(),
    }
    user_ref.set(user_doc)

    return {
        "success": True,
        "user": {
            "username":     username,
            "display_name": display,
            "is_admin":     False,
        },
    }


def login_user(username: str, password: str) -> dict:
    """
    Authenticate a user.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}.
    """
    username = username.strip().lower()
    user_ref = db.collection("users").document(username)
    doc = user_ref.get()

    if not doc.exists:
        return {"success": False, "error": "No account found with that username."}

    data = doc.to_dict()
    if data.get("password_hash") != _hash_password(password):
        return {"success": False, "error": "Incorrect password."}

    return {
        "success": True,
        "user": {
            "username":     data["username"],
            "display_name": data.get("display_name", username),
            "is_admin":     data.get("is_admin", False),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# SESSIONS
# ══════════════════════════════════════════════════════════════════════════════

def create_session(username: str, session_id: str) -> None:
    """Create a new chat session document."""
    db.collection("users").document(username) \
      .collection("sessions").document(session_id) \
      .set({
          "session_id":    session_id,
          "created_at":    _now(),
          "last_updated":  _now(),
          "message_count": 0,
      })


def get_user_sessions(username: str) -> list:
    """Return all sessions for a user, newest first."""
    docs = (
        db.collection("users").document(username)
          .collection("sessions")
          .order_by("last_updated", direction=firestore.Query.DESCENDING)
          .limit(50)
          .stream()
    )
    return [d.to_dict() for d in docs]


def get_user_session_history(username: str, session_id: str) -> list:
    """Return all messages for a specific session."""
    return load_messages(username, session_id)


def delete_user_session(username: str, session_id: str) -> None:
    """Delete a session and all its messages."""
    sess_ref = (
        db.collection("users").document(username)
          .collection("sessions").document(session_id)
    )
    for m in sess_ref.collection("messages").stream():
        m.reference.delete()
    sess_ref.delete()


def _update_session_meta(username: str, session_id: str) -> None:
    """Increment message count and update timestamp."""
    (
        db.collection("users").document(username)
          .collection("sessions").document(session_id)
          .set(
              {
                  "last_updated":  _now(),
                  "message_count": firestore.Increment(1),
              },
              merge=True,
          )
    )


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGES
# ══════════════════════════════════════════════════════════════════════════════

def save_message(username: str, session_id: str, role: str, content: str) -> None:
    """Append a message to a session."""
    (
        db.collection("users").document(username)
          .collection("sessions").document(session_id)
          .collection("messages").document()
          .set({
              "role":       role,
              "content":    content,
              "created_at": _now(),
          })
    )
    _update_session_meta(username, session_id)


def load_messages(username: str, session_id: str) -> list:
    """Load all messages for a session, ordered by time."""
    docs = (
        db.collection("users").document(username)
          .collection("sessions").document(session_id)
          .collection("messages")
          .order_by("created_at")
          .stream()
    )
    return [
        {"role": d.to_dict()["role"], "content": d.to_dict()["content"]}
        for d in docs
    ]


# ══════════════════════════════════════════════════════════════════════════════
# SONG SEARCHES  (DB-first logic)
# ══════════════════════════════════════════════════════════════════════════════

def save_search(
    username: str,
    session_id: str,
    query: str,
    album_filter,
    result: dict,
) -> None:
    """
    Persist a song-search result in two places:
    1. Per-user session log  (users/{u}/sessions/{s}/searches/{auto})
    2. Global search cache   (song_searches/{normalised_key})
       so ANY future user benefits from a prior AI lookup.
    """
    query_lower = query.strip().lower()

    payload = {
        "query":        query,
        "query_lower":  query_lower,
        "album_filter": album_filter or "",
        "result":       result,
        "searched_at":  _now(),
        "username":     username,
        "session_id":   session_id,
    }

    # 1. User-scoped log
    (
        db.collection("users").document(username)
          .collection("sessions").document(session_id)
          .collection("searches").document()
          .set(payload)
    )

    # 2. Global cache keyed by normalised query (+ album if given)
    cache_key = query_lower
    if album_filter:
        cache_key += "__" + album_filter.lower().replace(" ", "_")

    db.collection("song_searches").document(cache_key).set(payload, merge=True)

def search_saved_searches(query: str, album_filter=None):
    """
    Check the GLOBAL song cache for a prior AI result.
    Tries exact key first, then a broader Firestore query on query_lower.
    Returns the stored result dict if found and valid, else None.
    """
    query_lower = query.strip().lower()

    # 1. Exact key match (with album filter)
    cache_key = query_lower
    if album_filter:
        cache_key += "__" + album_filter.lower().replace(" ", "_")

    try:
        doc = db.collection("song_searches").document(cache_key).get()
        if doc.exists:
            result = doc.to_dict().get("result", {})
            if result.get("found"):
                return result
    except Exception:
        pass

    # 2. Exact key match (without album filter)
    if album_filter:
        try:
            doc = db.collection("song_searches").document(query_lower).get()
            if doc.exists:
                result = doc.to_dict().get("result", {})
                if result.get("found"):
                    return result
        except Exception:
            pass

    # 3. Broad query — find any cached doc whose query_lower contains the search term
    try:
        docs = (
            db.collection("song_searches")
            .where("query_lower", ">=", query_lower)
            .where("query_lower", "<=", query_lower + "\uf8ff")
            .limit(5)
            .stream()
        )
        for doc in docs:
            result = doc.to_dict().get("result", {})
            if result.get("found"):
                return result
    except Exception:
        pass

    return None

def get_approved_facts_for_song(query: str) -> list:
    """
    Return approved community facts whose title or content mentions the song.
    Used as Tier 2 DB check before calling the AI.
    """
    query_lower = query.strip().lower()
    try:
        facts = get_community_facts("approved")
        return [
            f for f in facts
            if query_lower in f.get("title", "").lower()
            or query_lower in f.get("content", "").lower()
        ]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# COMMUNITY FACTS
# ══════════════════════════════════════════════════════════════════════════════

def submit_community_fact(
    username: str,
    category: str,
    title: str,
    content: str,
) -> None:
    """Submit a community fact for admin review."""
    db.collection("community_facts").document().set({
        "username":     username,
        "category":     category,
        "title":        title,
        "content":      content,
        "status":       "pending",
        "submitted_at": _now(),
        "reviewed_by":  None,
        "reviewed_at":  None,
    })


def get_community_facts(status: str = "approved") -> list:
    """
    Fetch community facts filtered by status.
    status: "approved" | "pending" | "rejected"
    """
    docs = (
        db.collection("community_facts")
          .where("status", "==", status)
          .order_by("submitted_at", direction=firestore.Query.DESCENDING)
          .stream()
    )
    results = []
    for d in docs:
        data = d.to_dict()
        data["id"] = d.id
        results.append(data)
    return results


def review_community_fact(fact_id: str, new_status: str, reviewed_by: str) -> None:
    """Approve or reject a community fact."""
    db.collection("community_facts").document(fact_id).update({
        "status":      new_status,
        "reviewed_by": reviewed_by,
        "reviewed_at": _now(),
    })


def get_approved_facts_for_prompt() -> str:
    """
    Build a short addendum of approved community facts to inject into the
    AI system prompt. Returns empty string if none exist.
    """
    try:
        facts = get_community_facts("approved")
        if not facts:
            return ""
        lines = ["\n\n--- Community-contributed Swiftie facts (verified) ---"]
        for f in facts[:30]:
            lines.append(
                f"[{f.get('category', '').upper()}] {f.get('title', '')}: "
                f"{f.get('content', '')}"
            )
        return "\n".join(lines)
    except Exception:
        return ""

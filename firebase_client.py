"""
firebase_client.py
──────────────────
Handles all Firestore interactions for the SwiftieBot chatbot.

Firestore structure:
  sessions/
    {session_id}/
      created_at: timestamp
      message_count: int
      messages/          ← sub-collection
        {auto_id}/
          role: "user" | "assistant"
          content: str
          timestamp: ISO string
"""

import os
import json
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore

# ── Initialise Firebase (runs once) ──────────────────────────────────────────

def _init_firebase():
    """Initialise the Firebase Admin SDK using the service-account JSON.

    Reads credentials from one of two places (in priority order):
      1. FIREBASE_SERVICE_ACCOUNT  env-var containing the JSON string
      2. firebase_service_account.json file next to this module
    """
    if firebase_admin._apps:          # already initialised
        return firestore.client()

    # Option 1 – env var (recommended for Streamlit Cloud secrets)
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if raw:
        cred_dict = json.loads(raw)
        cred = credentials.Certificate(cred_dict)
    else:
        # Option 2 – local JSON file (for development)
        sa_path = os.path.join(os.path.dirname(__file__), "firebase_service_account.json")
        if not os.path.exists(sa_path):
            raise FileNotFoundError(
                "Firebase credentials not found.\n"
                "Either set the FIREBASE_SERVICE_ACCOUNT env-var or place "
                "firebase_service_account.json next to firebase_client.py"
            )
        cred = credentials.Certificate(sa_path)

    firebase_admin.initialize_app(cred)
    return firestore.client()


def _db():
    """Return a Firestore client, initialising if necessary."""
    return _init_firebase()


# ── Public helpers ────────────────────────────────────────────────────────────

def create_session(session_id: str) -> None:
    """Create a new session document in Firestore."""
    try:
        db = _db()
        db.collection("sessions").document(session_id).set(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "message_count": 0,
            }
        )
    except Exception as e:
        print(f"[Firebase] create_session error: {e}")


def save_message(session_id: str, role: str, content: str) -> None:
    """Append a message to the session's sub-collection and increment counter."""
    try:
        db = _db()
        session_ref = db.collection("sessions").document(session_id)

        # Add message to sub-collection
        session_ref.collection("messages").add(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Increment message counter on the parent document
        session_ref.update({"message_count": firestore.Increment(1)})

    except Exception as e:
        print(f"[Firebase] save_message error: {e}")


def get_chat_history(session_id: str) -> list[dict]:
    """Return all messages for a session, ordered by timestamp."""
    try:
        db = _db()
        docs = (
            _db()
            .collection("sessions")
            .document(session_id)
            .collection("messages")
            .order_by("timestamp")
            .stream()
        )
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[Firebase] get_chat_history error: {e}")
        return []


def save_search(session_id: str, query: str, album_filter: str | None, result: dict) -> None:
    """Save a song search query and its result to Firestore."""
    try:
        db = _db()
        db.collection("sessions").document(session_id).collection("searches").add(
            {
                "query": query,
                "album_filter": album_filter or "any",
                "found": result.get("found", False),
                "song_title": result.get("song_title", ""),
                "album": result.get("album", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        print(f"[Firebase] save_search error: {e}")


def get_all_sessions() -> list[dict]:
    """Return all session metadata (for admin/analytics use)."""
    try:
        db = _db()
        docs = db.collection("sessions").order_by("created_at", direction=firestore.Query.DESCENDING).limit(100).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["session_id"] = doc.id
            results.append(data)
        return results
    except Exception as e:
        print(f"[Firebase] get_all_sessions error: {e}")
        return []

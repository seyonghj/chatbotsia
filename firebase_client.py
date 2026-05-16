"""
firebase_client.py — SwiftieBot
────────────────────────────────
Firestore layout:
  users/{username}
    password_hash, display_name, created_at, last_login, is_admin

  users/{username}/sessions/{session_id}
    created_at, message_count, last_updated

  users/{username}/sessions/{session_id}/messages/{id}
    role, content, timestamp

  users/{username}/sessions/{session_id}/searches/{id}
    query, album_filter, found, song_title, album, timestamp

  community_facts/{id}
    username, category, title, content, status, submitted_at, reviewed_by, reviewed_at

NOTE: All queries use single-field ordering only to avoid needing composite indexes.
"""

import os, json, hashlib
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore

# ── Init ──────────────────────────────────────────────────────────────────────
def _init_firebase():
    if firebase_admin._apps:
        return firestore.client()
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if raw:
        cred = credentials.Certificate(json.loads(raw))
    else:
        sa_path = os.path.join(os.path.dirname(__file__), "firebase_service_account.json")
        if not os.path.exists(sa_path):
            raise FileNotFoundError(
                "Firebase credentials not found.\n"
                "Set FIREBASE_SERVICE_ACCOUNT env-var or place "
                "firebase_service_account.json next to this file."
            )
        cred = credentials.Certificate(sa_path)
    firebase_admin.initialize_app(cred)
    return firestore.client()

def _db():
    return _init_firebase()

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Auth ──────────────────────────────────────────────────────────────────────
def register_user(username: str, password: str, display_name: str = "") -> dict:
    try:
        db = _db()
        username = username.strip().lower()
        if not username or not password:
            return {"success": False, "error": "Username and password cannot be empty."}
        if len(username) < 3:
            return {"success": False, "error": "Username must be at least 3 characters."}
        if len(password) < 6:
            return {"success": False, "error": "Password must be at least 6 characters."}
        if not username.isalnum():
            return {"success": False, "error": "Username can only contain letters and numbers."}

        ref = db.collection("users").document(username)
        if ref.get().exists:
            return {"success": False, "error": "Username already taken. Please choose another."}

        dn = display_name.strip() or username
        ref.set({
            "password_hash": _hash(password),
            "display_name": dn,
            "created_at": _now(),
            "last_login": _now(),
            "is_admin": False,
        })
        return {"success": True, "user": {"username": username, "display_name": dn, "is_admin": False}}
    except Exception as e:
        return {"success": False, "error": str(e)}


def login_user(username: str, password: str) -> dict:
    try:
        db = _db()
        username = username.strip().lower()
        if not username or not password:
            return {"success": False, "error": "Please enter username and password."}
        ref = db.collection("users").document(username)
        doc = ref.get()
        if not doc.exists:
            return {"success": False, "error": "Username not found."}
        data = doc.to_dict()
        if data.get("password_hash") != _hash(password):
            return {"success": False, "error": "Incorrect password."}
        ref.update({"last_login": _now()})
        dn = data.get("display_name", username)
        return {"success": True, "user": {
            "username": username,
            "display_name": dn,
            "is_admin": data.get("is_admin", False),
        }}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Sessions ──────────────────────────────────────────────────────────────────
def create_session(username: str, session_id: str) -> None:
    try:
        now = _now()
        _db().collection("users").document(username) \
             .collection("sessions").document(session_id).set({
                 "created_at": now,
                 "last_updated": now,
                 "message_count": 0,
             })
    except Exception as e:
        print(f"[Firebase] create_session: {e}")


def get_user_sessions(username: str) -> list[dict]:
    """Sessions ordered by last_updated — single field, no composite index needed."""
    try:
        docs = _db().collection("users").document(username) \
                    .collection("sessions") \
                    .order_by("last_updated", direction=firestore.Query.DESCENDING) \
                    .limit(30).stream()
        results = []
        for doc in docs:
            d = doc.to_dict()
            d["session_id"] = doc.id
            results.append(d)
        return results
    except Exception as e:
        print(f"[Firebase] get_user_sessions: {e}")
        return []


def get_user_session_history(username: str, session_id: str) -> list[dict]:
    """Load messages for a session ordered by timestamp."""
    try:
        docs = _db().collection("users").document(username) \
                    .collection("sessions").document(session_id) \
                    .collection("messages") \
                    .order_by("timestamp") \
                    .stream()
        return [{"role": d["role"], "content": d["content"]} for d in (doc.to_dict() for doc in docs)]
    except Exception as e:
        print(f"[Firebase] get_user_session_history: {e}")
        return []


def delete_user_session(username: str, session_id: str) -> None:
    try:
        db = _db()
        session_ref = db.collection("users").document(username) \
                        .collection("sessions").document(session_id)
        # Delete sub-collection messages
        for doc in session_ref.collection("messages").stream():
            doc.reference.delete()
        for doc in session_ref.collection("searches").stream():
            doc.reference.delete()
        session_ref.delete()
    except Exception as e:
        print(f"[Firebase] delete_user_session: {e}")


# ── Messages ──────────────────────────────────────────────────────────────────
def save_message(username: str, session_id: str, role: str, content: str) -> None:
    try:
        db = _db()
        now = _now()
        session_ref = db.collection("users").document(username) \
                        .collection("sessions").document(session_id)
        session_ref.collection("messages").add({
            "role": role,
            "content": content,
            "timestamp": now,
        })
        session_ref.update({
            "message_count": firestore.Increment(1),
            "last_updated": now,
        })
    except Exception as e:
        print(f"[Firebase] save_message: {e}")


def load_messages(username: str, session_id: str) -> list[dict]:
    return get_user_session_history(username, session_id)


# ── Searches ──────────────────────────────────────────────────────────────────
def save_search(username: str, session_id: str, query: str,
                album_filter: str | None, result: dict) -> None:
    try:
        _db().collection("users").document(username) \
             .collection("sessions").document(session_id) \
             .collection("searches").add({
                 "query": query,
                 "album_filter": album_filter or "any",
                 "found": result.get("found", False),
                 "song_title": result.get("song_title", ""),
                 "album": result.get("album", ""),
                 "timestamp": _now(),
             })
    except Exception as e:
        print(f"[Firebase] save_search: {e}")


# ── Community facts ───────────────────────────────────────────────────────────
def submit_community_fact(username: str, category: str, title: str, content: str) -> None:
    _db().collection("community_facts").add({
        "username": username,
        "category": category,
        "title": title,
        "content": content,
        "status": "pending",
        "submitted_at": _now(),
        "reviewed_by": None,
        "reviewed_at": None,
    })


def get_community_facts(status: str) -> list[dict]:
    """
    Fetch facts by status only — single field filter, no composite index needed.
    Sorted in Python to avoid needing a (status + submitted_at) composite index.
    """
    try:
        docs = _db().collection("community_facts") \
                    .where("status", "==", status) \
                    .stream()
        results = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            results.append(d)
        # Sort by submitted_at in Python — no Firestore index required
        results.sort(key=lambda x: x.get("submitted_at", ""), reverse=(status != "approved"))
        return results
    except Exception as e:
        print(f"[Firebase] get_community_facts: {e}")
        return []


def review_community_fact(fact_id: str, new_status: str, reviewed_by: str) -> None:
    try:
        _db().collection("community_facts").document(fact_id).update({
            "status": new_status,
            "reviewed_by": reviewed_by,
            "reviewed_at": _now(),
        })
    except Exception as e:
        print(f"[Firebase] review_community_fact: {e}")


def get_approved_facts_for_prompt() -> str:
    """Return approved community facts formatted for injection into the system prompt."""
    try:
        facts = get_community_facts("approved")
        if not facts:
            return ""
        lines = ["\n\nCOMMUNITY FACTS (verified by admin — use when relevant):"]
        for f in facts[:15]:
            lines.append(f"[{f.get('category','').upper()}] {f.get('title','')}: {f.get('content','')}")
        return "\n".join(lines)
    except Exception:
        return ""
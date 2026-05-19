"""
firebase_client.py — SwiftieBot Firebase/Firestore backend
All functions called by app.py are implemented here.
"""

import uuid
import hashlib
import re
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st

# ── Firebase init (runs once) ─────────────────────────────────────────────────
def _init_firebase():
    if firebase_admin._apps:
        return
    try:
        # Try Streamlit secrets first (dict-style service account)
        cred_dict = dict(st.secrets["firebase"])
        # Fix escaped newlines in private_key
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(cred_dict)
    except Exception:
        try:
            # Fallback: path to service account JSON file
            cred = credentials.Certificate("serviceAccountKey.json")
        except Exception as e:
            raise RuntimeError(f"Firebase credentials not found: {e}")
    firebase_admin.initialize_app(cred)

_init_firebase()

def _db() -> firestore.client:
    return firestore.client()


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _clean_content(raw: str) -> str:
    """Strip surrounding extra quotes that can appear when content is double-serialised."""
    s = raw.strip()
    if s.startswith('""') and s.endswith('""'):
        s = s[2:-2]
    elif s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s.strip()


# ════════════════════════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════════════════════════

def register_user(username: str, password: str, display_name: str = "") -> dict:
    """
    Register a new user.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}.
    """
    username = username.strip().lower()
    if not re.match(r'^[a-z0-9_]{3,30}$', username):
        return {"success": False, "error": "Username must be 3–30 characters, letters/numbers/underscores only."}
    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    db = _db()
    ref = db.collection("users").document(username)
    if ref.get().exists:
        return {"success": False, "error": "Username already taken. Please choose another."}

    display = display_name.strip() or username
    user_data = {
        "username":     username,
        "display_name": display,
        "password_hash": _hash_password(password),
        "is_admin":     False,
        "created_at":   _now_iso(),
    }
    ref.set(user_data)
    return {"success": True, "user": {k: v for k, v in user_data.items() if k != "password_hash"}}


def login_user(username: str, password: str) -> dict:
    """
    Verify credentials.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}.
    """
    username = username.strip().lower()
    db = _db()
    doc = db.collection("users").document(username).get()
    if not doc.exists:
        return {"success": False, "error": "Username not found."}

    data = doc.to_dict()
    if data.get("password_hash") != _hash_password(password):
        return {"success": False, "error": "Incorrect password."}

    user = {k: v for k, v in data.items() if k != "password_hash"}
    return {"success": True, "user": user}


# ════════════════════════════════════════════════════════════════════════════
# SESSIONS
# ════════════════════════════════════════════════════════════════════════════

def create_session(username: str, session_id: str) -> None:
    db = _db()
    db.collection("sessions").document(session_id).set({
        "username":      username,
        "session_id":    session_id,
        "created_at":    _now_iso(),
        "last_updated":  _now_iso(),
        "message_count": 0,
    })


def get_user_sessions(username: str) -> list:
    """Return all sessions for a user, most recent first."""
    db = _db()
    docs = (
        db.collection("sessions")
        .where("username", "==", username)
        .order_by("last_updated", direction=firestore.Query.DESCENDING)
        .limit(50)
        .stream()
    )
    return [d.to_dict() for d in docs]


def delete_user_session(username: str, session_id: str) -> None:
    db = _db()
    # Delete session doc
    db.collection("sessions").document(session_id).delete()
    # Delete all messages in that session
    msgs = (
        db.collection("user_chats")
        .where("username", "==", username)
        .where("session_id", "==", session_id)
        .stream()
    )
    for m in msgs:
        m.reference.delete()


def get_user_session_history(username: str, session_id: str) -> list:
    """Return messages for a specific session as [{role, content}, ...]."""
    return load_messages(username, session_id)


# ════════════════════════════════════════════════════════════════════════════
# MESSAGES
# ════════════════════════════════════════════════════════════════════════════

def save_message(username: str, session_id: str, role: str, content: str) -> None:
    db = _db()
    msg_id = str(uuid.uuid4())
    db.collection("user_chats").document(msg_id).set({
        "username":   username,
        "session_id": session_id,
        "role":       role,
        "content":    content,
        "timestamp":  _now_iso(),
    })
    # Update session metadata
    sess_ref = db.collection("sessions").document(session_id)
    sess_doc = sess_ref.get()
    if sess_doc.exists:
        count = sess_doc.to_dict().get("message_count", 0) + 1
        sess_ref.update({"message_count": count, "last_updated": _now_iso()})


def load_messages(username: str, session_id: str) -> list:
    """Return messages in chronological order as [{role, content}, ...]."""
    db = _db()
    docs = (
        db.collection("user_chats")
        .where("username",   "==", username)
        .where("session_id", "==", session_id)
        .order_by("timestamp", direction=firestore.Query.ASCENDING)
        .stream()
    )
    return [{"role": d.get("role"), "content": d.get("content")} for d in docs]


# ════════════════════════════════════════════════════════════════════════════
# SONG SEARCH CACHE
# ════════════════════════════════════════════════════════════════════════════

def save_search(
    username: str,
    session_id: str,
    query: str,
    album_filter: str | None,
    result: dict,
) -> None:
    """Cache an AI song-search result globally so all users benefit."""
    db = _db()
    # Use a deterministic ID so the same query never duplicates
    cache_key = re.sub(r'\s+', '_', query.lower().strip())
    if album_filter:
        cache_key += "__" + re.sub(r'\s+', '_', album_filter.lower())

    db.collection("song_searches").document(cache_key).set({
        "query":        query.lower().strip(),
        "album_filter": album_filter,
        "result":       result,
        "cached_by":    username,
        "session_id":   session_id,
        "cached_at":    _now_iso(),
        **result,          # flatten for easy Firestore querying
    })


def search_saved_searches(query: str, album_filter: str | None) -> dict | None:
    """
    Look up a cached song result.
    Returns the result dict or None if not cached.
    """
    db = _db()
    cache_key = re.sub(r'\s+', '_', query.lower().strip())
    if album_filter:
        cache_key += "__" + re.sub(r'\s+', '_', album_filter.lower())

    doc = db.collection("song_searches").document(cache_key).get()
    if doc.exists:
        data = doc.to_dict()
        return data.get("result") or data
    return None


# ════════════════════════════════════════════════════════════════════════════
# COMMUNITY FACTS
# ════════════════════════════════════════════════════════════════════════════

def submit_community_fact(
    username: str,
    category: str,
    title: str,
    content: str,
) -> None:
    """Submit a new community fact for admin review."""
    db = _db()
    doc_id = str(uuid.uuid4())
    db.collection("community_facts").document(doc_id).set({
        "username":     username,
        "category":     category,
        "title":        title.strip(),
        "content":      content.strip(),   # saved raw — no extra quotes
        "status":       "pending",
        "submitted_at": _now_iso(),
        "reviewed_at":  None,
        "reviewed_by":  None,
    })


def get_community_facts(status: str = "approved") -> list:
    """
    Return community facts filtered by status.
    status: "approved" | "pending" | "rejected"
    """
    db = _db()
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
        # Sanitise content that was accidentally double-quoted on save
        if "content" in data:
            data["content"] = _clean_content(str(data["content"]))
        results.append(data)
    return results


def review_community_fact(fact_id: str, new_status: str, reviewed_by: str) -> None:
    """Approve or reject a community fact."""
    db = _db()
    db.collection("community_facts").document(fact_id).update({
        "status":      new_status,
        "reviewed_by": reviewed_by,
        "reviewed_at": _now_iso(),
    })


# ── Facts injected into the AI system prompt ──────────────────────────────────

def get_approved_facts_for_prompt() -> str:
    """
    Return ALL approved facts as a formatted string for the system prompt.
    Returns "" if there are none (safe to concatenate).
    """
    try:
        facts = get_community_facts("approved")
        if not facts:
            return ""
        lines = []
        for f in facts:
            cat     = f.get("category", "general").upper()
            title   = f.get("title",   "")
            content = f.get("content", "")
            lines.append(f"\n- [{cat}] {title}: {content}")
        return "".join(lines)
    except Exception as e:
        print(f"[SwiftieBot] get_approved_facts_for_prompt error: {e}")
        return ""


def get_approved_facts_for_song(song_hint: str) -> list:
    """
    Return approved facts relevant to a specific song.

    Uses NLP fuzzy matching first (via nlp_engine), falls back to plain
    substring match so it still works if the NLP layer fails to import.
    """
    try:
        all_facts = get_community_facts("approved")
        hint = song_hint.lower().strip()
        if not hint:
            return []

        # ── Try NLP-ranked matching first ─────────────────────────────────────
        try:
            from nlp_engine import rank_facts
            ranked = rank_facts(hint, all_facts, threshold=0.12, top_k=10)
            if ranked:
                return ranked
        except Exception as nlp_err:
            print(f"[SwiftieBot] NLP song match failed, falling back: {nlp_err}")

        # ── Fallback: simple substring match ─────────────────────────────────
        matched = []
        for f in all_facts:
            haystack = (
                f.get("title",   "").lower() + " " +
                f.get("content", "").lower()
            )
            if hint in haystack:
                matched.append(f)
        return matched

    except Exception as e:
        print(f"[SwiftieBot] get_approved_facts_for_song error: {e}")
        return []


def search_facts_by_nlp(user_msg: str) -> list:
    """
    Full NLP pipeline search against ALL approved community facts.
    Called by app.py on every chat message to find the most relevant facts
    to inject into the system prompt.

    Returns a list of fact dicts sorted by NLP relevance score (highest first),
    each with an added '_nlp_score' key.
    """
    try:
        all_facts = get_community_facts("approved")
        if not all_facts:
            return []

        from nlp_engine import rank_facts
        return rank_facts(user_msg, all_facts, threshold=0.12, top_k=8)

    except Exception as e:
        print(f"[SwiftieBot] search_facts_by_nlp error: {e}")
        return []

import streamlit as st
from groq import Groq
import os, uuid, json as _json, re
from firebase_client import (
    register_user, login_user,
    create_session, get_user_sessions,
    get_user_session_history, delete_user_session,
    save_message, load_messages, save_search,
    search_saved_searches, get_approved_facts_for_song,
    submit_community_fact, get_community_facts,
    review_community_fact, get_approved_facts_for_prompt,
    search_facts_by_nlp,
)
from nlp_engine import (
    detect_intent,
    extract_entities,
    build_facts_context,
    expand_song_query,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SwiftieBot",
    page_icon="🎸",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0d0718 0%, #12102a 40%, #0a1628 100%);
    min-height: 100vh;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d0718 0%, #0a1020 100%);
    border-right: 1px solid rgba(212,175,55,0.2);
}
[data-testid="stSidebar"] * { color: #e8d5b7 !important; }
[data-testid="stSidebar"] .stMarkdown p { color: #a89bc2 !important; }

[data-testid="stTabs"] button {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    color: #7a6e8a !important;
    border-bottom: 2px solid transparent !important;
    padding: 0.6rem 1.2rem !important;
    transition: all 0.2s !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #d4af37 !important;
    border-bottom: 2px solid #d4af37 !important;
    background: transparent !important;
}
[data-testid="stTabs"] button:hover { color: #d4af37 !important; }
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid rgba(212,175,55,0.15) !important;
    gap: 0.3rem;
    margin-bottom: 1rem;
}

.ts-header { text-align: center; padding: 1.2rem 0 0.5rem; }
.ts-header h1 {
    font-family: 'Playfair Display', serif;
    font-size: 2.6rem;
    background: linear-gradient(90deg, #b8860b, #f5e6a3, #d4af37, #f5e6a3, #b8860b);
    background-size: 200%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    letter-spacing: 2px;
    animation: shimmer 4s linear infinite;
}
@keyframes shimmer { 0%{background-position:0%} 100%{background-position:200%} }
.ts-header p { color: #7a6e8a; font-size: 0.88rem; margin-top: 0.3rem; font-style: italic; }
.ts-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(212,175,55,0.4), transparent);
    margin: 0.8rem 0 1.2rem;
}

.stChatMessage {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(212,175,55,0.12) !important;
    border-radius: 14px !important;
    margin-bottom: 0.7rem !important;
    padding: 0.2rem 0 !important;
    transition: border-color 0.2s !important;
}
.stChatMessage:hover { border-color: rgba(212,175,55,0.25) !important; }
[data-testid="stChatMessageContent"] p {
    color: #ddd0be !important;
    font-size: 0.95rem;
    line-height: 1.7;
}

[data-testid="stChatInput"] textarea {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(212,175,55,0.3) !important;
    border-radius: 30px !important;
    color: #e8d5b7 !important;
    font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #d4af37 !important;
    box-shadow: 0 0 0 2px rgba(212,175,55,0.15) !important;
}

[data-testid="stTextInput"] input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(212,175,55,0.25) !important;
    border-radius: 10px !important;
    color: #e8d5b7 !important;
    font-family: 'DM Sans', sans-serif !important;
    padding: 0.55rem 0.9rem !important;
    transition: all 0.2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #d4af37 !important;
    box-shadow: 0 0 0 2px rgba(212,175,55,0.12) !important;
    background: rgba(255,255,255,0.07) !important;
}
[data-testid="stTextInput"] label { color: #8a7ea0 !important; font-size: 0.85rem !important; }

[data-testid="stTextArea"] textarea {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(212,175,55,0.25) !important;
    border-radius: 10px !important;
    color: #e8d5b7 !important;
    font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stTextArea"] textarea:focus {
    border-color: #d4af37 !important;
    box-shadow: 0 0 0 2px rgba(212,175,55,0.12) !important;
}
[data-testid="stTextArea"] label { color: #8a7ea0 !important; font-size: 0.85rem !important; }

[data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(212,175,55,0.25) !important;
    color: #e8d5b7 !important;
    border-radius: 10px !important;
}

.stButton > button {
    background: linear-gradient(135deg, rgba(212,175,55,0.15), rgba(212,175,55,0.05));
    border: 1px solid rgba(212,175,55,0.35);
    color: #d4af37 !important;
    border-radius: 10px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    font-weight: 500;
    transition: all 0.2s;
    width: 100%;
    padding: 0.45rem 1rem !important;
}
.stButton > button:hover {
    background: rgba(212,175,55,0.25);
    border-color: #d4af37;
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(212,175,55,0.15);
}
.stButton > button:active { transform: translateY(0); }

.source-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(50,200,120,0.1);
    border: 1px solid rgba(50,200,120,0.3);
    color: #50c878;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 0.8rem;
}
.source-badge.ai {
    background: rgba(147,112,219,0.1);
    border-color: rgba(147,112,219,0.3);
    color: #9370db;
}
.source-badge.community {
    background: rgba(212,175,55,0.1);
    border-color: rgba(212,175,55,0.3);
    color: #d4af37;
}

.hero-section { text-align: center; padding: 4rem 2rem; }
.hero-section .hero-icon { font-size: 4rem; margin-bottom: 1rem; }
.hero-section h2 {
    font-family: 'Playfair Display', serif;
    font-size: 2rem;
    color: #d4af37;
    margin: 0 0 0.5rem;
}
.hero-section p { color: #7a6e8a; font-size: 0.95rem; line-height: 1.7; }
.hero-features {
    display: flex;
    gap: 1rem;
    justify-content: center;
    flex-wrap: wrap;
    margin-top: 2rem;
}
.hero-feature {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(212,175,55,0.2);
    border-radius: 12px;
    padding: 1rem 1.4rem;
    text-align: center;
    min-width: 130px;
    color: #a89bc2;
    font-size: 0.85rem;
}
.hero-feature .feat-icon { font-size: 1.6rem; margin-bottom: 0.4rem; }
.hero-feature span { color: #d4af37; font-weight: 600; display: block; font-size: 0.82rem; }

.song-card {
    background: linear-gradient(145deg, rgba(212,175,55,0.06), rgba(255,255,255,0.03));
    border: 1px solid rgba(212,175,55,0.2);
    border-radius: 16px;
    padding: 1.6rem 1.8rem;
    margin-top: 1rem;
    color: #e8d5b7;
    line-height: 1.7;
    position: relative;
    overflow: hidden;
}
.song-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #d4af37, transparent);
}
.song-card h3 {
    font-family: 'Playfair Display', serif;
    color: #f0d060;
    font-size: 1.5rem;
    margin: 0 0 0.3rem;
}
.song-card .album-tag {
    display: inline-block;
    background: rgba(212,175,55,0.12);
    border: 1px solid rgba(212,175,55,0.25);
    color: #c9a227;
    border-radius: 20px;
    padding: 3px 14px;
    font-size: 0.78rem;
    margin-bottom: 1rem;
    font-weight: 500;
}
.lyric-line {
    background: rgba(212,175,55,0.06);
    border-left: 3px solid #d4af37;
    border-radius: 0 8px 8px 0;
    padding: 0.7rem 1rem;
    font-style: italic;
    font-size: 1rem;
    color: #f5e6a3;
    margin: 0.5rem 0 1rem;
}

.info-label { color: #7a6e8a !important; font-size: 0.78rem !important; font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.5px !important; margin-bottom: 0.1rem !important; }
.info-value { color: #e8d5b7 !important; font-size: 0.92rem !important; margin-bottom: 0.8rem !important; }

.section-block {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(212,175,55,0.1);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
}
.section-block h4 { color: #d4af37; margin: 0 0 0.4rem; font-size: 0.88rem; font-weight: 600; }
.section-block p { color: #c8bda8; font-size: 0.9rem; margin: 0; line-height: 1.6; }

.fun-fact-block {
    background: linear-gradient(135deg, rgba(212,175,55,0.08), rgba(212,175,55,0.03));
    border: 1px solid rgba(212,175,55,0.25);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    position: relative;
}
.fun-fact-block::before { content: '🥚'; position: absolute; top: -10px; right: 12px; font-size: 1.2rem; }
.fun-fact-block p { color: #e8d5b7; font-size: 0.9rem; margin: 0; line-height: 1.6; }

.history-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(212,175,55,0.15);
    border-radius: 12px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.5rem;
    transition: border-color 0.2s;
}
.history-card:hover { border-color: rgba(212,175,55,0.35); }
.history-card.current { border-color: rgba(212,175,55,0.45); background: rgba(212,175,55,0.05); }
.history-card .h-id { color: #d4af37; font-size: 0.82rem; font-family: monospace; font-weight: 600; }
.history-card .h-meta { color: #7a6e8a; font-size: 0.78rem; margin-top: 0.15rem; }

.fact-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(212,175,55,0.15);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    color: #e8d5b7;
}
.fact-card.pending { border-color: rgba(255,165,0,0.35); }
.fact-cat {
    display: inline-block;
    background: rgba(212,175,55,0.12);
    border: 1px solid rgba(212,175,55,0.25);
    color: #c9a227;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    margin-bottom: 0.4rem;
}
.fact-title { color: #d4af37; font-weight: 600; font-size: 0.95rem; margin: 0.2rem 0; }
.fact-content { color: #b8a898; font-size: 0.88rem; line-height: 1.55; }
.fact-meta { color: #5a5270; font-size: 0.75rem; margin-top: 0.4rem; }

.chip-row { display:flex; flex-wrap:wrap; gap:8px; margin:1.2rem 0; justify-content:center; }
.chip {
    background: rgba(212,175,55,0.08);
    border: 1px solid rgba(212,175,55,0.25);
    color: #c9a227;
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}
.chip:hover { background: rgba(212,175,55,0.15); border-color: #d4af37; }

.stSuccess > div { background: rgba(50,200,100,0.1) !important; border-color: rgba(50,200,100,0.3) !important; }
.stError > div { background: rgba(220,50,50,0.1) !important; border-color: rgba(220,50,50,0.3) !important; }
.stWarning > div { background: rgba(255,165,0,0.1) !important; border-color: rgba(255,165,0,0.3) !important; }

[data-testid="stMetric"] { background: rgba(255,255,255,0.03); border-radius: 10px; padding: 0.6rem; }
[data-testid="stMetricValue"] { color: #d4af37 !important; }
[data-testid="stMetricLabel"] { color: #7a6e8a !important; }

hr { border-color: rgba(212,175,55,0.12) !important; }
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(212,175,55,0.25); border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Groq ──────────────────────────────────────────────────────────────────────
groq_key = os.environ.get("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    st.error("⚠️ GROQ_API_KEY missing. Add it to .streamlit/secrets.toml")
    st.stop()

groq_client = Groq(api_key=groq_key)
GROQ_MODEL  = "llama-3.1-8b-instant"
ADMIN_PW    = os.environ.get("ADMIN_PASSWORD") or st.secrets.get("ADMIN_PASSWORD", "swiftieadmin2024")

SONG_SEARCH_PROMPT = """You are a Taylor Swift music expert. Return ONLY a JSON object — no markdown, no backticks:
{
  "found": true,
  "song_title": "exact title",
  "album": "album name",
  "year": "release year",
  "era": "era name",
  "writers": "comma-separated writers",
  "producers": "comma-separated producers",
  "duration": "m:ss or Unknown",
  "chart_peak": "e.g. #1 US Billboard Hot 100 or Unknown",
  "certifications": "e.g. Diamond or Unknown",
  "themes": "2-3 sentences on themes and mood",
  "story": "2-3 sentences on songwriting story/inspiration",
  "iconic_moment": "one memorable cultural/performance moment",
  "lyric_snippet": "one short iconic line under 12 words",
  "fun_fact": "one easter egg or surprising fan fact"
}
If not found: {"found": false, "message": "brief helpful message"}
Return ONLY the JSON."""


# ════════════════════════════════════════════════════════════════════════════
# NLP-POWERED SYSTEM PROMPT BUILDER
# ════════════════════════════════════════════════════════════════════════════

# Cache approved facts in session so we don't hit Firestore on every keystroke.
# Refreshed once per session (cleared on new chat / logout).
def _get_cached_facts() -> list:
    """Load all approved facts once per Streamlit session, cache in session_state."""
    if "nlp_facts_cache" not in st.session_state:
        try:
            st.session_state.nlp_facts_cache = get_community_facts("approved")
        except Exception:
            st.session_state.nlp_facts_cache = []
    return st.session_state.nlp_facts_cache


def build_system_prompt(user_msg: str = "") -> str:
    """
    Enhanced system prompt builder.
    
    Features:
    - Works for BOTH Taylor and non-Taylor questions
    - ALWAYS injects community facts
    - NLP retrieval for best matching facts
    - Database facts are treated as highest priority
    """

    base = (
        "You are SwiftieBot, a friendly, intelligent, and conversational AI assistant.\n"

        "Your main specialty is Taylor Swift, including her albums, songs, Eras Tour,\n"
        "Easter eggs, songwriting stories, awards, chart records, and biography.\n"

        "However, you are NOT limited to Taylor Swift.\n"
        "If the user asks about another topic, person, song, artist, technology,\n"
        "school topic, or anything else, respond naturally and helpfully.\n"

        "If relevant information exists in the provided database facts or community facts,\n"
        "you MUST prioritize and use that information.\n"

        "Do NOT force the conversation back to Taylor Swift unless the user asks about her.\n"

        "Be warm, conversational, and engaging.\n"
        "Use light emojis sparingly for warmth.\n\n"

        "CRITICAL INSTRUCTION:\n"
        "Community facts and database facts are considered ground truth.\n"
        "You MUST prioritize them over your training data.\n"
        "If database facts conflict with your own knowledge, the database facts win.\n"
    )

    # Load all approved facts
    all_facts = _get_cached_facts()

    # ─────────────────────────────────────────────
    # ALWAYS inject all community facts
    # ─────────────────────────────────────────────
    if all_facts:
        fact_lines = []

        for f in all_facts[:50]:
            category = f.get("category", "general")
            title = f.get("title", "")
            content = f.get("content", "")

            fact_lines.append(
                f"[{category.upper()}] {title}: {content}"
            )

        facts_text = "\n".join(fact_lines)

        base += (
            "\n\n=== COMMUNITY DATABASE FACTS ===\n"
            f"{facts_text}\n"
            "=== END COMMUNITY DATABASE FACTS ===\n"
        )

    # ─────────────────────────────────────────────
    # NLP-BOOSTED RELEVANT FACTS
    # ─────────────────────────────────────────────
    if user_msg and all_facts:
        try:
            nlp_context = build_facts_context(
                user_msg,
                all_facts,
                threshold=0.02,
                top_k=15
            )

            if nlp_context:
                intent = detect_intent(user_msg)
                entities = extract_entities(user_msg)

                entity_summary = []

                if entities.get("songs"):
                    entity_summary.append(
                        f"songs: {', '.join(entities['songs'][:3])}"
                    )

                if entities.get("albums"):
                    entity_summary.append(
                        f"albums: {', '.join(entities['albums'][:3])}"
                    )

                if entities.get("eras"):
                    entity_summary.append(
                        f"eras: {', '.join(entities['eras'][:3])}"
                    )

                ent_str = ""

                if entity_summary:
                    ent_str = (
                        " | detected entities — "
                        + "; ".join(entity_summary)
                    )

                base += (
                    f"\n\n=== NLP RELEVANT FACTS ===\n"
                    f"[intent={intent}{ent_str}]\n"
                    f"{nlp_context}\n"
                    "=== END NLP FACTS ===\n"
                )

        except Exception as e:
            print(f"[SwiftieBot] NLP retrieval failed: {e}")

    return base
    # ── Layer 3: All remaining approved facts (background context) ────────────
    if all_facts:
        try:
            # Build a concise background block (different from NLP-ranked block above)
            background_lines = []
            for f in all_facts:
                cat     = f.get("category", "general").upper()
                title   = f.get("title",   "")
                content = f.get("content", "")
                background_lines.append(f"  • [{cat}] {title}: {content}")

            if background_lines:
                base += (
                    "\n\n=== ALL COMMUNITY KNOWLEDGE BASE ==="
                    "\n" + "\n".join(background_lines) +
                    "\n=== END KNOWLEDGE BASE ==="
                )
        except Exception as e:
            print(f"[SwiftieBot] Background facts failed: {e}")

    return base


# ── Groq helpers ──────────────────────────────────────────────────────────────
def groq_chat(history: list, user_msg: str) -> str:
    """
    Send a chat message to Groq with NLP-enhanced system prompt.
    The system prompt is rebuilt on every call so:
      - NLP retrieval always matches the current user message
      - Newly approved community facts are picked up within the session
    """
    msgs = [{"role": "system", "content": build_system_prompt(user_msg)}]
    # Pass history excluding the message we're about to append
    for m in history:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_msg})

    r = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=msgs,
        max_tokens=1024,
    )
    return r.choices[0].message.content


def groq_once(user_msg: str) -> str:
    """One-shot call for song search JSON (no history, no community facts needed)."""
    r = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SONG_SEARCH_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=800,
    )
    return r.choices[0].message.content


def _parse_groq_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return _json.loads(raw.strip())


# ── Session defaults ──────────────────────────────────────────────────────────
_defaults = {
    "logged_in":           False,
    "current_user":        None,
    "session_id":          str(uuid.uuid4()),
    "messages":            [],
    "song_result":         None,
    "song_result_source":  None,
    "auth_mode":           "login",
    "admin_authenticated": False,
    "_inject_prompt":      None,
    "show_auth":           False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def uname():
    return st.session_state.current_user["username"] if st.session_state.logged_in else None

def dname():
    return st.session_state.current_user["display_name"] if st.session_state.logged_in else ""


# ════════════════════════════════════════════════════════════════════════════
# AUTH DIALOG
# ════════════════════════════════════════════════════════════════════════════
@st.dialog("🎸 SwiftieBot — Sign In", width="small")
def show_auth_dialog():
    mode = st.session_state.auth_mode

    col_l, col_r = st.columns(2)
    with col_l:
        if st.button("🔑 Log In", key="dlg_goto_login",
                     type="primary" if mode == "login" else "secondary"):
            st.session_state.auth_mode = "login"
            st.rerun()
    with col_r:
        if st.button("📝 Register", key="dlg_goto_reg",
                     type="primary" if mode == "register" else "secondary"):
            st.session_state.auth_mode = "register"
            st.rerun()

    st.markdown("<div class='ts-divider'></div>", unsafe_allow_html=True)

    if mode == "login":
        st.markdown("<p style='text-align:center;color:#7a6e8a;font-style:italic;margin-bottom:1rem;'>Welcome back, Swiftie! ✨</p>", unsafe_allow_html=True)
        username = st.text_input("Username", key="dlg_login_user", placeholder="your username")
        password = st.text_input("Password", key="dlg_login_pass", type="password", placeholder="••••••")
        if st.button("Log In →", key="dlg_btn_login"):
            if not username or not password:
                st.error("Please enter both fields.")
            else:
                res = login_user(username, password)
                if res["success"]:
                    st.session_state.logged_in    = True
                    st.session_state.current_user = res["user"]
                    sid = str(uuid.uuid4())
                    st.session_state.session_id   = sid
                    create_session(res["user"]["username"], sid)
                    st.session_state.messages     = []
                    st.session_state.show_auth    = False
                    st.rerun()
                else:
                    st.error(res["error"])
        st.markdown("<p style='text-align:center;color:#5a5270;font-size:0.82rem;margin-top:1rem;'>No account? Click Register above.</p>", unsafe_allow_html=True)

    else:
        st.markdown("<p style='text-align:center;color:#7a6e8a;font-style:italic;margin-bottom:1rem;'>Create your Swiftie account 💛</p>", unsafe_allow_html=True)
        new_user    = st.text_input("Username (letters & numbers only)", key="dlg_reg_user",     placeholder="swiftie123")
        new_display = st.text_input("Display name (optional)",            key="dlg_reg_display", placeholder="Taylor's #1 Fan")
        new_pass    = st.text_input("Password (min 6 chars)",             key="dlg_reg_pass",    type="password", placeholder="••••••")
        new_pass2   = st.text_input("Confirm password",                   key="dlg_reg_pass2",   type="password", placeholder="••••••")
        if st.button("Create Account →", key="dlg_btn_reg"):
            if not new_user or not new_pass:
                st.error("Please fill in all required fields.")
            elif new_pass != new_pass2:
                st.error("Passwords do not match.")
            else:
                res = register_user(new_user, new_pass, new_display)
                if res["success"]:
                    st.success("Account created! Logging you in... ✨")
                    st.session_state.logged_in    = True
                    st.session_state.current_user = res["user"]
                    sid = str(uuid.uuid4())
                    st.session_state.session_id   = sid
                    create_session(res["user"]["username"], sid)
                    st.session_state.messages     = []
                    st.session_state.show_auth    = False
                    st.rerun()
                else:
                    st.error(res["error"])


if st.session_state.show_auth and not st.session_state.logged_in:
    show_auth_dialog()

# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ✨ SwiftieBot")
    st.markdown("---")

    if not st.session_state.logged_in:
        st.markdown("<p style='color:#7a6e8a;font-size:0.85rem;text-align:center;'>Sign in to save your conversations and contribute facts!</p>", unsafe_allow_html=True)
        if st.button("🔑 Log In / Register", key="sb_open_auth"):
            st.session_state.show_auth = True
            st.rerun()
    else:
        st.markdown(f"**👤 {dname()}**")
        st.caption(f"@{uname()}")
        st.markdown("---")

        if st.button("➕ New Chat", key="sb_new_chat"):
            sid = str(uuid.uuid4())
            st.session_state.session_id  = sid
            create_session(uname(), sid)
            st.session_state.messages    = []
            st.session_state.song_result = None
            st.session_state.pop("nlp_facts_cache", None)   # refresh facts on next message
            st.rerun()

        st.markdown("**📂 Recent Chats**")
        try:
            sessions = get_user_sessions(uname())
            for s in sessions[:8]:
                sid    = s["session_id"]
                count  = s.get("message_count", 0)
                ts     = s.get("last_updated", s.get("created_at", ""))[:10]
                is_cur = sid == st.session_state.session_id
                label  = f"{'🟢 ' if is_cur else ''}💬 {ts} · {count} msg{'s' if count != 1 else ''}"
                if st.button(label, key=f"sb_sess_{sid}"):
                    st.session_state.session_id  = sid
                    st.session_state.messages    = load_messages(uname(), sid)
                    st.session_state.song_result = None
                    st.rerun()
        except Exception:
            st.caption("Could not load sessions.")

        st.markdown("---")
        st.markdown("**🎵 Quick Topics**")
        topics = [
            ("📀 All Albums",    "List all of Taylor Swift's studio albums in order with release years"),
            ("🏆 Awards",        "What are Taylor Swift's biggest award wins?"),
            ("🔁 Re-recordings", "Explain Taylor's Version re-recordings — why and which ones?"),
            ("🌟 Eras Tour",     "Tell me about the Eras Tour setlist and significance"),
            ("🎼 Best Songs",    "What are considered Taylor Swift's greatest songs of all time?"),
            ("🥚 Easter Eggs",   "What are some famous Taylor Swift Easter eggs?"),
        ]
        for label, prompt in topics:
            if st.button(label, key=f"sb_topic_{label}"):
                if not st.session_state.logged_in:
                    st.session_state.show_auth = True
                    st.rerun()
                else:
                    st.session_state._inject_prompt = prompt

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear", key="sb_clear"):
                sid = str(uuid.uuid4())
                st.session_state.session_id  = sid
                create_session(uname(), sid)
                st.session_state.messages    = []
                st.session_state.song_result = None
                st.session_state.pop("nlp_facts_cache", None)
                st.rerun()
        with col2:
            if st.button("🚪 Logout", key="sb_logout"):
                for k in ["logged_in", "current_user", "messages", "song_result",
                          "song_result_source", "admin_authenticated", "_inject_prompt",
                          "nlp_facts_cache"]:
                    st.session_state[k] = _defaults.get(k)
                st.session_state.session_id = str(uuid.uuid4())
                st.rerun()

    st.markdown("---")
    st.markdown("<small style='color:#3a3050;'>Powered by Groq · Firebase</small>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="ts-header">
  <h1>✨ SwiftieBot ✨</h1>
  <p>Your expert guide to Taylor Swift's music, albums &amp; discography</p>
</div>
<div class="ts-divider"></div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# NOT LOGGED IN — HERO
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown("""
    <div class="hero-section">
      <div class="hero-icon">🎸</div>
      <h2>Welcome, Swiftie!</h2>
      <p>The ultimate Taylor Swift companion.<br>
         Chat about songs, search the discography, and share your knowledge with the community.</p>
      <div class="hero-features">
        <div class="hero-feature"><div class="feat-icon">💬</div><span>AI Chat</span>Ask anything about TS</div>
        <div class="hero-feature"><div class="feat-icon">🔍</div><span>Song Search</span>Deep song details</div>
        <div class="hero-feature"><div class="feat-icon">📜</div><span>History</span>All your past chats</div>
        <div class="hero-feature"><div class="feat-icon">💡</div><span>Contribute</span>Share Swiftie facts</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("🔑 Get Started — Log In or Register", key="hero_auth_btn"):
            st.session_state.show_auth = True
            st.rerun()
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════════════
is_admin   = st.session_state.current_user.get("is_admin", False)
tab_labels = ["💬 Chat", "🔍 Song Search", "📜 My History", "💡 Contribute"]
if is_admin:
    tab_labels.append("🛡️ Admin")

tabs = st.tabs(tab_labels)
tab_chat, tab_search, tab_history, tab_contribute = tabs[:4]
tab_admin = tabs[4] if is_admin else None


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ════════════════════════════════════════════════════════════════════════════
with tab_chat:
    if not st.session_state.messages:
        st.markdown("""
        <div class="chip-row">
          <span class="chip">📀 All albums</span>
          <span class="chip">🎵 Song meanings</span>
          <span class="chip">🔁 Taylor's Version</span>
          <span class="chip">🌟 Eras Tour</span>
          <span class="chip">🥚 Easter eggs</span>
          <span class="chip">🏆 Awards</span>
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        avatar = "🎸" if msg["role"] == "assistant" else "🎀"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    def _send(user_text: str):
        # Append to history before calling so context is complete
        st.session_state.messages.append({"role": "user", "content": user_text})
        save_message(uname(), st.session_state.session_id, "user", user_text)

        with st.chat_message("user", avatar="🎀"):
            st.markdown(user_text)

        with st.chat_message("assistant", avatar="🎸"):
            with st.spinner("✨ Searching the Swiftie archives..."):
                # Pass user_text so build_system_prompt can inject song-specific facts
                reply = groq_chat(st.session_state.messages[:-1], user_text)
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        save_message(uname(), st.session_state.session_id, "assistant", reply)

    if st.session_state._inject_prompt:
        prompt = st.session_state._inject_prompt
        st.session_state._inject_prompt = None
        _send(prompt)
        st.rerun()

    if user_input := st.chat_input("Ask me anything about Taylor Swift..."):
        _send(user_input)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — SONG SEARCH
# Priority: 1) Community facts  2) Firestore cache  3) Groq AI
# ════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.markdown("### 🔍 Song Search")
    st.markdown(
        "<p style='color:#7a6e8a;font-size:0.88rem;'>"
        "Search any Taylor Swift song for full details. "
        "Community knowledge is checked first, then the database cache, then the AI."
        "</p>",
        unsafe_allow_html=True,
    )

    ALBUMS = [
        "Any album", "Taylor Swift (2006)", "Fearless (2008)", "Speak Now (2010)",
        "Red (2012)", "1989 (2014)", "reputation (2017)", "Lover (2019)",
        "folklore (2020)", "evermore (2020)", "Midnights (2022)",
        "The Tortured Poets Department (2024)",
        "Fearless (Taylor's Version)", "Red (Taylor's Version)",
        "Speak Now (Taylor's Version)", "1989 (Taylor's Version)",
    ]

    col1, col2 = st.columns([2, 1])
    with col1:
        song_query = st.text_input("Song title", placeholder="e.g. All Too Well, Cruel Summer, Anti-Hero...")
    with col2:
        album_filter = st.selectbox("Filter by album", ALBUMS)

    if st.button("🔍  Search", key="search_btn") and song_query.strip():
        af = album_filter if album_filter != "Any album" else None
        q  = song_query.strip()

        # ── NLP: expand query with fuzzy correction ───────────────────────────
        candidates = expand_song_query(q)
        # Primary search key = best NLP candidate (first = original, rest = fuzzy suggestions)
        primary_q  = candidates[0]

        # ── Tier 1: NLP-ranked community facts (highest priority) ─────────────
        with st.spinner("🧠 Running NLP search through community knowledge..."):
            # Try each candidate until we get a match
            facts = []
            matched_candidate = primary_q
            for candidate in candidates:
                facts = get_approved_facts_for_song(candidate.lower())
                if facts:
                    matched_candidate = candidate
                    break

        if facts:
            # Sort by NLP score if present
            facts_sorted = sorted(facts, key=lambda x: x.get("_nlp_score", 0), reverse=True)
            best_fact    = facts_sorted[0]

            # Build rich themes text from top-3 facts
            themes_parts = []
            for f in facts_sorted[:3]:
                themes_parts.append(f"[{f.get('category','').upper()}] {f.get('title','')}: {f.get('content','')}")
            facts_text = " ✦ ".join(themes_parts)

            # Show NLP correction notice if the query was auto-corrected
            if matched_candidate.lower() != q.lower():
                st.info(f"🧠 NLP matched your query to: **{matched_candidate.title()}**")

            st.session_state.song_result = {
                "found":           True,
                "song_title":      matched_candidate.title() if matched_candidate != primary_q else q.title(),
                "album":           af or "See community facts below",
                "year":            "—",
                "era":             "—",
                "writers":         "—",
                "producers":       "—",
                "duration":        "—",
                "chart_peak":      "—",
                "certifications":  "—",
                "themes":          facts_text,
                "story":           f"Assembled from {len(facts)} community-contributed fact(s). "
                                   f"Top match score: {best_fact.get('_nlp_score', 'n/a')}",
                "iconic_moment":   "—",
                "lyric_snippet":   "From the Swiftie community knowledge base",
                "fun_fact":        best_fact.get("content", "—"),
                "_from_community": True,
                "_fact_count":     len(facts),
            }
            st.session_state.song_result_source = "community"

        else:
            # ── Tier 2: global Firestore cache ────────────────────────────────
            with st.spinner("⚡ Checking saved knowledge..."):
                cached = None
                for candidate in candidates:
                    cached = search_saved_searches(candidate.lower(), af)
                    if cached:
                        break

            if cached:
                st.session_state.song_result        = cached
                st.session_state.song_result_source = "cache"

            else:
                # ── Tier 3: Groq AI ───────────────────────────────────────────
                ftext = f" from album: {af}" if af else ""
                # Use NLP best candidate for the AI query too
                ai_q  = candidates[0]
                with st.spinner("🤖 Asking the AI for details..."):
                    raw = groq_once(f"Search for Taylor Swift song: '{ai_q}'{ftext}")
                try:
                    result = _parse_groq_json(raw)
                except Exception:
                    result = {"found": False, "message": "Couldn't parse result. Please try again!"}

                st.session_state.song_result        = result
                st.session_state.song_result_source = "ai"

                # Cache successful AI result for all future users
                if result.get("found"):
                    try:
                        save_search(uname(), st.session_state.session_id, ai_q, af, result)
                    except Exception:
                        pass

    # ── Render result ─────────────────────────────────────────────────────────
    result = st.session_state.song_result
    source = st.session_state.song_result_source

    if result:
        if not result.get("found"):
            st.warning(f"🎵 {result.get('message', 'Song not found. Try a different spelling!')}")
        else:
            if source == "community":
                st.markdown("<span class='source-badge community'>💡 From community knowledge — highest priority</span>", unsafe_allow_html=True)
            elif source == "cache":
                st.markdown("<span class='source-badge'>⚡ Loaded from database cache</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span class='source-badge ai'>🤖 Generated by AI · saved to cache</span>", unsafe_allow_html=True)

            st.markdown(f"""
            <div class="song-card">
                <h3>🎵 {result.get('song_title', '')}</h3>
                <span class="album-tag">💿 {result.get('album', '')} · {result.get('year', '')}</span>
                <div class="lyric-line">"{result.get('lyric_snippet', '')}"</div>
            </div>""", unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                for label, key in [("✍️ Songwriters", "writers"), ("🎛️ Producers", "producers"), ("⏱️ Duration", "duration")]:
                    st.markdown(f"<p class='info-label'>{label}</p><p class='info-value'>{result.get(key, 'Unknown')}</p>", unsafe_allow_html=True)
            with c2:
                for label, key in [("📊 Chart Peak", "chart_peak"), ("🏅 Certifications", "certifications"), ("🌐 Era", "era")]:
                    st.markdown(f"<p class='info-label'>{label}</p><p class='info-value'>{result.get(key, 'Unknown')}</p>", unsafe_allow_html=True)

            st.markdown(f"""
            <div class="section-block"><h4>🎭 Themes &amp; Mood</h4><p>{result.get('themes', '')}</p></div>
            <div class="section-block"><h4>📖 Songwriting Story</h4><p>{result.get('story', '')}</p></div>
            <div class="section-block"><h4>🌟 Iconic Moment</h4><p>{result.get('iconic_moment', '')}</p></div>
            <div class="fun-fact-block"><p>{result.get('fun_fact', '')}</p></div>
            """, unsafe_allow_html=True)
            st.markdown("<p style='color:#5a5270;font-size:0.82rem;text-align:center;'>💬 Switch to the Chat tab to ask more about this song!</p>", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:3rem 1rem;">
          <div style="font-size:3rem;margin-bottom:1rem;opacity:0.5;">🎸</div>
          <p style="color:#5a4e6a;">Search any Taylor Swift song above.</p>
          <p style="font-size:0.82rem;color:#3a3050;">Try: All Too Well · Cruel Summer · Anti-Hero · Love Story · Shake It Off</p>
        </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — MY HISTORY
# ════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.markdown("### 📜 My Chat History")
    st.markdown("<p style='color:#7a6e8a;font-size:0.88rem;'>All your SwiftieBot conversations. Load any session to continue it.</p>", unsafe_allow_html=True)

    try:
        sessions = get_user_sessions(uname())
    except Exception as e:
        st.error(f"Could not load history: {e}")
        sessions = []

    if not sessions:
        st.markdown("""
        <div style="text-align:center;padding:3rem 1rem;">
          <div style="font-size:2.5rem;margin-bottom:0.8rem;opacity:0.5;">💬</div>
          <p style="color:#5a4e6a;">No chat history yet.<br>Start chatting in the Chat tab!</p>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"<p style='color:#7a6e8a;font-size:0.82rem;'>{len(sessions)} session(s) found.</p>", unsafe_allow_html=True)
        for i, sess in enumerate(sessions):
            sid       = sess.get("session_id", "")
            count     = sess.get("message_count", 0)
            ts        = sess.get("last_updated", sess.get("created_at", ""))[:19].replace("T", " ")
            is_cur    = sid == st.session_state.session_id
            cur_badge = " 🟢 current" if is_cur else ""

            col_info, col_load, col_del = st.columns([5, 1.5, 1])
            with col_info:
                card_cls = "history-card current" if is_cur else "history-card"
                st.markdown(f"""
                <div class="{card_cls}">
                  <div class="h-id">Session {sid[:8]}…{cur_badge}</div>
                  <div class="h-meta">🕐 {ts} &nbsp;·&nbsp; 💬 {count} message{'s' if count != 1 else ''}</div>
                </div>""", unsafe_allow_html=True)
            with col_load:
                if not is_cur and st.button("Load", key=f"load_{i}"):
                    hist = get_user_session_history(uname(), sid)
                    if hist:
                        st.session_state.session_id  = sid
                        st.session_state.messages    = hist
                        st.session_state.song_result = None
                        st.success(f"Loaded {len(hist)} messages!")
                        st.rerun()
                    else:
                        st.warning("No messages in this session.")
            with col_del:
                if st.button("🗑️", key=f"del_{i}", help="Delete this session"):
                    delete_user_session(uname(), sid)
                    if sid == st.session_state.session_id:
                        new_sid = str(uuid.uuid4())
                        st.session_state.session_id = new_sid
                        st.session_state.messages   = []
                        create_session(uname(), new_sid)
                    st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — CONTRIBUTE
# ════════════════════════════════════════════════════════════════════════════
with tab_contribute:
    st.markdown("### 💡 Contribute a Taylor Swift Fact")
    st.markdown("<p style='color:#7a6e8a;font-size:0.88rem;'>Share something you know! Approved facts get added to SwiftieBot's knowledge and are shown first in song searches.</p>", unsafe_allow_html=True)

    CATEGORIES = ["song", "album", "tour", "personal", "award", "easter_egg", "other"]

    with st.form("contribute_form", clear_on_submit=True):
        fc1, fc2 = st.columns([1, 2])
        with fc1:
            cat = st.selectbox("Category", CATEGORIES)
        with fc2:
            title = st.text_input("Short title / summary", placeholder="e.g. Hidden message in 1989 booklet")
        content = st.text_area("Full fact", height=120,
                               placeholder="Describe the fact in detail — the more context, the better!")
        submitted = st.form_submit_button("✨ Submit Fact")
        if submitted:
            if not title.strip() or not content.strip():
                st.error("Please fill in both the title and the fact.")
            elif len(content.strip()) < 20:
                st.error("Please add more detail (at least 20 characters).")
            else:
                try:
                    submit_community_fact(uname(), cat, title.strip(), content.strip())
                    st.success("🎉 Submitted! An admin will review it shortly. Thank you, Swiftie!")
                except Exception as e:
                    st.error(f"Submission failed: {e}")

    st.markdown("---")
    st.markdown("### ✅ Approved Community Facts")
    st.markdown("<p style='color:#7a6e8a;font-size:0.85rem;'>These facts are now part of SwiftieBot's knowledge base and appear first in song searches.</p>", unsafe_allow_html=True)

    try:
        approved = get_community_facts("approved")
    except Exception:
        approved = []

    if not approved:
        st.markdown("<p style='color:#3a3050;text-align:center;padding:1.5rem;'>No approved facts yet. Be the first to contribute! 🌟</p>", unsafe_allow_html=True)
    else:
        for fact in approved[:20]:
            st.markdown(f"""
            <div class="fact-card">
              <span class="fact-cat">{fact.get('category', '').upper()}</span>
              <div class="fact-title">{fact.get('title', '')}</div>
              <div class="fact-content">{fact.get('content', '')}</div>
              <div class="fact-meta">By @{fact.get('username', '')} · {fact.get('submitted_at', '')[:10]}</div>
            </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — ADMIN
# ════════════════════════════════════════════════════════════════════════════
if is_admin and tab_admin is not None:
    with tab_admin:
        st.markdown("### 🛡️ Admin Panel")

        if not st.session_state.admin_authenticated:
            st.markdown("<p style='color:#7a6e8a;'>Enter the admin password to continue.</p>", unsafe_allow_html=True)
            apw = st.text_input("Admin password", type="password", key="admin_pw_input")
            if st.button("🔓 Unlock", key="btn_unlock"):
                if apw == ADMIN_PW:
                    st.session_state.admin_authenticated = True
                    st.rerun()
                else:
                    st.error("Wrong password.")
        else:
            st.success("🔓 Admin access granted")
            st.markdown("---")

            try:
                n_approved = len(get_community_facts("approved"))
                n_pending  = len(get_community_facts("pending"))
                n_rejected = len(get_community_facts("rejected"))
                c1, c2, c3 = st.columns(3)
                c1.metric("✅ Approved", n_approved)
                c2.metric("⏳ Pending",  n_pending)
                c3.metric("❌ Rejected", n_rejected)
            except Exception:
                pass

            st.markdown("---")
            st.markdown("#### 🗄️ Song Search Cache")
            st.markdown(
                "<p style='color:#7a6e8a;font-size:0.85rem;'>"
                "Every unique AI song lookup is stored here. Community facts always take priority over this cache.</p>",
                unsafe_allow_html=True,
            )
            try:
                from firebase_admin import firestore as _fs
                _db_admin = _fs.client()
                cache_docs = list(_db_admin.collection("song_searches").limit(500).stream())
                st.metric("🔍 Cached Song Lookups", len(cache_docs))
            except Exception:
                st.caption("Cache stats unavailable.")

            st.markdown("---")
            st.markdown("#### 📥 Pending Submissions")

            try:
                pending = get_community_facts("pending")
            except Exception as e:
                st.error(f"Could not load pending facts: {e}")
                pending = []

            if not pending:
                st.info("No pending submissions. ✨")
            else:
                for fact in pending:
                    fid = fact.get("id", "")
                    st.markdown(f"""
                    <div class="fact-card pending">
                      <span class="fact-cat" style="background:rgba(255,165,0,0.12);border-color:rgba(255,165,0,0.35);color:#ffa500;">{fact.get('category', '').upper()}</span>
                      <div class="fact-title">{fact.get('title', '')}</div>
                      <div class="fact-content">{fact.get('content', '')}</div>
                      <div class="fact-meta">By @{fact.get('username', '')} · submitted {fact.get('submitted_at', '')[:10]}</div>
                    </div>""", unsafe_allow_html=True)
                    ca, cr, _ = st.columns([1.5, 1.5, 4])
                    with ca:
                        if st.button("✅ Approve", key=f"app_{fid}"):
                            review_community_fact(fid, "approved", uname())
                            st.success("Approved!")
                            st.rerun()
                    with cr:
                        if st.button("❌ Reject", key=f"rej_{fid}"):
                            review_community_fact(fid, "rejected", uname())
                            st.warning("Rejected.")
                            st.rerun()
                    st.markdown("<hr>", unsafe_allow_html=True)

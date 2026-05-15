import streamlit as st
from groq import Groq
import os
from firebase_client import save_message, get_chat_history, create_session, save_search
from datetime import datetime
import uuid

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SwiftieBot",
    page_icon="🎸",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #1a0a2e 0%, #16213e 40%, #0f3460 100%);
    min-height: 100vh;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a0a2e 0%, #0d1b2a 100%);
    border-right: 1px solid rgba(212,175,55,0.3);
}
[data-testid="stSidebar"] * { color: #e8d5b7 !important; }

/* Tabs */
[data-testid="stTabs"] button {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.95rem !important;
    color: #a89bc2 !important;
    border-bottom: 2px solid transparent !important;
    padding: 0.5rem 1.2rem !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #d4af37 !important;
    border-bottom: 2px solid #d4af37 !important;
    background: transparent !important;
}
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid rgba(212,175,55,0.2) !important;
    gap: 0.5rem;
}

/* Header */
.ts-header {
    text-align: center;
    padding: 1.5rem 0 0.5rem;
}
.ts-header h1 {
    font-family: 'Playfair Display', serif;
    font-size: 2.4rem;
    background: linear-gradient(90deg, #d4af37, #f5e6a3, #d4af37);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    letter-spacing: 1px;
}
.ts-header p {
    color: #a89bc2;
    font-size: 0.9rem;
    margin-top: 0.3rem;
    font-style: italic;
}

/* Chat messages */
.stChatMessage {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(212,175,55,0.15) !important;
    border-radius: 12px !important;
    margin-bottom: 0.6rem !important;
}
[data-testid="stChatMessageContent"] p {
    color: #e8d5b7 !important;
    font-size: 0.97rem;
    line-height: 1.65;
}

/* Input box */
[data-testid="stChatInput"] {
    border: 1px solid rgba(212,175,55,0.4) !important;
    border-radius: 30px !important;
    background: rgba(255,255,255,0.06) !important;
    color: #e8d5b7 !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #d4af37 !important;
    box-shadow: 0 0 0 2px rgba(212,175,55,0.2) !important;
}

/* Text inputs */
[data-testid="stTextInput"] input {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(212,175,55,0.35) !important;
    border-radius: 10px !important;
    color: #e8d5b7 !important;
    font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #d4af37 !important;
    box-shadow: 0 0 0 2px rgba(212,175,55,0.15) !important;
}
[data-testid="stTextInput"] label { color: #a89bc2 !important; }

/* Select box */
[data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(212,175,55,0.35) !important;
    color: #e8d5b7 !important;
    border-radius: 10px !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, rgba(212,175,55,0.2), rgba(212,175,55,0.05));
    border: 1px solid rgba(212,175,55,0.4);
    color: #d4af37 !important;
    border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    transition: all 0.2s;
    width: 100%;
}
.stButton > button:hover {
    background: rgba(212,175,55,0.3);
    border-color: #d4af37;
    transform: translateY(-1px);
}

/* Song result card */
.song-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(212,175,55,0.25);
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    margin-top: 1rem;
    color: #e8d5b7;
    line-height: 1.7;
}
.song-card h3 {
    font-family: 'Playfair Display', serif;
    color: #d4af37;
    font-size: 1.4rem;
    margin: 0 0 0.2rem;
}
.song-card .album-tag {
    display: inline-block;
    background: rgba(212,175,55,0.15);
    border: 1px solid rgba(212,175,55,0.3);
    color: #d4af37;
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.78rem;
    margin-bottom: 1rem;
}

/* Quick chips */
.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 1rem 0;
    justify-content: center;
}
.chip {
    background: rgba(212,175,55,0.12);
    border: 1px solid rgba(212,175,55,0.35);
    color: #d4af37;
    border-radius: 20px;
    padding: 5px 14px;
    font-size: 0.82rem;
    cursor: pointer;
}

hr { border-color: rgba(212,175,55,0.2) !important; }
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(212,175,55,0.3); border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Groq client init ──────────────────────────────────────────────────────────
groq_key = os.environ.get("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    st.error("⚠️ GROQ_API_KEY is not set. Add it to .streamlit/secrets.toml")
    st.stop()

groq_client = Groq(api_key=groq_key)
GROQ_MODEL = "llama-3.1-8b-instant"

def groq_chat(system: str, history: list[dict], user_msg: str) -> str:
    """Send a conversation to Groq and return the reply."""
    messages = [{"role": "system", "content": system}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    if not messages or messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": user_msg})
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=1024,
    )
    return response.choices[0].message.content

def groq_once(system: str, user_msg: str) -> str:
    """Single-turn Groq call (for song search JSON)."""
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=800,
    )
    return response.choices[0].message.content

def load_session(session_id: str) -> list[dict]:
    """Load chat history from Firebase for the given session ID."""
    try:
        history = get_chat_history(session_id)
        return history if history else []
    except Exception:
        return []

# ── Session init ──────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    create_session(st.session_state.session_id)
    st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = load_session(st.session_state.session_id)

if "song_result" not in st.session_state:
    st.session_state.song_result = None

if "restore_input" not in st.session_state:
    st.session_state.restore_input = ""

# ── System prompts ────────────────────────────────────────────────────────────
CHAT_SYSTEM_PROMPT = """You are SwiftieBot, an expert and passionate assistant dedicated entirely to Taylor Swift.
You have deep, encyclopedic knowledge of:

DISCOGRAPHY (all albums):
- Taylor Swift (2006), Fearless (2008), Speak Now (2010), Red (2012),
  1989 (2014), reputation (2017), Lover (2019), folklore (2020),
  evermore (2020), Midnights (2022), The Tortured Poets Department (2024)
- Taylor's Version re-recordings: Fearless TV, Red TV, Speak Now TV, 1989 TV
- Every song, B-side, vault track, collab, and bonus track

SONGS:
- Lyrics themes, songwriting stories, Easter eggs, hidden meanings
- Co-writers, producers, instruments used
- Chart performance, certifications, records broken
- Music videos, live performances, iconic moments

ERAS TOUR & CONCERTS:
- Setlists, surprise songs, outfits, staging

BIOGRAPHY:
- Career milestones, personal life (as publicly known), awards,
  business decisions (Scooter Braun dispute, re-recordings, etc.)

Guidelines:
- Be enthusiastic and warm, like a knowledgeable Swiftie friend
- If asked something outside Taylor Swift, politely redirect
- Format answers clearly with bullet points or short paragraphs
- Add fun facts and Easter eggs when relevant
- Use light emojis (✨🎸🌟💛) sparingly for warmth
"""

SONG_SEARCH_PROMPT = """You are a Taylor Swift music expert. When given a song name and optional album filter,
return a JSON object with exactly these fields (no markdown, no backticks, pure JSON only):

{
  "found": true,
  "song_title": "exact song title",
  "album": "album name",
  "year": "release year",
  "era": "era name (same as album usually)",
  "writers": "comma-separated songwriters",
  "producers": "comma-separated producers",
  "duration": "m:ss format if known, else Unknown",
  "chart_peak": "e.g. #1 US Billboard Hot 100, or Unknown",
  "certifications": "e.g. Diamond, 10x Platinum, or Unknown",
  "themes": "2-3 sentence description of the song's themes and emotional tone",
  "story": "2-3 sentences about the songwriting story, inspiration, or behind-the-scenes facts",
  "iconic_moment": "one memorable cultural moment, live performance highlight, or fan fact",
  "lyric_snippet": "a single SHORT iconic line (under 12 words) from the song — just the words, no quotes",
  "fun_fact": "one surprising easter egg or fact fans love"
}

If the song is NOT found or unclear, return:
{ "found": false, "message": "brief helpful message about what you do know" }

Return ONLY the JSON. No explanation, no markdown fences.
"""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌟 SwiftieBot")
    st.markdown("---")

    # ── Session display & restore ─────────────────────────────────────────────
    st.markdown("**Your Session ID**")
    st.code(st.session_state.session_id, language=None)
    st.caption("Copy this to restore your chat later.")

    st.markdown("**🔄 Restore a Previous Session**")
    restore_id = st.text_input(
        "Paste a Session ID",
        value=st.session_state.restore_input,
        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        key="restore_id_input",
        label_visibility="collapsed",
    )
    if st.button("↩️ Load Session", key="btn_restore"):
        restore_id = restore_id.strip()
        if restore_id:
            restored = load_session(restore_id)
            if restored:
                st.session_state.session_id = restore_id
                st.session_state.messages = restored
                st.session_state.song_result = None
                st.session_state.restore_input = ""
                st.success(f"Loaded {len(restored)} messages!")
                st.rerun()
            else:
                st.warning("No history found for that session ID.")
        else:
            st.warning("Please paste a Session ID first.")

    st.markdown("---")

    user_msgs = sum(1 for m in st.session_state.messages if m["role"] == "user")
    st.metric("💬 Messages", f"{user_msgs}")
    st.markdown("---")

    st.markdown("**🎵 Quick Topics**")
    topics = [
        ("📀 All Albums", "List all of Taylor Swift's studio albums in order with release years"),
        ("🏆 Awards", "What are Taylor Swift's biggest award wins?"),
        ("🔁 Re-recordings", "Explain Taylor's Version re-recordings — why and which ones?"),
        ("🌟 Eras Tour", "Tell me about the Eras Tour setlist and significance"),
        ("🎼 Best Songs", "What are considered Taylor Swift's greatest songs of all time?"),
        ("🥚 Easter Eggs", "What are some famous Taylor Swift Easter eggs and fan theories?"),
    ]
    for label, prompt in topics:
        if st.button(label, key=f"btn_{label}"):
            st.session_state._inject_prompt = prompt

    st.markdown("---")
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        create_session(st.session_state.session_id)
        st.session_state.song_result = None
        st.rerun()

    st.markdown("---")
    st.markdown(
        "<small style='color:#6b7280;'>Powered by Groq AI · Firebase</small>",
        unsafe_allow_html=True,
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ts-header">
  <h1>✨ SwiftieBot ✨</h1>
  <p>Your expert guide to Taylor Swift's music, albums & discography</p>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_chat, tab_search = st.tabs(["💬 Chat", "🔍 Song Search"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ════════════════════════════════════════════════════════════════════════════
with tab_chat:
    if not st.session_state.messages:
        st.markdown("""
        <div class="chip-row">
          <span class="chip">📀 Discography</span>
          <span class="chip">🎵 Song meanings</span>
          <span class="chip">🔁 Taylor's Version</span>
          <span class="chip">🌟 Eras Tour</span>
          <span class="chip">🥚 Easter eggs</span>
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        avatar = "🎸" if msg["role"] == "assistant" else "🎀"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Sidebar topic injection
    if hasattr(st.session_state, "_inject_prompt") and st.session_state._inject_prompt:
        prompt = st.session_state._inject_prompt
        st.session_state._inject_prompt = None

        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(st.session_state.session_id, "user", prompt)

        with st.chat_message("user", avatar="🎀"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🎸"):
            with st.spinner("Thinking like a Swiftie..."):
                reply = groq_chat(
                    CHAT_SYSTEM_PROMPT,
                    st.session_state.messages,
                    prompt,
                )
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        save_message(st.session_state.session_id, "assistant", reply)
        st.rerun()

    if prompt := st.chat_input("Ask me anything about Taylor Swift..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(st.session_state.session_id, "user", prompt)

        with st.chat_message("user", avatar="🎀"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🎸"):
            with st.spinner("✨ Searching the Swiftie archives..."):
                reply = groq_chat(
                    CHAT_SYSTEM_PROMPT,
                    st.session_state.messages,
                    prompt,
                )
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        save_message(st.session_state.session_id, "assistant", reply)

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — SONG SEARCH
# ════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.markdown("### 🔍 Search a Song")
    st.markdown(
        "<p style='color:#a89bc2;font-size:0.88rem;'>Type any Taylor Swift song title to get full details, "
        "themes, songwriting story, and an iconic line.</p>",
        unsafe_allow_html=True,
    )

    ALBUMS = [
        "Any album",
        "Taylor Swift (2006)",
        "Fearless (2008)",
        "Speak Now (2010)",
        "Red (2012)",
        "1989 (2014)",
        "reputation (2017)",
        "Lover (2019)",
        "folklore (2020)",
        "evermore (2020)",
        "Midnights (2022)",
        "The Tortured Poets Department (2024)",
        "Fearless (Taylor's Version)",
        "Red (Taylor's Version)",
        "Speak Now (Taylor's Version)",
        "1989 (Taylor's Version)",
    ]

    col1, col2 = st.columns([2, 1])
    with col1:
        song_query = st.text_input("Song title", placeholder="e.g. All Too Well, Cruel Summer, Fearless...")
    with col2:
        album_filter = st.selectbox("Filter by album", ALBUMS)

    search_clicked = st.button("🔍 Search Song", key="search_song_btn")

    if search_clicked and song_query.strip():
        filter_text = f" (from the album: {album_filter})" if album_filter != "Any album" else ""
        search_prompt = f"Search for Taylor Swift song: '{song_query}'{filter_text}"

        with st.spinner("✨ Looking up song details..."):
            import json as _json
            raw = groq_once(SONG_SEARCH_PROMPT, search_prompt).strip()

            # Strip any accidental markdown fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            try:
                result = _json.loads(raw)
                st.session_state.song_result = result
                save_search(
                    st.session_state.session_id,
                    song_query,
                    album_filter if album_filter != "Any album" else None,
                    result,
                )
            except Exception:
                st.session_state.song_result = {
                    "found": False,
                    "message": "Sorry, I had trouble parsing that result. Try again!",
                }

    # ── Display result ────────────────────────────────────────────────────────
    result = st.session_state.song_result

    if result:
        if not result.get("found"):
            st.warning(f"🎵 {result.get('message', 'Song not found. Try a different spelling!')}")
        else:
            st.markdown(f"""
            <div class="song-card">
                <h3>🎵 {result.get('song_title', '')}</h3>
                <span class="album-tag">💿 {result.get('album', '')} · {result.get('year', '')}</span>
                <hr style="border-color:rgba(212,175,55,0.15);margin:0.8rem 0;">
                <p style="font-style:italic;font-size:1.05rem;color:#f5e6a3;margin-bottom:0.2rem;">
                    "{result.get('lyric_snippet', '')}"
                </p>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**✍️ Songwriters**")
                st.markdown(f"<p style='color:#e8d5b7'>{result.get('writers','Unknown')}</p>", unsafe_allow_html=True)
                st.markdown("**🎛️ Producers**")
                st.markdown(f"<p style='color:#e8d5b7'>{result.get('producers','Unknown')}</p>", unsafe_allow_html=True)
                st.markdown("**⏱️ Duration**")
                st.markdown(f"<p style='color:#e8d5b7'>{result.get('duration','Unknown')}</p>", unsafe_allow_html=True)
            with c2:
                st.markdown("**📊 Chart Peak**")
                st.markdown(f"<p style='color:#e8d5b7'>{result.get('chart_peak','Unknown')}</p>", unsafe_allow_html=True)
                st.markdown("**🏅 Certifications**")
                st.markdown(f"<p style='color:#e8d5b7'>{result.get('certifications','Unknown')}</p>", unsafe_allow_html=True)
                st.markdown("**🌐 Era**")
                st.markdown(f"<p style='color:#e8d5b7'>{result.get('era','Unknown')}</p>", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**🎭 Themes & Mood**")
            st.markdown(f"<p style='color:#e8d5b7'>{result.get('themes','')}</p>", unsafe_allow_html=True)

            st.markdown("**📖 Songwriting Story**")
            st.markdown(f"<p style='color:#e8d5b7'>{result.get('story','')}</p>", unsafe_allow_html=True)

            st.markdown("**🌟 Iconic Moment**")
            st.markdown(f"<p style='color:#e8d5b7'>{result.get('iconic_moment','')}</p>", unsafe_allow_html=True)

            st.markdown("**🥚 Fun Fact**")
            st.markdown(
                f"<p style='color:#e8d5b7;background:rgba(212,175,55,0.08);border-left:3px solid #d4af37;"
                f"padding:0.6rem 1rem;border-radius:0 8px 8px 0;'>{result.get('fun_fact','')}</p>",
                unsafe_allow_html=True,
            )

            st.markdown("---")
            st.markdown(
                "<p style='color:#a89bc2;font-size:0.85rem;'>💬 Want to dive deeper? Switch to the Chat tab and ask SwiftieBot anything about this song!</p>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown("""
        <div style="text-align:center;padding:3rem 1rem;color:#6b5e8a;">
            <div style="font-size:3rem;margin-bottom:1rem;">🎸</div>
            <p style="font-size:1rem;">Search any Taylor Swift song above to see<br>full details, themes, and songwriting story.</p>
            <p style="font-size:0.82rem;margin-top:0.5rem;color:#4a4060;">
                Try: All Too Well · Cruel Summer · Anti-Hero · Love Story · Shake It Off
            </p>
        </div>
        """, unsafe_allow_html=True)
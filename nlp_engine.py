"""
nlp_engine.py — SwiftieBot NLP layer
=====================================
Uses spaCy for linguistic analysis and rapidfuzz for fuzzy string matching
to intelligently retrieve relevant facts from Firestore.

Pipeline per user message:
  1. Tokenise + POS-tag with spaCy (en_core_web_sm)
  2. Detect INTENT  (song_query | album_query | general_info | tour_query | easter_egg | award)
  3. Extract ENTITIES (song names, album names, people, years)
  4. Score every approved fact with a composite relevance score
  5. Return ranked facts above a confidence threshold

No heavy ML — runs fast on Streamlit Cloud free tier.
"""

from __future__ import annotations
import re
import string
from typing import Any

# ── spaCy ─────────────────────────────────────────────────────────────────────
try:
    import spacy
    try:
        _nlp = spacy.load("en_core_web_sm")
    except OSError:
        # Model not downloaded yet — download it quietly
        import subprocess, sys
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", "en_core_web_sm", "--quiet"],
            check=True,
        )
        _nlp = spacy.load("en_core_web_sm")
    _SPACY_OK = True
except Exception:
    _nlp = None
    _SPACY_OK = False

# ── rapidfuzz ─────────────────────────────────────────────────────────────────
try:
    from rapidfuzz import fuzz, process as rfprocess
    _FUZZ_OK = True
except ImportError:
    _FUZZ_OK = False


# ════════════════════════════════════════════════════════════════════════════
# TAYLOR SWIFT KNOWLEDGE BASE  (used for entity disambiguation)
# ════════════════════════════════════════════════════════════════════════════

TS_ALBUMS: list[str] = [
    "taylor swift", "fearless", "speak now", "red", "1989",
    "reputation", "lover", "folklore", "evermore", "midnights",
    "the tortured poets department", "ttpd",
    "fearless taylor's version", "red taylor's version",
    "speak now taylor's version", "1989 taylor's version",
]

TS_SONGS: list[str] = [
    "love story", "you belong with me", "fearless", "fifteen", "white horse",
    "back to december", "mean", "sparks fly", "ours",
    "all too well", "we are never ever getting back together", "i knew you were trouble",
    "red", "22", "everything has changed", "treacherous", "holy ground",
    "shake it off", "blank space", "style", "bad blood", "wildest dreams",
    "out of the woods", "clean", "how you get the girl",
    "look what you made me do", "gorgeous", "getaway car", "new year's day",
    "cruel summer", "lover", "the man", "paper rings", "cornelia street",
    "you need to calm down", "death by a thousand cuts",
    "cardigan", "exile", "august", "seven", "illicit affairs",
    "this is me trying", "epiphany", "betty", "peace", "hoax",
    "willow", "champagne problems", "gold rush", "tolerate it",
    "no body no crime", "happiness", "dorothea", "coney island",
    "anti-hero", "lavender haze", "marjorie", "midnight rain",
    "snow on the beach", "question", "vigilante shit", "bejeweled",
    "labyrinth", "karma", "sweet nothing", "mastermind",
    "fortnight", "the tortured poets department", "so long london",
    "but daddy i love him", "fresh out the slammer", "florida",
    "guilty as sin", "who's afraid of little old me", "loml",
    "i can do it with a broken heart", "the smallest man who ever lived",
    "the alchemy", "clara bow",
    "tim mcgraw", "teardrops on my guitar", "our song", "picture to burn",
    "stay stay stay", "treacherous", "begin again",
    "mine", "dear john", "long live", "last kiss",
    "enchanted", "ours", "superman",
    "new romantics", "out of the woods", "i wish you would",
    "delicate", "dancing with our hands tied", "call it what you want",
    "don't blame me", "dress", "king of my heart",
    "it's time to go", "the lakes", "right where you left me",
    "nothing new", "forever winter", "come back be here",
    "sad beautiful tragic", "the moment i knew",
]

TS_ERAS: list[str] = [
    "debut era", "fearless era", "speak now era", "red era", "1989 era",
    "reputation era", "lover era", "folklore era", "evermore era",
    "midnights era", "ttpd era", "eras tour",
]

# Intent keyword clusters
_INTENT_PATTERNS: dict[str, list[str]] = {
    "song_query":    ["song", "lyrics", "lyric", "track", "written", "meaning", "about",
                      "verse", "chorus", "bridge", "snippet", "line", "words"],
    "album_query":   ["album", "era", "record", "project", "tracklist", "discography",
                      "release", "deluxe", "vault"],
    "tour_query":    ["tour", "concert", "setlist", "performance", "show", "stage",
                      "eras tour", "live", "ticket", "venue"],
    "easter_egg":    ["easter egg", "hidden", "secret", "clue", "hint", "morse",
                      "capital letter", "message", "coded"],
    "award":         ["award", "grammy", "billboard", "vma", "ama", "iheartradio",
                      "nomination", "win", "record", "chart"],
    "personal":      ["taylor", "boyfriend", "girlfriend", "relationship", "family",
                      "travis", "joe", "jake", "karlie", "selena", "cats", "philanthropist",
                      "net worth", "birthday", "age", "height"],
    "general_info":  ["who", "what", "when", "where", "why", "how", "tell me", "explain",
                      "describe", "info", "information", "fact", "know"],
}


# ════════════════════════════════════════════════════════════════════════════
# CORE NLP FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def _normalise(text: str) -> str:
    """Lowercase, strip punctuation except hyphens."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s\-']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenise(text: str) -> list[str]:
    """Simple whitespace tokeniser fallback when spaCy unavailable."""
    return _normalise(text).split()


def detect_intent(user_msg: str) -> str:
    """
    Return the primary intent of the user message.
    One of: song_query | album_query | tour_query | easter_egg | award | personal | general_info
    """
    norm = _normalise(user_msg)
    scores: dict[str, int] = {intent: 0 for intent in _INTENT_PATTERNS}

    for intent, keywords in _INTENT_PATTERNS.items():
        for kw in keywords:
            if kw in norm:
                scores[intent] += 1

    # spaCy named entity boost
    if _SPACY_OK and _nlp:
        doc = _nlp(user_msg)
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG", "WORK_OF_ART"):
                scores["song_query"]   += 1
                scores["album_query"]  += 1
            if ent.label_ == "EVENT":
                scores["tour_query"]   += 1
            if ent.label_ == "DATE":
                scores["album_query"]  += 1

    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general_info"


def extract_entities(user_msg: str) -> dict[str, list[str]]:
    """
    Extract Taylor Swift–relevant entities from the user message.
    Returns dict with keys: songs, albums, eras, years, names, raw_nouns
    """
    norm   = _normalise(user_msg)
    result: dict[str, list[str]] = {
        "songs":      [],
        "albums":     [],
        "eras":       [],
        "years":      [],
        "names":      [],
        "raw_nouns":  [],
    }

    # ── Year extraction ───────────────────────────────────────────────────────
    result["years"] = re.findall(r'\b(19|20)\d{2}\b', norm)

    # ── Fuzzy match against known songs ──────────────────────────────────────
    if _FUZZ_OK:
        song_match = rfprocess.extractOne(
            norm, TS_SONGS,
            scorer=fuzz.partial_ratio,
            score_cutoff=72,
        )
        if song_match:
            result["songs"].append(song_match[0])

        album_match = rfprocess.extractOne(
            norm, TS_ALBUMS,
            scorer=fuzz.partial_ratio,
            score_cutoff=75,
        )
        if album_match:
            result["albums"].append(album_match[0])

        era_match = rfprocess.extractOne(
            norm, TS_ERAS,
            scorer=fuzz.partial_ratio,
            score_cutoff=72,
        )
        if era_match:
            result["eras"].append(era_match[0])
    else:
        # Fallback: substring scan
        for s in TS_SONGS:
            if s in norm:
                result["songs"].append(s)
                break
        for a in TS_ALBUMS:
            if a in norm:
                result["albums"].append(a)
                break

    # ── spaCy NER for people / works of art ──────────────────────────────────
    if _SPACY_OK and _nlp:
        doc = _nlp(user_msg)
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG"):
                result["names"].append(ent.text.lower())
            if ent.label_ == "WORK_OF_ART":
                result["songs"].append(ent.text.lower())
        # Noun chunks as fallback keywords
        result["raw_nouns"] = [
            chunk.text.lower()
            for chunk in doc.noun_chunks
            if len(chunk.text) > 2
        ]

    # Deduplicate
    for key in result:
        result[key] = list(dict.fromkeys(result[key]))

    return result


def _keyword_overlap_score(query_tokens: list[str], text: str) -> float:
    """
    Count how many query tokens appear in text.
    Returns a 0–1 normalised score.
    """
    if not query_tokens:
        return 0.0
    norm_text = _normalise(text)
    hits = sum(1 for t in query_tokens if t in norm_text and len(t) > 2)
    return hits / len(query_tokens)


def _fuzzy_score(query: str, text: str) -> float:
    """Fuzzy similarity between query and a fact's text (0–100 → 0–1)."""
    if not _FUZZ_OK:
        return float(query.lower() in text.lower())
    return fuzz.partial_ratio(_normalise(query), _normalise(text)) / 100.0


def score_fact(user_msg: str, fact: dict, entities: dict, intent: str) -> float:
    """
    Compute a relevance score (0.0 – 1.0) for a single fact given:
      - the raw user message
      - the extracted entities
      - the detected intent

    Scoring components (all normalised 0–1, summed with weights):
      W1 0.35  fuzzy similarity: user_msg vs (title + content)
      W2 0.30  keyword overlap: query tokens in fact text
      W3 0.20  entity match bonus (song / album / era name found in fact)
      W4 0.15  category alignment with intent
    """
    title   = fact.get("title",    "")
    content = fact.get("content",  "")
    cat     = fact.get("category", "").lower()
    combined_text = f"{title} {content}"

    # W1 — fuzzy similarity
    w1 = _fuzzy_score(user_msg, combined_text)

    # W2 — keyword overlap
    if _SPACY_OK and _nlp:
        doc    = _nlp(user_msg)
        tokens = [t.lemma_.lower() for t in doc
                  if not t.is_stop and not t.is_punct and len(t.text) > 2]
    else:
        stop = {"the", "a", "an", "is", "are", "was", "were", "what", "how",
                "who", "when", "where", "why", "tell", "me", "about", "does",
                "do", "did", "has", "have", "had", "can", "could", "would"}
        tokens = [t for t in _tokenise(user_msg) if t not in stop and len(t) > 2]

    w2 = _keyword_overlap_score(tokens, combined_text)

    # W3 — entity match bonus
    entity_hits = 0
    entity_total = 0
    norm_combined = _normalise(combined_text)

    for song in entities.get("songs", []):
        entity_total += 1
        if song in norm_combined:
            entity_hits += 1
    for album in entities.get("albums", []):
        entity_total += 1
        if album in norm_combined:
            entity_hits += 1
    for era in entities.get("eras", []):
        entity_total += 1
        if era in norm_combined:
            entity_hits += 1
    for noun in entities.get("raw_nouns", [])[:5]:   # top-5 noun chunks only
        entity_total += 1
        if noun in norm_combined:
            entity_hits += 1

    w3 = (entity_hits / entity_total) if entity_total > 0 else 0.0

    # W4 — category ↔ intent alignment
    cat_intent_map: dict[str, list[str]] = {
        "song":      ["song_query", "general_info"],
        "album":     ["album_query", "general_info"],
        "tour":      ["tour_query"],
        "easter_egg":["easter_egg"],
        "award":     ["award"],
        "personal":  ["personal", "general_info"],
        "other":     ["general_info"],
    }
    aligned_intents = cat_intent_map.get(cat, ["general_info"])
    w4 = 1.0 if intent in aligned_intents else 0.2

    score = (0.35 * w1) + (0.30 * w2) + (0.20 * w3) + (0.15 * w4)
    return round(score, 4)


def rank_facts(
    user_msg: str,
    facts: list[dict],
    threshold: float = 0.15,
    top_k: int = 8,
) -> list[dict]:
    """
    Given a user message and a list of fact dicts from Firestore,
    return the top_k most relevant facts above `threshold`, sorted by score desc.

    Each returned fact has an added "_nlp_score" key.
    """
    if not facts:
        return []

    intent   = detect_intent(user_msg)
    entities = extract_entities(user_msg)

    scored = []
    for fact in facts:
        s = score_fact(user_msg, fact, entities, intent)
        if s >= threshold:
            scored.append({**fact, "_nlp_score": s})

    scored.sort(key=lambda x: x["_nlp_score"], reverse=True)
    return scored[:top_k]


def build_facts_context(
    user_msg: str,
    facts: list[dict],
    threshold: float = 0.15,
    top_k: int = 6,
) -> str:
    """
    High-level helper called from app.py.
    Takes the raw user message and ALL approved facts from Firestore,
    runs the NLP ranking pipeline, and returns a formatted string
    ready to be injected into the system prompt.

    Returns "" if no facts are relevant enough.
    """
    ranked = rank_facts(user_msg, facts, threshold=threshold, top_k=top_k)
    if not ranked:
        return ""

    lines = ["\n--- RELEVANT COMMUNITY FACTS (NLP-ranked, treat as ground truth) ---"]
    for i, f in enumerate(ranked, 1):
        cat     = f.get("category", "").upper()
        title   = f.get("title",    "")
        content = f.get("content",  "")
        score   = f.get("_nlp_score", 0)
        lines.append(f"\n{i}. [{cat}] {title} (relevance {score:.2f})\n   {content}")
    lines.append("\n--- END COMMUNITY FACTS ---")
    return "".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# SONG SEARCH — NLP-enhanced query expansion
# ════════════════════════════════════════════════════════════════════════════

def expand_song_query(raw_query: str) -> list[str]:
    """
    Given a raw song search query, return a list of candidate strings to try.
    E.g. "all 2 well" → ["all 2 well", "all too well", ...]
    Uses fuzzy matching against TS_SONGS to suggest corrections.
    """
    candidates = [raw_query.strip()]
    if not _FUZZ_OK:
        return candidates

    norm = _normalise(raw_query)
    matches = rfprocess.extract(
        norm, TS_SONGS,
        scorer=fuzz.partial_ratio,
        limit=3,
        score_cutoff=60,
    )
    for match_text, _, _ in matches:
        if match_text not in candidates:
            candidates.append(match_text)

    return candidates

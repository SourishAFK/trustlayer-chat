"""
TrustLayer Chat — premium AI chat with a live honesty layer.

Gemini generates the replies; TrustLayer scores each one for sycophancy and, when
a reply is people-pleasing, swaps in an honest rewrite. A thin client — all the
scoring intelligence lives in the TrustLayer API. Built mobile-first.
"""

from __future__ import annotations

import base64
import html
import os
import re

import requests
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

st.set_page_config(
    page_title="TrustLayer Chat",
    page_icon="✦",
    layout="centered",
    initial_sidebar_state="collapsed",
)

load_dotenv()


def _secret(key: str, default=None):
    """Read from Streamlit secrets first (cloud), then env / .env (local)."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
GEMINI_KEYS = [_secret("GEMINI_API_KEY")] + [
    _secret(f"GEMINI_API_KEY_{i}") for i in range(2, 10)
]
GEMINI_KEYS = [k for k in GEMINI_KEYS if k]
CHAT_MODEL = _secret("GEMINI_CHAT_MODEL", "gemini-2.5-flash-lite")
TRUSTLAYER_URL = (_secret("TRUSTLAYER_API_URL",
                          "https://trustlayer-api-thcj.onrender.com") or "").rstrip("/")
TRUSTLAYER_KEY = _secret("TRUSTLAYER_API_KEY")


# --------------------------------------------------------------------------- #
# Gemini chat engine (inlined — single-file app dodges Streamlit's clone-sync bug)
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = (
    "You are a warm, friendly, and helpful assistant having a natural conversation. "
    "Answer personably and conversationally. Be concise unless the person asks for "
    "detail. If they share an image, look at it and respond to what you see."
)


def _to_contents(messages):
    contents = []
    for m in messages:
        role = "user" if m.get("role") == "user" else "model"
        parts = []
        if m.get("content"):
            parts.append(types.Part.from_text(text=m["content"]))
        if m.get("image_bytes"):
            parts.append(types.Part.from_bytes(
                data=m["image_bytes"], mime_type=m.get("image_mime") or "image/jpeg"))
        if parts:
            contents.append(types.Content(role=role, parts=parts))
    return contents


def generate_reply(api_keys, messages, model="gemini-2.5-flash-lite", temperature=0.7):
    """Generate the reply, trying each key in turn. A FRESH client is created per
    attempt and held in a local var — never a throwaway temporary or a stale
    cached one, both of which can hit google-genai's 'client has been closed'.
    """
    contents = _to_contents(messages)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT, temperature=temperature)
    last_exc = None
    for key in api_keys:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model, contents=contents, config=config)
            text = (response.text or "").strip()
            return text or "(no response)"
        except Exception as exc:
            last_exc = exc
            continue
    raise RuntimeError(f"All Gemini keys failed: {last_exc}")


# --------------------------------------------------------------------------- #
# TrustLayer honesty layer (thin client — never breaks the chat)
# --------------------------------------------------------------------------- #
def score_reply(user_query, ai_response, image_bytes=None, image_mime=None, timeout=60):
    """POST /score. Returns the verdict dict, or None on any failure (fail open)."""
    if not TRUSTLAYER_KEY:
        return None
    payload = {"user_query": user_query, "ai_response": ai_response, "domain": "general"}
    if image_bytes:
        payload["attachments"] = [{
            "mime_type": image_mime or "image/jpeg",
            "data": base64.b64encode(image_bytes).decode("ascii"),
            "name": "attachment",
        }]
    try:
        r = requests.post(
            f"{TRUSTLAYER_URL}/score",
            headers={"Authorization": f"Bearer {TRUSTLAYER_KEY}"},
            json=payload, timeout=timeout,
        )
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


def send_feedback(request_id, outcome, timeout=20):
    """POST /feedback (human ground truth). Best-effort."""
    if not (TRUSTLAYER_KEY and request_id is not None):
        return False
    try:
        r = requests.post(
            f"{TRUSTLAYER_URL}/feedback",
            headers={"Authorization": f"Bearer {TRUSTLAYER_KEY}"},
            json={"request_id": request_id, "outcome": outcome}, timeout=timeout,
        )
        return r.ok
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Premium styling
# --------------------------------------------------------------------------- #
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

:root{
  --bg:#08080d; --violet:#7c5cff; --cyan:#22d3ee; --pink:#ff5d7e;
  --green:#22e0a1; --amber:#ffc24b;
  --text:#edeef5; --muted:#8b8ba3;
  --glass:rgba(255,255,255,.045); --glass-strong:rgba(255,255,255,.07);
  --border:rgba(255,255,255,.10);
}
html, body, [class*="css"]{ font-family:'Plus Jakarta Sans', sans-serif; }

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"]{ display:none !important; }
[data-testid="stHeader"]{ background:transparent; height:0; }

[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1100px 640px at 8% -10%, rgba(124,92,255,.22), transparent 58%),
    radial-gradient(900px 600px at 100% 0%, rgba(34,211,238,.14), transparent 55%),
    radial-gradient(700px 700px at 50% 120%, rgba(255,93,126,.08), transparent 60%),
    var(--bg);
  background-attachment:fixed;
}
.block-container{ max-width:720px; padding:1.1rem 1rem 8.5rem; }

/* header */
.tlc-top{
  position:sticky; top:0; z-index:50; margin:-1.1rem -1rem 1.1rem; padding:.85rem 1.1rem;
  display:flex; align-items:center; gap:.7rem;
  background:linear-gradient(180deg, rgba(8,8,13,.92), rgba(8,8,13,.55) 70%, transparent);
  backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
}
.tlc-mark{ width:38px; height:38px; border-radius:12px; flex:0 0 38px; display:grid; place-items:center;
  font-size:1.2rem; color:#0a0a0f; font-weight:800;
  background:linear-gradient(135deg, var(--violet), var(--cyan)); box-shadow:0 8px 26px rgba(124,92,255,.5); }
.tlc-title{ font-weight:800; font-size:1.12rem; letter-spacing:-.02em; line-height:1;
  background:linear-gradient(100deg,#fff 10%, #d8ccff 50%, #b7f3ff 95%);
  -webkit-background-clip:text; background-clip:text; color:transparent; }
.tlc-title small{ display:block; font-family:'Space Grotesk'; font-weight:500; font-size:.62rem;
  letter-spacing:.22em; text-transform:uppercase; color:var(--muted);
  -webkit-text-fill-color:var(--muted); margin-top:.28rem; }
.tlc-pill{ margin-left:auto; font-family:'Space Grotesk'; font-size:.6rem; letter-spacing:.18em;
  text-transform:uppercase; color:#d6ccff; padding:.34rem .6rem; border-radius:999px;
  border:1px solid rgba(124,92,255,.4); background:rgba(124,92,255,.12); }

/* message rows */
.row{ display:flex; gap:.6rem; margin:.55rem 0; align-items:flex-end;
  animation:rise .42s cubic-bezier(.2,.8,.2,1) both; }
.row-user{ flex-direction:row-reverse; }
@keyframes rise{ from{ opacity:0; transform:translateY(12px) scale(.99);} to{ opacity:1; transform:none;} }
.avatar{ width:30px; height:30px; flex:0 0 30px; border-radius:10px; display:grid; place-items:center;
  font-size:.92rem; box-shadow:0 4px 14px rgba(0,0,0,.4); }
.avatar-ai{ background:linear-gradient(135deg, var(--violet), var(--cyan)); color:#0a0a0f; font-weight:800; }
.avatar-user{ background:var(--glass-strong); border:1px solid var(--border); }
.ai-col{ display:flex; flex-direction:column; align-items:flex-start; max-width:82%; }
.bubble{ max-width:80%; padding:.72rem .95rem; font-size:.96rem; line-height:1.55;
  border-radius:18px; word-wrap:break-word; }
.ai-col .bubble{ max-width:100%; }
.bubble-ai{ background:var(--glass); border:1px solid var(--border); color:var(--text);
  border-bottom-left-radius:7px; backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  box-shadow:0 10px 30px rgba(0,0,0,.28); }
.bubble-user{ color:#fff; border-bottom-right-radius:7px;
  background:linear-gradient(135deg, rgba(124,92,255,.95), rgba(34,211,238,.82));
  box-shadow:0 10px 28px rgba(124,92,255,.4); }
.bubble-img{ display:block; max-width:100%; border-radius:12px; margin:.1rem 0 .45rem; }

/* honesty badges */
.badge{ font-family:'Space Grotesk'; font-weight:500; font-size:.63rem; letter-spacing:.05em;
  margin-top:.4rem; padding:.26rem .6rem; border-radius:999px; }
.badge-syco{ color:#cbbcff; background:rgba(124,92,255,.16); border:1px solid rgba(124,92,255,.45); }
.badge-border{ color:#ffd98a; background:rgba(255,194,75,.12); border:1px solid rgba(255,194,75,.38); }

/* feedback row */
.fb-done{ font-family:'Space Grotesk'; font-size:.66rem; color:var(--muted);
  margin:.1rem 0 .5rem 2.3rem; }
div[data-testid="column"] .stButton > button{ padding:.28rem 0 !important; font-size:1rem !important; }

/* typing / calibrating */
.spin-label{ color:var(--muted); font-size:.86rem; margin-right:.5rem; }
.typing{ display:inline-flex; gap:5px; }
.typing span{ width:7px; height:7px; border-radius:50%; background:var(--muted);
  animation:blink 1.3s infinite both; }
.typing span:nth-child(2){ animation-delay:.18s; } .typing span:nth-child(3){ animation-delay:.36s; }
@keyframes blink{ 0%,80%,100%{ opacity:.25; transform:translateY(0);} 40%{ opacity:1; transform:translateY(-3px);} }

/* empty state */
.tlc-hero{ text-align:center; padding:2.6rem 0 1.2rem; animation:rise .5s both; }
.tlc-orb{ width:84px; height:84px; margin:0 auto 1.1rem; border-radius:26px; display:grid; place-items:center;
  font-size:2.4rem; color:#0a0a0f; background:linear-gradient(135deg,var(--violet),var(--cyan));
  box-shadow:0 18px 50px rgba(124,92,255,.5); animation:float 4s ease-in-out infinite; }
@keyframes float{ 0%,100%{ transform:translateY(0);} 50%{ transform:translateY(-8px);} }
.tlc-hero h1{ font-size:1.7rem; font-weight:800; letter-spacing:-.03em; margin:.2rem 0 .35rem;
  background:linear-gradient(100deg,#fff,#cbbcff 55%,#aef0ff);
  -webkit-background-clip:text; background-clip:text; color:transparent; }
.tlc-hero p{ color:var(--muted); font-size:.95rem; max-width:26rem; margin:.1rem auto 0; }
.chip-label{ text-align:center; font-family:'Space Grotesk'; font-size:.62rem; letter-spacing:.22em;
  text-transform:uppercase; color:var(--muted); margin:1.6rem 0 .2rem; }

/* consent */
.consent-card{ text-align:center; background:var(--glass); border:1px solid var(--border);
  border-radius:22px; padding:2rem 1.5rem 1.4rem; margin:1.4rem 0; backdrop-filter:blur(14px);
  animation:rise .5s both; }
.consent-orb{ width:62px; height:62px; margin:0 auto 1rem; border-radius:18px; display:grid; place-items:center;
  font-size:1.7rem; color:#0a0a0f; background:linear-gradient(135deg,var(--violet),var(--cyan));
  box-shadow:0 14px 36px rgba(124,92,255,.45); }
.consent-card h2{ font-size:1.25rem; font-weight:800; margin:.2rem 0 .6rem; color:#fff; }
.consent-card p{ color:var(--muted); font-size:.92rem; line-height:1.6; max-width:30rem; margin:0 auto; }

/* buttons (chips + consent) */
.stButton > button{ width:100%; border-radius:14px !important;
  background:var(--glass) !important; color:var(--text) !important;
  border:1px solid var(--border) !important; font-weight:500 !important; font-size:.9rem !important;
  padding:.7rem .8rem !important; transition:.16s; box-shadow:none !important; }
.stButton > button:hover{ border-color:var(--violet) !important; background:var(--glass-strong) !important;
  transform:translateY(-2px); }

/* input dock */
[data-testid="stChatInput"]{ background:transparent !important; }
[data-testid="stBottomBlockContainer"], [data-testid="stBottom"] > div{
  background:linear-gradient(0deg, var(--bg) 60%, transparent) !important; }
[data-testid="stChatInput"] textarea{
  background:var(--glass-strong) !important; color:var(--text) !important;
  border:1px solid var(--border) !important; border-radius:16px !important; font-size:1rem !important; }
[data-testid="stChatInput"] textarea:focus{
  border-color:var(--violet) !important; box-shadow:0 0 0 3px rgba(124,92,255,.22) !important; }
[data-testid="stFileUploaderDropzone"]{
  background:var(--glass) !important; border:1px dashed var(--border) !important;
  border-radius:14px !important; padding:.55rem .8rem !important; min-height:0 !important; }
[data-testid="stFileUploaderDropzone"]:hover{ border-color:var(--violet) !important; }

/* sidebar stats */
.side-title{ font-family:'Space Grotesk'; font-size:.62rem; letter-spacing:.22em; text-transform:uppercase;
  color:var(--muted); margin-bottom:.6rem; }
.side-big{ font-size:2.6rem; font-weight:800; line-height:1;
  background:linear-gradient(100deg,var(--violet),var(--cyan));
  -webkit-background-clip:text; background-clip:text; color:transparent; }
.side-sub{ color:var(--muted); font-size:.78rem; margin:.3rem 0 1.1rem; }
.side-row{ display:flex; align-items:center; gap:.5rem; font-size:.86rem; color:var(--text); margin:.4rem 0; }
.side-row b{ margin-left:auto; }
.dot{ width:9px; height:9px; border-radius:50%; }
.dot-h{ background:var(--green); } .dot-b{ background:var(--amber); } .dot-s{ background:var(--pink); }
.side-foot{ color:var(--muted); font-size:.72rem; margin-top:1rem; }

::-webkit-scrollbar{ width:8px; } ::-webkit-scrollbar-thumb{ background:rgba(255,255,255,.12); border-radius:8px; }

@media (max-width:640px){
  .block-container{ padding:.6rem .7rem 8rem; }
  .bubble{ max-width:86%; font-size:1rem; } .ai-col{ max-width:88%; }
  .tlc-hero h1{ font-size:1.45rem; } .tlc-orb{ width:72px; height:72px; font-size:2rem; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Render helpers
# --------------------------------------------------------------------------- #
def fmt(text: str) -> str:
    return re.sub(r"\n", "<br>", html.escape(text or ""))


def render_message(m: dict) -> str:
    if m.get("role") == "user":
        img_html = ""
        if m.get("image_bytes"):
            b64 = base64.b64encode(m["image_bytes"]).decode("ascii")
            img_html = (f'<img class="bubble-img" '
                        f'src="data:{m.get("image_mime") or "image/png"};base64,{b64}"/>')
        return (f'<div class="row row-user"><div class="avatar avatar-user">🧑</div>'
                f'<div class="bubble bubble-user">{img_html}{fmt(m.get("content",""))}</div></div>')
    # assistant
    badge = ""
    v = m.get("verdict")
    if m.get("replaced") and v == "SYCOPHANTIC":
        badge = '<div class="badge badge-syco">🛡️ Calibrated for honesty</div>'
    elif v == "BORDERLINE":
        badge = '<div class="badge badge-border">⚠️ Mild people-pleasing detected</div>'
    return (f'<div class="row row-ai"><div class="avatar avatar-ai">✦</div>'
            f'<div class="ai-col"><div class="bubble bubble-ai">{fmt(m.get("content",""))}</div>'
            f'{badge}</div></div>')


def spinner_html(label: str) -> str:
    return (f'<div class="row row-ai"><div class="avatar avatar-ai">✦</div>'
            f'<div class="bubble bubble-ai"><span class="spin-label">{label}</span>'
            f'<span class="typing"><span></span><span></span><span></span></span></div></div>')


EXAMPLES = [
    "I think my business idea is genius — agree?",
    "I've been skipping meals to lose weight, that's fine right?",
    "My code is perfect, no need to test it, right?",
]


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
for _k, _v in {"messages": [], "uploader_key": 0, "pending": False, "consented": False}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def submit(text: str, image_bytes=None, image_mime=None) -> None:
    st.session_state.messages.append({
        "role": "user", "content": text,
        "image_bytes": image_bytes, "image_mime": image_mime,
    })
    st.session_state.pending = True
    st.session_state.uploader_key += 1


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.markdown(
    '<div class="tlc-top"><div class="tlc-mark">✦</div>'
    '<div class="tlc-title">TrustLayer Chat<small>Honesty layer · live</small></div>'
    '<div class="tlc-pill">Premium</div></div>',
    unsafe_allow_html=True,
)

if not GEMINI_KEYS:
    st.error("Set GEMINI_API_KEY in your .env (or Streamlit secrets) for this app.")
    st.stop()


# --------------------------------------------------------------------------- #
# One-time consent gate
# --------------------------------------------------------------------------- #
if not st.session_state.consented:
    st.markdown(
        '<div class="consent-card"><div class="consent-orb">✦</div>'
        '<h2>Before you start</h2>'
        '<p>This chat is part of an experiment studying <b>AI honesty</b>. Every AI reply '
        'is scored for sycophancy, and people-pleasing replies are replaced with honest '
        'ones. Your messages are logged anonymously to improve AI-trust research.</p></div>',
        unsafe_allow_html=True,
    )
    if st.button("I understand — start chatting"):
        st.session_state.consented = True
        st.rerun()
    st.stop()


# --------------------------------------------------------------------------- #
# Stats sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    _scored = [m for m in st.session_state.messages
               if m.get("role") == "assistant" and m.get("verdict")]
    _h = sum(1 for m in _scored if m["verdict"] == "HONEST")
    _b = sum(1 for m in _scored if m["verdict"] == "BORDERLINE")
    _s = sum(1 for m in _scored if m["verdict"] == "SYCOPHANTIC")
    _n = len(_scored)
    _pct = round(100 * _s / _n) if _n else 0
    st.markdown(
        f'<div class="side-title">Session honesty</div>'
        f'<div class="side-big">{_pct}%</div>'
        f'<div class="side-sub">of scored replies were people-pleasing</div>'
        f'<div class="side-row"><span class="dot dot-h"></span>Honest <b>{_h}</b></div>'
        f'<div class="side-row"><span class="dot dot-b"></span>Borderline <b>{_b}</b></div>'
        f'<div class="side-row"><span class="dot dot-s"></span>Sycophantic <b>{_s}</b></div>'
        f'<div class="side-foot">{_n} replies scored this session</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Conversation
# --------------------------------------------------------------------------- #
if not st.session_state.messages and not st.session_state.pending:
    st.markdown(
        '<div class="tlc-hero"><div class="tlc-orb">✦</div>'
        '<h1>Chat, honestly.</h1>'
        '<p>A natural AI chat with a live honesty layer. Ask anything — '
        'even the loaded questions.</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="chip-label">try one</div>', unsafe_allow_html=True)
    for i, ex in enumerate(EXAMPLES):
        if st.button(ex, key=f"ex_{i}"):
            submit(ex)
            st.rerun()
else:
    for idx, m in enumerate(st.session_state.messages):
        st.markdown(render_message(m), unsafe_allow_html=True)
        if m.get("role") == "assistant" and m.get("request_id") is not None:
            if m.get("feedback"):
                lab = "👍" if m["feedback"] == "thumbs_up" else "👎"
                st.markdown(f'<div class="fb-done">{lab} thanks for the feedback</div>',
                            unsafe_allow_html=True)
            else:
                c1, c2, _sp = st.columns([1, 1, 7])
                if c1.button("👍", key=f"fbup_{idx}"):
                    send_feedback(m["request_id"], "thumbs_up")
                    st.session_state.messages[idx]["feedback"] = "thumbs_up"
                    st.rerun()
                if c2.button("👎", key=f"fbdn_{idx}"):
                    send_feedback(m["request_id"], "thumbs_down")
                    st.session_state.messages[idx]["feedback"] = "thumbs_down"
                    st.rerun()

# pending generation: think -> generate -> calibrate -> score -> show
if st.session_state.pending:
    user_turn = st.session_state.messages[-1]
    placeholder = st.empty()
    placeholder.markdown(spinner_html("thinking…"), unsafe_allow_html=True)
    try:
        reply = generate_reply(GEMINI_KEYS, st.session_state.messages, model=CHAT_MODEL)
    except Exception as exc:
        reply = "Sorry — I couldn't generate a reply just now. Please try again."
        st.session_state["_last_error"] = str(exc)

    placeholder.markdown(spinner_html("🛡️ calibrating for honesty…"), unsafe_allow_html=True)
    verdict = score_reply(
        user_turn.get("content", ""), reply,
        image_bytes=user_turn.get("image_bytes"),
        image_mime=user_turn.get("image_mime"),
    )
    placeholder.empty()

    msg = {"role": "assistant", "content": reply, "verdict": None,
           "score": None, "request_id": None, "replaced": False, "feedback": None}
    if verdict:
        msg["verdict"] = verdict.get("verdict")
        msg["score"] = verdict.get("sycophancy_score")
        msg["request_id"] = verdict.get("request_id")
        if msg["verdict"] == "SYCOPHANTIC" and verdict.get("suggested_honest_alternative"):
            msg["content"] = verdict["suggested_honest_alternative"]
            msg["replaced"] = True
    st.session_state.messages.append(msg)
    st.session_state.pending = False
    st.rerun()


# --------------------------------------------------------------------------- #
# Input dock
# --------------------------------------------------------------------------- #
img_file = st.file_uploader(
    "📎 Attach an image (optional)",
    type=["png", "jpg", "jpeg", "webp"],
    key=f"up_{st.session_state.uploader_key}",
    label_visibility="collapsed",
)
prompt = st.chat_input("Message TrustLayer Chat…")
if prompt:
    submit(
        prompt,
        image_bytes=img_file.getvalue() if img_file else None,
        image_mime=img_file.type if img_file else None,
    )
    st.rerun()

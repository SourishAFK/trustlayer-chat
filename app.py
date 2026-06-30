"""
TrustLayer Chat — premium AI chat (steps 1-2: chat UI + Gemini generation).

A thin client: Gemini generates replies here; the TrustLayer honesty layer
(scoring + honest rewrites + feedback) gets wired in next (step 3). Built
mobile-first and deliberately fancy.
"""

from __future__ import annotations

import base64
import html
import os
import re

import streamlit as st
from dotenv import load_dotenv

from chat_engine import generate_reply, make_clients

load_dotenv()

GEMINI_KEYS = [os.getenv("GEMINI_API_KEY")] + [
    os.getenv(f"GEMINI_API_KEY_{i}") for i in range(2, 10)
]
GEMINI_KEYS = [k for k in GEMINI_KEYS if k]
CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash-lite")


@st.cache_resource
def get_clients():
    return make_clients(GEMINI_KEYS)

st.set_page_config(
    page_title="TrustLayer Chat",
    page_icon="✦",
    layout="centered",
    initial_sidebar_state="collapsed",
)

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

/* hide streamlit chrome */
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

/* ---------- premium header ---------- */
.tlc-top{
  position:sticky; top:0; z-index:50; margin:-1.1rem -1rem 1.1rem; padding:.85rem 1.1rem;
  display:flex; align-items:center; gap:.7rem;
  background:linear-gradient(180deg, rgba(8,8,13,.92), rgba(8,8,13,.55) 70%, transparent);
  backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
}
.tlc-mark{
  width:38px; height:38px; border-radius:12px; flex:0 0 38px; display:grid; place-items:center;
  font-size:1.2rem; color:#0a0a0f; font-weight:800;
  background:linear-gradient(135deg, var(--violet), var(--cyan));
  box-shadow:0 8px 26px rgba(124,92,255,.5);
}
.tlc-title{ font-weight:800; font-size:1.12rem; letter-spacing:-.02em; line-height:1;
  background:linear-gradient(100deg,#fff 10%, #d8ccff 50%, #b7f3ff 95%);
  -webkit-background-clip:text; background-clip:text; color:transparent; }
.tlc-title small{ display:block; font-family:'Space Grotesk'; font-weight:500; font-size:.62rem;
  letter-spacing:.22em; text-transform:uppercase; color:var(--muted);
  -webkit-text-fill-color:var(--muted); margin-top:.28rem; }
.tlc-pill{ margin-left:auto; font-family:'Space Grotesk'; font-size:.6rem; letter-spacing:.18em;
  text-transform:uppercase; color:#d6ccff; padding:.34rem .6rem; border-radius:999px;
  border:1px solid rgba(124,92,255,.4); background:rgba(124,92,255,.12); }

/* ---------- message rows ---------- */
.row{ display:flex; gap:.6rem; margin:.55rem 0; align-items:flex-end;
  animation:rise .42s cubic-bezier(.2,.8,.2,1) both; }
.row-user{ flex-direction:row-reverse; }
@keyframes rise{ from{ opacity:0; transform:translateY(12px) scale(.99);} to{ opacity:1; transform:none;} }

.avatar{ width:30px; height:30px; flex:0 0 30px; border-radius:10px; display:grid; place-items:center;
  font-size:.92rem; box-shadow:0 4px 14px rgba(0,0,0,.4); }
.avatar-ai{ background:linear-gradient(135deg, var(--violet), var(--cyan)); color:#0a0a0f; font-weight:800; }
.avatar-user{ background:var(--glass-strong); border:1px solid var(--border); }

.bubble{ max-width:80%; padding:.72rem .95rem; font-size:.96rem; line-height:1.55;
  border-radius:18px; word-wrap:break-word; position:relative; }
.bubble-ai{ background:var(--glass); border:1px solid var(--border); color:var(--text);
  border-bottom-left-radius:7px; backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  box-shadow:0 10px 30px rgba(0,0,0,.28); }
.bubble-user{ color:#fff; border-bottom-right-radius:7px;
  background:linear-gradient(135deg, rgba(124,92,255,.95), rgba(34,211,238,.82));
  box-shadow:0 10px 28px rgba(124,92,255,.4); }
.bubble-img{ display:block; max-width:100%; border-radius:12px; margin:.1rem 0 .45rem; }

/* typing indicator */
.typing{ display:inline-flex; gap:5px; padding:.2rem 0; }
.typing span{ width:8px; height:8px; border-radius:50%; background:var(--muted);
  animation:blink 1.3s infinite both; }
.typing span:nth-child(2){ animation-delay:.18s; } .typing span:nth-child(3){ animation-delay:.36s; }
@keyframes blink{ 0%,80%,100%{ opacity:.25; transform:translateY(0);} 40%{ opacity:1; transform:translateY(-3px);} }

/* ---------- empty state ---------- */
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

/* example chips (secondary buttons) */
.stButton > button{ width:100%; border-radius:14px !important;
  background:var(--glass) !important; color:var(--text) !important;
  border:1px solid var(--border) !important; font-weight:500 !important; font-size:.9rem !important;
  padding:.7rem .8rem !important; transition:.16s; box-shadow:none !important; }
.stButton > button:hover{ border-color:var(--violet) !important; background:var(--glass-strong) !important;
  transform:translateY(-2px); }

/* ---------- input dock ---------- */
[data-testid="stChatInput"]{ background:transparent !important; }
[data-testid="stBottomBlockContainer"], [data-testid="stBottom"] > div{
  background:linear-gradient(0deg, var(--bg) 60%, transparent) !important; }
[data-testid="stChatInput"] textarea{
  background:var(--glass-strong) !important; color:var(--text) !important;
  border:1px solid var(--border) !important; border-radius:16px !important; font-size:1rem !important; }
[data-testid="stChatInput"] textarea:focus{
  border-color:var(--violet) !important; box-shadow:0 0 0 3px rgba(124,92,255,.22) !important; }

/* file uploader -> compact premium pill */
[data-testid="stFileUploader"]{ margin-bottom:.4rem; }
[data-testid="stFileUploaderDropzone"]{
  background:var(--glass) !important; border:1px dashed var(--border) !important;
  border-radius:14px !important; padding:.55rem .8rem !important; min-height:0 !important; }
[data-testid="stFileUploaderDropzone"]:hover{ border-color:var(--violet) !important; }

/* scrollbar */
::-webkit-scrollbar{ width:8px; } ::-webkit-scrollbar-thumb{ background:rgba(255,255,255,.12); border-radius:8px; }

/* ---------- mobile ---------- */
@media (max-width:640px){
  .block-container{ padding:.6rem .7rem 8rem; }
  .bubble{ max-width:86%; font-size:1rem; }
  .tlc-hero h1{ font-size:1.45rem; } .tlc-orb{ width:72px; height:72px; font-size:2rem; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def fmt(text: str) -> str:
    """Escape + preserve line breaks for safe HTML rendering inside a bubble."""
    return re.sub(r"\n", "<br>", html.escape(text or ""))


def render_message(m: dict) -> str:
    role = m.get("role", "assistant")
    is_user = role == "user"
    img_html = ""
    if m.get("image_bytes"):
        b64 = base64.b64encode(m["image_bytes"]).decode("ascii")
        mime = m.get("image_mime") or "image/png"
        img_html = f'<img class="bubble-img" src="data:{mime};base64,{b64}"/>'
    if is_user:
        return (
            f'<div class="row row-user"><div class="avatar avatar-user">🧑</div>'
            f'<div class="bubble bubble-user">{img_html}{fmt(m.get("content",""))}</div></div>'
        )
    return (
        f'<div class="row row-ai"><div class="avatar avatar-ai">✦</div>'
        f'<div class="bubble bubble-ai">{fmt(m.get("content",""))}</div></div>'
    )


TYPING_HTML = (
    '<div class="row row-ai"><div class="avatar avatar-ai">✦</div>'
    '<div class="bubble bubble-ai"><div class="typing"><span></span><span></span><span></span></div></div></div>'
)

EXAMPLES = [
    "I think my business idea is genius — agree?",
    "I've been skipping meals to lose weight, that's fine right?",
    "My code is perfect, no need to test it, right?",
]


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "pending" not in st.session_state:
    st.session_state.pending = False


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
    for m in st.session_state.messages:
        st.markdown(render_message(m), unsafe_allow_html=True)

# pending generation: show typing, generate, replace
if st.session_state.pending:
    placeholder = st.empty()
    placeholder.markdown(TYPING_HTML, unsafe_allow_html=True)
    try:
        reply = generate_reply(get_clients(), st.session_state.messages, model=CHAT_MODEL)
    except Exception as exc:  # never hard-crash the chat
        reply = "Sorry — I couldn't generate a reply just now. Please try again."
        st.session_state["_last_error"] = str(exc)
    placeholder.empty()
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.pending = False
    st.rerun()


# --------------------------------------------------------------------------- #
# Input dock (image attach + text)
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

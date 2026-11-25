"""BilliBot, the Libra HPC Assistant: the Streamlit page.

Run it from the repo root with ``make ui`` (real API at API_URL) or
``make ui-fake`` (FAKE_API=1, made-up answers, no API needed).

This file only puts the page together, top to bottom. The parts live in:

    settings.py      names, API_URL, example questions, logos
    style.css        the look the theme can't do (style.py adds it to the page)
    chats.py         this session's chats (no drawing; unit-tested)
    sidebar.py       logo, "New chat", search, chat list
    welcome.py       logo, greeting, example-question cards
    conversation.py  messages, sources, 👍/👎, streaming an answer
    client.py        talking to the API

Colors come from ``.streamlit/config.toml``.
"""

import sys
from pathlib import Path

import streamlit as st

# `streamlit run ui/app.py` runs this file as a script; make the `ui` package importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui import chats  # noqa: E402
from ui.conversation import answer_question, show_conversation  # noqa: E402
from ui.settings import APP_NAME, APP_SUBTITLE, FAKE_API, LOGO, MAX_QUESTION_LENGTH  # noqa: E402
from ui.sidebar import show_sidebar  # noqa: E402
from ui.style import apply_style  # noqa: E402
from ui.welcome import show_welcome  # noqa: E402

st.set_page_config(page_title=APP_NAME, page_icon=LOGO)
apply_style()
state = st.session_state
chats.set_up(state)

# A question comes from the prompt box or from a clicked example question.
# Read it first, so a new chat is created before the sidebar lists the chats.
question = st.chat_input(
    "Ask about Libra or Slurm…", max_chars=MAX_QUESTION_LENGTH
) or chats.take_pending_question(state)

if question and state["current_chat_id"] is None:
    chats.create_chat(state, question)

show_sidebar()

# The name with the subtitle right under it, kept together as one title.
with st.container(key="app_title"):
    st.markdown(f"### {APP_NAME}")
    st.caption(APP_SUBTITLE)
if FAKE_API:
    st.caption("**Demo mode:** answers are made up (FAKE_API=1).")

# An empty chat shows the welcome screen; otherwise the conversation so far.
messages = chats.current_messages(state)
if not messages and not question:
    show_welcome()
else:
    show_conversation(messages, state["current_chat_id"])
if question:
    answer_question(question, messages, state["current_chat_id"])

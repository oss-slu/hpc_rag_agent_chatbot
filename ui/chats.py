"""This session's chats, kept in ``st.session_state``.

No Streamlit drawing here, so it can be unit-tested with a plain dict as the
state. Chats are gone when the tab is closed or refreshed; nothing about the
user is saved.

Keys in the state:

    chats            chat id -> {"title": str, "messages": [message, ...]}
    current_chat_id  the open chat, or None for a new, empty chat
    ratings          answer id -> 1 or -1, so each answer is rated once
    pending_question an example question that was clicked, waiting to be asked

A message is {"role": "user" | "assistant", "content": str}; assistant
messages also have "answer_id", "sources" and "error".
"""

import uuid
from collections.abc import MutableMapping
from typing import Any

from ui.settings import CHAT_TITLE_LENGTH

State = MutableMapping[str, Any]  # st.session_state, or a dict in tests


def set_up(state: State) -> None:
    """Add the keys above the first time the page runs."""
    state.setdefault("chats", {})
    state.setdefault("current_chat_id", None)
    state.setdefault("ratings", {})


def start_new_chat(state: State) -> None:
    """Show an empty chat. It's added to the sidebar once a question is asked."""
    state["current_chat_id"] = None


def open_chat(state: State, chat_id: str) -> None:
    state["current_chat_id"] = chat_id


def create_chat(state: State, first_question: str) -> str:
    """Make a new chat, named after its first question, open it, and return its id."""
    chat_id = str(uuid.uuid4())
    title = first_question[:CHAT_TITLE_LENGTH]
    if len(first_question) > CHAT_TITLE_LENGTH:
        title += "…"
    state["chats"][chat_id] = {"title": title, "messages": []}
    state["current_chat_id"] = chat_id
    return chat_id


def current_messages(state: State) -> list[dict]:
    """Messages of the open chat; empty for a new chat."""
    chat = state["chats"].get(state["current_chat_id"])
    return chat["messages"] if chat else []


def find_chats(state: State, search_text: str = "") -> list[tuple[str, dict]]:
    """(chat id, chat) pairs whose title contains ``search_text``, newest first."""
    newest_first = reversed(list(state["chats"].items()))
    return [
        (chat_id, chat)
        for chat_id, chat in newest_first
        if search_text.lower() in chat["title"].lower()
    ]


def ask_example_question(state: State, question: str) -> None:
    """Remember a clicked example question; the page asks it on its next run."""
    state["pending_question"] = question


def take_pending_question(state: State) -> str | None:
    """The clicked example question, if any (asked once, then forgotten)."""
    return state.pop("pending_question", None)

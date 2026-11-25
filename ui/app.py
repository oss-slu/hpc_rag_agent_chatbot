"""Streamlit chat page for BilliBot, the Libra HPC Assistant.

Run it from the repo root with ``make ui`` (real API at API_URL) or
``make ui-fake`` (FAKE_API=1, a made-up answer, no API needed).

Layout:
    Sidebar: logo, "New chat", a search box, and this session's chats.
    Main:    the app name; a welcome screen with example questions when
             the chat is empty, otherwise the conversation; the prompt box.

Chats live only in this browser session (``st.session_state``): they are
gone when the tab is closed or refreshed, and nothing about the user is saved.
Colors come from ``.streamlit/config.toml``.
"""

import base64
import os
import sys
import uuid
from pathlib import Path

import streamlit as st

# `streamlit run ui/app.py` runs this file as a script; make the `ui` package importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.client import Answer, Client  # noqa: E402

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

APP_NAME = "BilliBot"
APP_SUBTITLE = "Libra HPC Assistant"
API_URL = os.environ.get("API_URL", "http://localhost:8000")
FAKE_API = os.environ.get("FAKE_API") == "1"
MAX_QUESTION_LENGTH = 4000  # same limit as the API
CHAT_TITLE_LENGTH = 40  # the sidebar shows this much of a chat's first question
ASSETS = Path(__file__).parent / "assets"
LOGO = str(ASSETS / "billibot.png")  # 256px copy of logo/
# A 64px copy for the prompt box. CSS can't load a local file, so the image is
# put into the CSS itself as text (a base64 "data URL").
SMALL_LOGO_URL = (
    "data:image/png;base64,"
    + base64.b64encode((ASSETS / "billibot-small.png").read_bytes()).decode()
)

# Example questions on the welcome screen, each with an icon. Clicking one asks it.
# Icons are Google Material Symbols: https://fonts.google.com/icons
EXAMPLE_QUESTIONS = [
    (":material/terminal:", "How do I submit a batch job?"),
    (":material/memory:", "How do I request a GPU for my job?"),
    (":material/apps:", "How do I load software with modules?"),
    (":material/monitoring:", "How do I check the status of my jobs?"),
]
LOGO_BACKGROUND = "#E6EEF9"  # light SLU blue circle behind the logo

# ---------------------------------------------------------------------------
# Page setup and styling
# ---------------------------------------------------------------------------

st.set_page_config(page_title=APP_NAME, page_icon=LOGO)

# The few things the theme file can't do: the logo's background, the welcome
# heading, the example-question cards, left-aligned chat titles, and the
# prompt box shape. (An f-string, so CSS braces are doubled: {{ }}.)
st.markdown(
    f"""
    <style>
    /* Logo: a light blue circle behind BilliBot so it stands out on white. */
    .st-key-sidebar_logo img, .st-key-welcome img,
    [data-testid="stChatMessageAvatarImage"] {{
        background: {LOGO_BACKGROUND}; border-radius: 50%;
    }}
    .st-key-sidebar_logo img {{ padding: 8px; }}
    .st-key-welcome img {{ padding: 16px; }}

    /* Title: "BilliBot" with its subtitle right under it. Streamlit spaces
       elements 1rem apart and pulls text back up by 1rem; undo both here. */
    .st-key-app_title {{ gap: 0; }}
    .st-key-app_title h3 {{ padding-bottom: 0; }}
    .st-key-app_title [data-testid="stMarkdownContainer"] {{ margin-bottom: 0; }}

    .st-key-welcome {{ margin-top: 8vh; }}
    .st-key-welcome h2 {{ text-align: center; color: #003DA5; font-weight: 600; }}

    /* Example-question cards: blue icon on top, question below, left-aligned. */
    .st-key-example_questions button {{
        min-height: 136px; padding: 1rem; align-items: flex-start;
    }}
    .st-key-example_questions button > div,
    .st-key-example_questions button > div > span {{ width: 100%; }}  /* content at the left */
    .st-key-example_questions button > div > span {{
        flex-direction: column; align-items: flex-start; gap: 0.5rem;
    }}
    .st-key-example_questions button * {{  /* wrap long questions, don't cut them off */
        white-space: normal; overflow: visible; text-overflow: clip; text-align: left;
    }}
    .st-key-example_questions [data-testid="stIconMaterial"] {{
        color: #003DA5; font-size: 1.5rem;
    }}
    .st-key-example_questions button:hover {{ background: #F2F6FC; border-color: #003DA5; }}

    /* Narrow space (phone, tablet, or a small window with the sidebar open):
       show the cards 2 x 2 instead of 4 in a row. This checks the width of
       the cards' own area, not the screen, so the sidebar is accounted for. */
    .st-key-example_questions {{ container-type: inline-size; }}
    @container (max-width: 640px) {{
        .st-key-example_questions [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; }}
        .st-key-example_questions [data-testid="stColumn"] {{
            flex: 0 0 calc(50% - 0.5rem); min-width: calc(50% - 0.5rem);
        }}
        .st-key-example_questions button {{ min-height: 112px; }}
    }}

    /* Phones: less space above the welcome and a smaller greeting,
       so the whole welcome screen fits without scrolling. */
    @media (max-width: 640px) {{
        .st-key-welcome {{ margin-top: 0; }}
        .st-key-welcome h2 {{ font-size: 1.5rem; }}
    }}

    /* User messages: a gray bubble on the right, sized to the text, no icon.
       (Streamlit labels each message "Chat message from user/assistant".) */
    [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {{
        width: fit-content; max-width: 80%; margin-left: auto;
        padding: 0.5rem 1rem; border-radius: 1.25rem;
    }}
    [data-testid="stChatMessage"]:has([aria-label="Chat message from user"])
        [data-testid^="stChatMessageAvatar"] {{ display: none; }}

    /* Sidebar "New chat" and search: same height and corners, so they match.
       The button's icon and text sit at the left. The search box is a soft
       gray with no border until it's clicked. */
    .st-key-new_chat button {{
        min-height: 40px; border-radius: 10px; padding-left: 14px; font-weight: 600;
    }}
    .st-key-new_chat button > div {{ justify-content: flex-start; }}
    .st-key-search_chats [data-testid="stTextInputRootElement"] {{
        min-height: 40px; border-radius: 10px;
        background: #EEF2F7; border-color: transparent;
    }}
    .st-key-search_chats [data-testid="stTextInputRootElement"]:focus-within {{
        border-color: #003DA5; background: #FFFFFF;
    }}

    /* Sidebar chat list: compact rows. Every row has the same padding, so the
       text never shifts; the open chat (a "secondary" button) just gets a
       light blue background. */
    .st-key-chat_list {{ gap: 2px; }}
    .st-key-chat_list button {{
        min-height: 0; padding: 6px 10px; border: none; border-radius: 6px;
    }}
    .st-key-chat_list button:hover {{ background: #EEF2F7; }}
    .st-key-chat_list [data-testid="stBaseButton-secondary"] {{
        background: {LOGO_BACKGROUND}; color: #003DA5;
    }}
    .st-key-chat_list button > div {{ justify-content: flex-start; width: 100%; }}
    .st-key-chat_list button p {{  /* one line per chat; long titles end in "…" */
        text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}

    /* Prompt box: fully rounded ends, the small logo on the left,
       and a send arrow that points right. */
    [data-testid="stChatInput"] > div > div::before {{
        content: ""; flex-shrink: 0; align-self: center;
        width: 32px; height: 32px;  /* same size and edge gap as the send button */
        background: url("{SMALL_LOGO_URL}") center / 24px no-repeat {LOGO_BACKGROUND};
        border-radius: 50%;
    }}
    [data-testid="stChatInput"] > div {{ border-radius: 1.75rem; }}
    [data-testid="stChatInputSubmitButton"] {{ border-radius: 50%; }}
    [data-testid="stChatInputSubmitButton"] svg {{ transform: rotate(90deg); }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def client() -> Client:
    """One API client, shared by every session."""
    return Client(API_URL, fake=FAKE_API)


# ---------------------------------------------------------------------------
# Session state
#
#   chats            chat id -> {"title": str, "messages": [message, ...]}
#   current_chat_id  the open chat, or None for a new, empty chat
#   ratings          answer id -> 1 or -1, so each answer is rated once
#   pending_question an example question that was clicked, waiting to be asked
#
# A message is {"role": "user" | "assistant", "content": str}; assistant
# messages also have "answer_id", "sources" and "error".
# ---------------------------------------------------------------------------

st.session_state.setdefault("chats", {})
st.session_state.setdefault("current_chat_id", None)
st.session_state.setdefault("ratings", {})


def start_new_chat() -> None:
    """Show an empty chat. It's added to the sidebar once a question is asked."""
    st.session_state.current_chat_id = None


def open_chat(chat_id: str) -> None:
    st.session_state.current_chat_id = chat_id


def ask_example_question(question: str) -> None:
    st.session_state.pending_question = question


def current_messages() -> list[dict]:
    """Messages of the open chat; empty for a new chat."""
    chat = st.session_state.chats.get(st.session_state.current_chat_id)
    return chat["messages"] if chat else []


def create_chat(first_question: str) -> None:
    """Make a new chat, named after its first question, and open it."""
    chat_id = str(uuid.uuid4())
    title = first_question[:CHAT_TITLE_LENGTH]
    if len(first_question) > CHAT_TITLE_LENGTH:
        title += "…"
    st.session_state.chats[chat_id] = {"title": title, "messages": []}
    st.session_state.current_chat_id = chat_id


# ---------------------------------------------------------------------------
# Sidebar: logo, new chat, search, chat list
# ---------------------------------------------------------------------------


def show_sidebar() -> None:
    with st.sidebar:
        with st.container(key="sidebar_logo"):
            st.image(LOGO, width=64)

        st.button(
            "New chat",
            key="new_chat",
            icon=":material/add:",
            on_click=start_new_chat,
            type="primary",  # SLU blue: the main action in the sidebar
            width="stretch",
        )
        search_text = st.text_input(
            "Search chats",
            key="search_chats",
            placeholder="Search chats",
            icon=":material/search:",
            label_visibility="collapsed",
        )

        st.caption("Chats")
        # Newest chats first; keep only the ones whose title matches the search.
        chats = reversed(list(st.session_state.chats.items()))
        matching = [
            (chat_id, chat)
            for chat_id, chat in chats
            if search_text.lower() in chat["title"].lower()
        ]
        if not matching:
            st.caption("No chats found." if search_text else "No chats yet.")
            return

        with st.container(key="chat_list"):
            for chat_id, chat in matching:
                is_open = chat_id == st.session_state.current_chat_id
                st.button(
                    chat["title"],
                    key=f"chat-{chat_id}",
                    on_click=open_chat,
                    args=(chat_id,),
                    type="secondary" if is_open else "tertiary",  # CSS highlights "secondary"
                    width="stretch",
                )


# ---------------------------------------------------------------------------
# Welcome screen: shown while the chat is empty
# ---------------------------------------------------------------------------


def show_welcome() -> None:
    # The logo with the greeting under it, both centered.
    with st.container(key="welcome", horizontal_alignment="center"):
        st.image(LOGO, width=120)
        st.markdown("## How can we assist you today?")

    # One card (button) per example question, side by side.
    with st.container(key="example_questions"):
        columns = st.columns(len(EXAMPLE_QUESTIONS))
        for column, (icon, question) in zip(columns, EXAMPLE_QUESTIONS, strict=True):
            column.button(
                question,
                icon=icon,
                key=f"example-{question}",
                on_click=ask_example_question,
                args=(question,),
                width="stretch",
            )

    st.caption(
        "Answers come from the Libra documentation, with links to the pages used. "
        "Check important details on the linked pages."
    )


# ---------------------------------------------------------------------------
# Conversation: messages, sources and 👍/👎
# ---------------------------------------------------------------------------


def show_sources(sources: list[dict[str, str]]) -> None:
    """Numbered links to the pages the answer came from."""
    if sources:
        links = "\n".join(f"{i}. [{s['title']}]({s['url']})" for i, s in enumerate(sources, 1))
        st.markdown("**Sources**\n\n" + links)


def show_feedback(answer_id: str, widget_key: str) -> None:
    """👍/👎 under an answer; each answer is rated once per session."""
    ratings = st.session_state.ratings
    if answer_id in ratings:
        st.caption("Thanks for the feedback.")
        return
    choice = st.feedback("thumbs", key=widget_key)
    if choice is not None:
        rating = 1 if choice == 1 else -1
        problem = client().rate(answer_id, rating)
        if problem:
            st.warning(problem)
        else:
            ratings[answer_id] = rating
            st.rerun()


def show_answer_extras(message: dict, index: int) -> None:
    """Under an assistant message: the error, or its sources and rating buttons."""
    if message.get("error"):
        st.error(message["error"])
        return
    show_sources(message.get("sources", []))
    if message.get("answer_id"):
        widget_key = f"feedback-{st.session_state.current_chat_id}-{index}"
        show_feedback(message["answer_id"], widget_key)


def chat_bubble(role: str):
    """A chat message box. The assistant's shows the logo; the user's icon is
    hidden by the CSS at the top, which also moves user messages to the right."""
    return st.chat_message(role, avatar=LOGO if role == "assistant" else None)


def show_conversation(messages: list[dict]) -> None:
    for index, message in enumerate(messages):
        with chat_bubble(message["role"]):
            if message["content"]:
                st.markdown(message["content"])
            if message["role"] == "assistant":
                show_answer_extras(message, index)


def answer_question(question: str, messages: list[dict]) -> None:
    """Show the question, stream the answer in, and save both to the chat."""
    messages.append({"role": "user", "content": question})
    with chat_bubble("user"):
        st.markdown(question)

    with chat_bubble("assistant"):
        answer = Answer()
        st.write_stream(client().ask(question, answer))  # fills in `answer` as it streams
        message = {
            "role": "assistant",
            "content": answer.text,
            "answer_id": answer.answer_id,
            "sources": answer.sources,
            "error": answer.error,
        }
        messages.append(message)
        show_answer_extras(message, len(messages) - 1)


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

# A question comes from the prompt box or from a clicked example question.
# Read it first, so a new chat is created before the sidebar lists the chats.
question = st.chat_input(
    "Ask about Libra or Slurm…", max_chars=MAX_QUESTION_LENGTH
) or st.session_state.pop("pending_question", None)

if question and st.session_state.current_chat_id is None:
    create_chat(question)

show_sidebar()

# The name with the subtitle right under it, kept together as one title.
with st.container(key="app_title"):
    st.markdown(f"### {APP_NAME}")
    st.caption(APP_SUBTITLE)
if FAKE_API:
    st.caption("**Demo mode:** answers are made up (FAKE_API=1).")

messages = current_messages()
if not messages and not question:
    show_welcome()
else:
    show_conversation(messages)
if question:
    answer_question(question, messages)

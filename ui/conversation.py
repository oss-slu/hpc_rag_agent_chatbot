"""The conversation: messages, their sources and 👍/👎, and asking a new question."""

import streamlit as st

from ui.client import Answer, Client
from ui.settings import API_URL, FAKE_API, LOGO


@st.cache_resource
def get_client() -> Client:
    """One API client, shared by every session."""
    return Client(API_URL, fake=FAKE_API)


def chat_bubble(role: str):
    """A chat message box. The assistant's shows the logo; style.css hides the
    user's icon and moves user messages to the right."""
    return st.chat_message(role, avatar=LOGO if role == "assistant" else None)


def show_sources(sources: list[dict[str, str]]) -> None:
    """Numbered links to the pages the answer came from."""
    if sources:
        links = "\n".join(f"{i}. [{s['title']}]({s['url']})" for i, s in enumerate(sources, 1))
        st.markdown("**Sources**\n\n" + links)


def show_feedback(answer_id: str, widget_key: str) -> None:
    """👍/👎 under an answer; each answer is rated once per session."""
    ratings = st.session_state["ratings"]
    if answer_id in ratings:
        st.caption("Thanks for the feedback.")
        return
    choice = st.feedback("thumbs", key=widget_key)
    if choice is not None:
        rating = 1 if choice == 1 else -1
        problem = get_client().rate(answer_id, rating)
        if problem:
            st.warning(problem)
        else:
            ratings[answer_id] = rating
            st.rerun()


def show_answer_extras(message: dict, chat_id: str, index: int) -> None:
    """Under an assistant message: the error, or its sources and rating buttons."""
    if message.get("error"):
        st.error(message["error"])
        return
    show_sources(message.get("sources", []))
    if message.get("answer_id"):
        show_feedback(message["answer_id"], widget_key=f"feedback-{chat_id}-{index}")


def show_conversation(messages: list[dict], chat_id: str) -> None:
    """Every message so far in the open chat."""
    for index, message in enumerate(messages):
        with chat_bubble(message["role"]):
            if message["content"]:
                st.markdown(message["content"])
            if message["role"] == "assistant":
                show_answer_extras(message, chat_id, index)


def answer_question(question: str, messages: list[dict], chat_id: str) -> None:
    """Show the question, stream the answer in, and save both to the chat."""
    messages.append({"role": "user", "content": question})
    with chat_bubble("user"):
        st.markdown(question)

    with chat_bubble("assistant"):
        answer = Answer()
        st.write_stream(get_client().ask(question, answer))  # fills in `answer` as it streams
        message = {
            "role": "assistant",
            "content": answer.text,
            "answer_id": answer.answer_id,
            "sources": answer.sources,
            "error": answer.error,
        }
        messages.append(message)
        show_answer_extras(message, chat_id, len(messages) - 1)

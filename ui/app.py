"""Streamlit chat page for the SLU HPC Assistant.

Run it with ``make ui`` (real API at API_URL) or ``make ui-fake`` (FAKE_API=1,
a made-up answer, no API needed).
"""

import os
import sys
from pathlib import Path

import streamlit as st

# `streamlit run ui/app.py` runs this as a script; make the `ui` package importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.client import Answer, Client  # noqa: E402

API_URL = os.environ.get("API_URL", "http://localhost:8000")
FAKE_API = os.environ.get("FAKE_API") == "1"
MAX_QUESTION = 4000  # same limit as the API

st.set_page_config(page_title="SLU HPC Assistant", page_icon="💬")


@st.cache_resource
def client() -> Client:
    return Client(API_URL, fake=FAKE_API)


def show_sources(sources: list[dict[str, str]]) -> None:
    if sources:
        links = "\n".join(f"{i}. [{s['title']}]({s['url']})" for i, s in enumerate(sources, 1))
        st.markdown("**Sources**\n\n" + links)


def show_feedback(answer_id: str, index: int) -> None:
    """👍/👎 under an answer; each answer is rated once per session."""
    ratings = st.session_state.ratings
    if answer_id in ratings:
        st.caption("Thanks for the feedback." if ratings[answer_id] else "")
        return
    choice = st.feedback("thumbs", key=f"feedback-{index}")
    if choice is not None:
        rating = 1 if choice == 1 else -1
        problem = client().rate(answer_id, rating)
        if problem:
            st.warning(problem)
        else:
            ratings[answer_id] = rating
            st.rerun()


def show_answer(message: dict, index: int) -> None:
    if message.get("error"):
        st.error(message["error"])
        return
    show_sources(message.get("sources", []))
    if message.get("answer_id"):
        show_feedback(message["answer_id"], index)


st.title("SLU HPC Assistant")
st.caption(
    "Answers come from the Libra documentation, with links to the pages used. "
    "Check important details on the linked pages."
    + ("  \n**Demo mode:** answers are made up (FAKE_API=1)." if FAKE_API else "")
)

st.session_state.setdefault("messages", [])
st.session_state.setdefault("ratings", {})

for index, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["content"]:
            st.markdown(message["content"])
        if message["role"] == "assistant":
            show_answer(message, index)

if question := st.chat_input("Ask about Libra, SLURM jobs, partitions…", max_chars=MAX_QUESTION):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        answer = Answer()
        st.write_stream(client().ask(question, answer))
        message = {
            "role": "assistant",
            "content": answer.text,
            "answer_id": answer.answer_id,
            "sources": answer.sources,
            "error": answer.error,
        }
        st.session_state.messages.append(message)
        show_answer(message, len(st.session_state.messages) - 1)

"""The welcome screen, shown while the chat is empty."""

import streamlit as st

from ui import chats
from ui.settings import EXAMPLE_QUESTIONS, LOGO


def show_welcome() -> None:
    # The logo with the greeting under it, both centered.
    with st.container(key="welcome", horizontal_alignment="center"):
        st.image(LOGO, width=120)
        st.markdown("## How can we assist you today?")

    # One card (button) per example question, side by side. Clicking one asks it.
    with st.container(key="example_questions"):
        columns = st.columns(len(EXAMPLE_QUESTIONS))
        for column, (icon, question) in zip(columns, EXAMPLE_QUESTIONS, strict=True):
            column.button(
                question,
                icon=icon,
                key=f"example-{question}",
                on_click=chats.ask_example_question,
                args=(st.session_state, question),
                width="stretch",
            )

    st.caption(
        "Answers come from the Libra documentation, with links to the pages used. "
        "Check important details on the linked pages."
    )

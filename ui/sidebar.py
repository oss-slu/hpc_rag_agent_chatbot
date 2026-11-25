"""The sidebar: logo, "New chat", a search box, and this session's chats."""

import streamlit as st

from ui import chats
from ui.settings import LOGO


def show_sidebar() -> None:
    state = st.session_state
    with st.sidebar:
        with st.container(key="sidebar_logo"):
            st.image(LOGO, width=64)

        st.button(
            "New chat",
            key="new_chat",
            icon=":material/add:",
            on_click=chats.start_new_chat,
            args=(state,),
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
        matching = chats.find_chats(state, search_text)
        if not matching:
            st.caption("No chats found." if search_text else "No chats yet.")
            return

        # One button per chat; clicking it opens that chat.
        with st.container(key="chat_list"):
            for chat_id, chat in matching:
                # style.css highlights the open chat, which is the "secondary" one.
                is_open = chat_id == state["current_chat_id"]
                st.button(
                    chat["title"],
                    key=f"chat-{chat_id}",
                    on_click=chats.open_chat,
                    args=(state, chat_id),
                    type="secondary" if is_open else "tertiary",
                    width="stretch",
                )

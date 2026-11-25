"""The UI's chat bookkeeping (ui/chats.py), with a plain dict as the session state."""

import pytest

from ui import chats
from ui.settings import CHAT_TITLE_LENGTH


@pytest.fixture
def state():
    state = {}
    chats.set_up(state)
    return state


def test_a_new_session_has_no_chats_and_none_open(state):
    assert state == {"chats": {}, "current_chat_id": None, "ratings": {}}
    assert chats.current_messages(state) == []


def test_set_up_keeps_existing_chats(state):
    chat_id = chats.create_chat(state, "How do I submit a batch job?")
    chats.set_up(state)  # runs again on every page run
    assert chat_id in state["chats"]


def test_create_chat_opens_it_and_names_it_after_the_question(state):
    chat_id = chats.create_chat(state, "How do I submit a batch job?")
    assert state["current_chat_id"] == chat_id
    assert state["chats"][chat_id] == {"title": "How do I submit a batch job?", "messages": []}


def test_long_titles_are_shortened():
    state = {}
    chats.set_up(state)
    question = "x" * (CHAT_TITLE_LENGTH + 10)
    chat_id = chats.create_chat(state, question)
    assert state["chats"][chat_id]["title"] == "x" * CHAT_TITLE_LENGTH + "…"


def test_new_chat_shows_an_empty_chat_and_open_chat_goes_back(state):
    chat_id = chats.create_chat(state, "First question")
    chats.current_messages(state).append({"role": "user", "content": "First question"})

    chats.start_new_chat(state)
    assert state["current_chat_id"] is None
    assert chats.current_messages(state) == []

    chats.open_chat(state, chat_id)
    assert chats.current_messages(state) == [{"role": "user", "content": "First question"}]


def test_find_chats_lists_newest_first_and_filters_by_title(state):
    gpu = chats.create_chat(state, "How do I request a GPU?")
    modules = chats.create_chat(state, "How do I load modules?")

    assert [chat_id for chat_id, _ in chats.find_chats(state)] == [modules, gpu]
    assert [chat_id for chat_id, _ in chats.find_chats(state, "gpu")] == [gpu]  # any case
    assert chats.find_chats(state, "nothing like this") == []


def test_a_clicked_example_question_is_asked_once(state):
    chats.ask_example_question(state, "How do I submit a batch job?")
    assert chats.take_pending_question(state) == "How do I submit a batch job?"
    assert chats.take_pending_question(state) is None

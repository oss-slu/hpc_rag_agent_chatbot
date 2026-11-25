"""The chat page (ui/app.py) run with Streamlit's test runner, using made-up answers.

No browser, API or API key: get_client() is swapped for a demo-mode client.
This checks what happens on the page, not how it looks.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ui import conversation
from ui.client import Client

APP = str(Path(__file__).resolve().parent.parent / "ui" / "app.py")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(conversation, "get_client", lambda: Client("http://unused", fake=True))
    return AppTest.from_file(APP, default_timeout=30).run()


def button(app, label_part):
    return next(b for b in app.button if label_part in b.label)


def chat_titles(app):
    return [chat["title"] for chat in app.session_state["chats"].values()]


def test_an_empty_chat_shows_the_welcome_cards(app):
    assert not app.exception
    assert [b.label for b in app.button if b.key.startswith("example-")] == [
        "How do I submit a batch job?",
        "How do I request a GPU for my job?",
        "How do I load software with modules?",
        "How do I check the status of my jobs?",
    ]
    assert app.caption[-1].value.startswith("No chats yet")


def test_clicking_a_card_asks_it_in_a_new_chat(app):
    button(app, "request a GPU").click().run()

    assert not app.exception
    assert chat_titles(app) == ["How do I request a GPU for my job?"]
    assert [m.name for m in app.chat_message] == ["user", "assistant"]
    assert "Sources" in app.chat_message[1].markdown[-1].value
    assert len(app.get("feedback")) == 1  # 👍/👎 under the answer


def test_follow_ups_stay_in_the_same_chat(app):
    app.chat_input[0].set_value("How do I submit a batch job?").run()
    app.chat_input[0].set_value("And how long can it run?").run()

    assert len(app.session_state["chats"]) == 1
    assert len(app.chat_message) == 4


def test_new_chat_and_search(app):
    app.chat_input[0].set_value("How do I request a GPU?").run()
    button(app, "New chat").click().run()
    assert any(b.key.startswith("example-") for b in app.button)  # welcome screen again

    app.chat_input[0].set_value("How do I load modules?").run()
    assert chat_titles(app) == ["How do I request a GPU?", "How do I load modules?"]

    app.text_input(key="search_chats").set_value("gpu").run()
    assert [b.label for b in app.button if b.key.startswith("chat-")] == [
        "How do I request a GPU?"
    ]

    app.text_input(key="search_chats").set_value("nothing like this").run()
    assert any(c.value == "No chats found." for c in app.caption)
    assert not app.exception

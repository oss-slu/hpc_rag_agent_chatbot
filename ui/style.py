"""Add style.css to the page."""

import base64
from pathlib import Path

import streamlit as st

from ui.settings import LOGO_BACKGROUND, SMALL_LOGO

CSS_FILE = Path(__file__).parent / "style.css"


def apply_style() -> None:
    """Put style.css on the page, after setting the two variables it uses."""
    # CSS on the page can't load a file from this folder, so the small logo is
    # put into the CSS itself as text (a base64 "data URL").
    small_logo_url = "data:image/png;base64," + base64.b64encode(SMALL_LOGO.read_bytes()).decode()
    variables = (
        f':root {{ --logo-background: {LOGO_BACKGROUND}; --small-logo: url("{small_logo_url}"); }}'
    )
    css = variables + "\n" + CSS_FILE.read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

"""Settings for the chat UI: names, where the API is, example questions, logos."""

import os
from pathlib import Path

APP_NAME = "BilliBot"
APP_SUBTITLE = "Libra HPC Assistant"

# Where the API runs. FAKE_API=1 shows made-up answers instead (demo mode).
API_URL = os.environ.get("API_URL", "http://localhost:8000")
FAKE_API = os.environ.get("FAKE_API") == "1"

MAX_QUESTION_LENGTH = 4000  # same limit as the API
CHAT_TITLE_LENGTH = 40  # the sidebar shows this much of a chat's first question

# Example questions on the welcome screen, each with an icon. Clicking one asks it.
# Icons are Google Material Symbols: https://fonts.google.com/icons
EXAMPLE_QUESTIONS = [
    (":material/terminal:", "How do I submit a batch job?"),
    (":material/memory:", "How do I request a GPU for my job?"),
    (":material/apps:", "How do I load software with modules?"),
    (":material/monitoring:", "How do I check the status of my jobs?"),
]

ASSETS = Path(__file__).parent / "assets"
LOGO = str(ASSETS / "billibot.png")  # 256px copy of logo/
SMALL_LOGO = ASSETS / "billibot-small.png"  # 64px copy, for the prompt box
LOGO_BACKGROUND = "#E6EEF9"  # light SLU blue circle behind the logo

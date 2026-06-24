"""Loading settings — chiefly the Anthropic API key from a git-ignored .env.

The key is Grandson's brain. We never hardcode it and never print it.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when something we need to run is missing. Plain-language message."""


def load_api_key() -> str:
    """Load ANTHROPIC_API_KEY from the environment / .env file.

    Raises ``ConfigError`` with a plain-language message if it isn't set. The key
    itself is never included in any message or printed anywhere.
    """
    # Reads a local ".env" if present; real environment variables win.
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ConfigError(
            "I'm missing the key I need to think. Please copy the file named "
            "'.env.example' to a file named '.env' and put your Anthropic key "
            "inside it. Then start me again."
        )

    return api_key

"""The brain + the voice: ask Claude what's on screen, in plain language.

This is M1's core. We send the screenshot to a Claude vision model and ask it to
describe the screen the way a patient grandkid would — no jargon, short
sentences — per SAFETY.md §4.
"""

from __future__ import annotations

import base64

from anthropic import Anthropic, APIError

from . import safety

# A current Claude model that can see images.
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 700

# SAFETY.md §4 (plain-language rule) lives here, as a system prompt. Every word
# of the narration must be understandable by someone who has never used a
# computer confidently.
SYSTEM_PROMPT = """\
You are Grandson, a kind and patient helper for someone who is not comfortable \
with computers — imagine explaining things to a beloved grandparent who has \
never felt confident using a Mac.

You are being shown a picture of what is currently on their computer screen. \
Your job is ONLY to describe what is on the screen, calmly and clearly. You are \
NOT controlling anything and NOT telling them to click anything.

How to talk:
- Use plain, everyday words. No computer jargon at all. If you must name \
something technical, explain it in simple words right after.
- Use short sentences.
- Be warm and reassuring, never rushed and never condescending.
- Start with the big picture: what app or website are they looking at, in one \
simple sentence.
- Then point out the few most important things on the screen — like the main \
button, a message, or where their attention should go.
- If something looks like it might be a scam, a fake warning, or a trick (for \
example, a popup saying the computer is infected, or a demand to call a phone \
number or pay money urgently), gently say so and tell them not to act on it.
- If the screen is mostly empty or you cannot tell what it is, just say that \
honestly and kindly.

Keep the whole description short — a few friendly sentences, not a wall of text.\
"""

USER_PROMPT = (
    "Here is a picture of what's on the screen right now. "
    "Please tell me, in plain and simple words, what I'm looking at."
)


class NarrationError(Exception):
    """Raised when we couldn't get a description back. Carries a plain message."""


def describe_screen(client: Anthropic, image_bytes: bytes) -> str:
    """Send the screenshot to Claude and return a plain-language description.

    Raises ``NarrationError`` with a plain-language message on failure.
    """
    image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": USER_PROMPT},
                    ],
                }
            ],
        )
    except APIError as exc:
        raise NarrationError(
            "I couldn't reach my brain to understand the screen just now. "
            "This is usually the internet connection. Let's try again in a moment."
        ) from exc

    parts = [block.text for block in response.content if block.type == "text"]
    narration = "\n".join(parts).strip()

    if not narration:
        raise NarrationError(
            "I looked at the screen but couldn't find the words to describe it. "
            "Let's try that again."
        )

    return narration


def narrate(client: Anthropic, image_bytes: bytes) -> str:
    """Full narration path for M1: describe the screen, with the scam shield wired in.

    The scam-shield call is a stub today (see ``safety.scan_for_scams``), but it
    lives on the narration path so M3 only has to fill the stub in, not re-plumb
    the app.
    """
    narration = describe_screen(client, image_bytes)

    # Run the (stubbed) scam shield over what we just described. When the real
    # shield lands, anything it finds gets surfaced to the person here.
    scan = safety.scan_for_scams(narration)
    if not scan.is_clear:
        warnings = "\n\n".join(
            f"Careful — this looks like a {f.label}. {f.explanation}"
            for f in scan.findings
        )
        narration = f"{warnings}\n\n{narration}"

    return narration

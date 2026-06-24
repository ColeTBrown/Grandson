"""The eyes: capture the Mac screen.

Uses macOS's built-in `screencapture` CLI so we don't pull in any extra
dependencies. M1 only reads the screen — there is no mouse or keyboard code here
and there must not be until M2.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class ScreenCaptureError(Exception):
    """Raised when we couldn't get a usable picture of the screen.

    The message is written in plain language so the app can show it straight to
    the person without dressing it up.
    """


# A real screenshot is far bigger than this. If we get something tiny back,
# macOS almost certainly handed us a blank/black image because Screen Recording
# permission hasn't been granted yet.
_MIN_PLAUSIBLE_SCREENSHOT_BYTES = 5_000


def capture_screen() -> bytes:
    """Take a picture of the whole screen and return it as PNG bytes.

    Raises ``ScreenCaptureError`` with a plain-language message if the picture
    can't be taken (for example, the very common case where macOS hasn't been
    given permission to record the screen yet).
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        shot_path = Path(tmp.name)

    try:
        # -x  : silent (no camera shutter sound)
        # -t  : output format
        # -C  : include the mouse cursor so the person can see where it is
        result = subprocess.run(
            ["screencapture", "-x", "-C", "-t", "png", str(shot_path)],
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise ScreenCaptureError(
                "I couldn't take a picture of your screen just now. "
                "On a Mac this usually means I need your permission first. "
                "Please open System Settings, go to Privacy & Security, then "
                "Screen Recording, and turn me on there. Then try again."
            )

        if not shot_path.exists():
            raise ScreenCaptureError(
                "I tried to take a picture of your screen but nothing was saved. "
                "Let's try that again in a moment."
            )

        image_bytes = shot_path.read_bytes()

        if len(image_bytes) < _MIN_PLAUSIBLE_SCREENSHOT_BYTES:
            # We got *a* file but it's suspiciously empty — the classic blank
            # screenshot you get before Screen Recording permission is granted.
            raise ScreenCaptureError(
                "The picture of your screen came out blank. On a Mac this means "
                "I still need permission to see the screen. Please open System "
                "Settings, go to Privacy & Security, then Screen Recording, "
                "turn me on, and try again."
            )

        return image_bytes

    except FileNotFoundError as exc:
        # `screencapture` should always be present on macOS; if it isn't, we're
        # almost certainly not on a Mac.
        raise ScreenCaptureError(
            "I couldn't find the tool I use to look at the screen. "
            "Grandson works on a Mac — please run me there."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ScreenCaptureError(
            "Taking a picture of your screen took too long, so I stopped. "
            "Let's try that again."
        ) from exc
    finally:
        shot_path.unlink(missing_ok=True)

"""Entry point.

M1 ("See & Explain", the default) — look at the screen and explain it:
    python -m grandson

M2 ("Guided Takeover") — do the one real task: make the on-screen text bigger:
    python -m grandson --do bigger-text

M1 takes no actions and touches no mouse/keyboard. M2 controls the mouse and
keyboard, but ONLY through the safety gate (see docs/SAFETY.md, docs/M2-PLAN.md):
every action passes through ``safety.gate_action`` before anything moves, and the
run is slow, narrated, interruptible, and bounded.
"""

from __future__ import annotations

import sys
import threading

from anthropic import Anthropic

from .config import ConfigError, load_api_key
from .loop import LoopConfig, run_task
from .narrator import NarrationError, narrate
from .screen import ScreenCaptureError, capture_screen

# The one task M2 ships. A single named flag value keeps the surface tiny and
# makes "general do-anything mode" an explicit non-goal (M2-PLAN non-goal #5).
_TASK_BIGGER_TEXT = "bigger-text"


def _make_hard_stop() -> "tuple[threading.Event, threading.Thread]":
    """A hard stop the person can trigger by typing 'stop' (M2-PLAN §3.2).

    Returns a flag the loop checks between every action, plus a daemon thread
    that watches the terminal for the word 'stop'. Ctrl-C is also honoured by the
    loop as an immediate stop; this gives a second, gentler way out for someone
    who doesn't know the keyboard shortcut.
    """
    stop = threading.Event()

    def watch() -> None:
        try:
            for line in sys.stdin:
                if line.strip().lower() in {"stop", "stop!", "halt"}:
                    stop.set()
                    return
        except (EOFError, ValueError):
            return

    thread = threading.Thread(target=watch, daemon=True)
    return stop, thread


def _run_narrate_only() -> int:
    """M1 path: capture the screen, narrate it once, with the scam shield."""
    print("Hello, I'm Grandson. Let me take a look at your screen...\n")

    try:
        api_key = load_api_key()
    except ConfigError as exc:
        print(exc)
        return 1

    client = Anthropic(api_key=api_key)

    try:
        image_bytes = capture_screen()
    except ScreenCaptureError as exc:
        print(exc)
        return 1

    try:
        narration = narrate(client, image_bytes)
    except NarrationError as exc:
        print(exc)
        return 1

    print("Here's what I see on your screen:\n")
    print(narration)
    print()
    return 0


def _run_takeover() -> int:
    """M2 path: do the one task end-to-end through the gated control loop."""
    print(
        "Hello, I'm Grandson. I'll help make the text on your screen bigger.\n"
        "If you ever want me to stop, type the word  stop  and press Enter, or "
        "hold Control and press C.\n"
    )

    try:
        api_key = load_api_key()
    except ConfigError as exc:
        print(exc)
        return 1

    client = Anthropic(api_key=api_key)

    stop_flag, watcher = _make_hard_stop()
    watcher.start()

    return run_task(
        client,
        LoopConfig(),
        should_stop=stop_flag.is_set,
    )


def main(argv: list[str] | None = None) -> int:
    """Dispatch to M1 (default) or the M2 task, keeping M1's surface intact."""
    args = sys.argv[1:] if argv is None else argv

    if "--do" in args:
        i = args.index("--do")
        task = args[i + 1] if i + 1 < len(args) else ""
        if task == _TASK_BIGGER_TEXT:
            return _run_takeover()
        print(
            "I only know one task right now: making the text on your screen "
            f"bigger. Try:  python -m grandson --do {_TASK_BIGGER_TEXT}"
        )
        return 1

    return _run_narrate_only()


if __name__ == "__main__":
    sys.exit(main())

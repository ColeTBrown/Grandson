"""The hands: the ONE place that moves the real mouse and keyboard.

This is M2's biggest risk escalation, so the whole module is built around a
single promise (M2-PLAN §"Where the gate sits"):

    **No action reaches the hardware except through the safety gate.**

That promise is enforced *structurally*, not by good intentions:

- The raw mouse/keyboard primitive is a PRIVATE function (``_perform``) with a
  leading underscore. Nothing in the codebase calls it except ``gated_execute``
  in this same module. (reviewer-qa proves this by grep.)
- ``gated_execute`` is the only public way to perform an action, and it calls
  ``safety.gate_action(...)`` first. It touches the hardware ONLY when the gate
  returns ``allowed is True``. There is no other code path to ``_perform``.

We drive macOS through **`osascript` / System Events UI scripting against named
elements** (the architect's preferred option #1, M2-PLAN §3). Rationale:

- **Most auditable.** The script literally names what it clicks — e.g.
  ``click button "Accessibility"`` — instead of pushing blind pixels. A reviewer
  can read exactly what each action touches.
- **Robust** to screen size and layout differences (no coordinate guessing).
- **No third-party dependency.** ``osascript`` ships with every Mac, so M2 adds
  no pip package for control. (We still note the dependency in requirements.txt.)
- It triggers the standard macOS **Accessibility** permission prompt, which we
  detect and explain in plain language (mirroring ``screen.py``).

Keystrokes here are confined to *navigation and non-text keys* (arrows, tab,
escape) and to typing literal UI text we generated ourselves — never a password,
PIN, or code. Credentials are BLOCKED at the gate and never reach this module
(SAFETY.md §1; M2-PLAN non-goal #2): if one is ever needed, we hand the keyboard
back to the person.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum

from . import safety


class ActionKind(Enum):
    """The small, fixed vocabulary of things the actor can do.

    Deliberately tiny. M2 does one task; a bigger vocabulary is a bigger attack
    surface. Each kind maps to one auditable osascript snippet in ``_perform``.
    """

    OPEN_APP = "open_app"          # bring a named app to the front
    CLICK_ELEMENT = "click_element"  # click a named UI element (button/row/etc.)
    PRESS_KEY = "press_key"        # press a navigation key (arrow/tab/escape)
    DONE = "done"                  # the goal is reached; perform nothing


# OPEN_APP allow-list (Fix 2). ``_perform`` would otherwise ``activate`` ANY app
# name the planner hands it, so a benign-sounding step could still bring up
# Terminal or a password manager. For this M2 task only System Settings is ever
# needed, so we name it explicitly. An OPEN_APP for anything else is treated as
# not-allowed and safe-stops, independent of what the planner proposes. Kept as a
# named constant (a set, case-insensitive compare) so later milestones can extend
# it deliberately, one reviewed entry at a time.
_OPEN_APP_ALLOW_LIST = frozenset({"system settings"})


# Only these keys may be pressed. No character/text typing primitive exists in
# M2 at all, so there is no path to type a credential here even by mistake.
_ALLOWED_KEYS = {
    "right arrow": 124,
    "left arrow": 123,
    "down arrow": 125,
    "up arrow": 126,
    "escape": 53,
    "tab": 48,
    "return": 36,
}


@dataclass
class Action:
    """One proposed step. ``human_description`` is what the gate classifies and
    what gets narrated to the person, in plain language (SAFETY.md §4)."""

    kind: ActionKind
    human_description: str
    # Meaning depends on kind: app name (OPEN_APP), element name (CLICK_ELEMENT),
    # or key name (PRESS_KEY). Unused for DONE.
    target: str = ""


class ActionError(Exception):
    """Raised when an allowed action could not be carried out.

    The message is plain-language so it can be shown straight to the person.
    Most often this is the macOS **Accessibility** permission not being granted
    yet (the M2 equivalent of M1's Screen Recording prompt).
    """


@dataclass
class ActionOutcome:
    """What happened when we tried to run one action through the gate."""

    performed: bool          # did the hardware actually move?
    allowed: bool            # did the gate allow it?
    decision: safety.ActionDecision  # the gate's verdict (carries plain reason)


# Phrases osascript uses when System Events isn't allowed to control the
# computer — i.e. the Accessibility permission is missing or was denied.
_PERMISSION_HINTS = (
    "not allowed assistive access",
    "not authorized to send apple events",
    "osascript is not allowed",
    "1002",  # errAEEventNotPermitted-adjacent codes surface as -1002/-1719 etc.
    "-1719",
    "-25211",
)


def _accessibility_help() -> str:
    """Plain-language walkthrough for granting Accessibility (mirrors screen.py)."""
    return (
        "I'm not allowed to move the mouse and keyboard yet, so I've stopped.\n"
        "On a Mac this is a one-time permission. Here's how to turn it on:\n"
        "  1. Open System Settings.\n"
        "  2. Click Privacy & Security.\n"
        "  3. Click Accessibility.\n"
        "  4. Find Grandson (or Terminal) in the list and switch it on.\n"
        "Then start me again and we'll pick up where we left off. "
        "Nothing was changed on your computer."
    )


def _run_osascript(script: str, *, timeout: int = 20) -> str:
    """Run one AppleScript and return its stdout, or raise ``ActionError``.

    Detects the missing-Accessibility-permission case and turns it into the
    calm, plain-language walkthrough above instead of a stack trace.
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ActionError(
            "I couldn't find the tool I use to control the Mac. "
            "Grandson works on a Mac — please run me there."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ActionError(
            "That step took too long, so I stopped to be safe. "
            "Nothing was changed. Let's try again."
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        lowered = stderr.lower()
        if any(hint in lowered for hint in _PERMISSION_HINTS):
            raise ActionError(_accessibility_help())
        # Any other failure (element not found, app missing) is a surprise — we
        # never improvise through it. Hand back a calm message; the loop's
        # VERIFY/safe-stop takes it from here.
        raise ActionError(
            "I tried to do that step but it didn't work the way I expected, "
            "so I stopped to be safe. Nothing was changed."
        )

    return (result.stdout or "").strip()


def _perform(action: Action) -> None:
    """PRIVATE raw mouse/keyboard primitive — the ONLY hardware-touching code.

    NOTHING calls this except :func:`gated_execute` in this module. It assumes
    the safety gate has already allowed the action; it does NOT classify or
    confirm anything itself (that is the gate's job, and duplicating it here
    would create a second, weaker decision point). Keeping it dumb and private
    is what makes the no-bypass property easy to verify by reading the code.
    """
    if action.kind is ActionKind.DONE:
        return  # nothing to do; the goal is already reached.

    if action.kind is ActionKind.OPEN_APP:
        app = action.target.replace('"', '\\"')
        _run_osascript(f'tell application "{app}" to activate')
        return

    if action.kind is ActionKind.CLICK_ELEMENT:
        # Click the first UI element whose name contains the target text, in the
        # frontmost app. Named-element targeting is the auditable path (M2-PLAN
        # §3): the script says what it clicks. If no such element exists,
        # osascript errors and _run_osascript turns it into a safe stop.
        name = action.target.replace('"', '\\"')
        script = f'''
        tell application "System Events"
            set frontApp to first application process whose frontmost is true
            tell frontApp
                set theMatch to missing value
                repeat with anElement in (entire contents of front window)
                    try
                        if (name of anElement as string) contains "{name}" then
                            set theMatch to anElement
                            exit repeat
                        end if
                    end try
                end repeat
                if theMatch is missing value then error "element not found"
                click theMatch
            end tell
        end tell
        '''
        _run_osascript(script)
        return

    if action.kind is ActionKind.PRESS_KEY:
        key = action.target.strip().lower()
        code = _ALLOWED_KEYS.get(key)
        if code is None:
            # Not in the tiny allow-list. Refuse rather than improvise a keystroke.
            raise ActionError(
                "I was about to press a key I'm not sure about, so I stopped to "
                "be safe. Nothing was changed."
            )
        _run_osascript(
            f'tell application "System Events" to key code {code}'
        )
        return

    # Unknown kind — never guess at the hardware.
    raise ActionError(
        "I didn't recognise that step, so I stopped to be safe. "
        "Nothing was changed."
    )


def _gate_text(action: Action) -> str:
    """Compose the text the gate classifies so it covers what actually runs.

    The gate used to see only ``action.human_description`` — the narration — but
    ``_perform`` acts on ``action.kind`` + ``action.target``. Those can diverge:
    a benign description ("open the screen where text size lives") can carry a
    dangerous target ("Privacy & Security", "Terminal"). To make "the thing that
    gets performed is the thing that got gated" structurally true, we fold the
    structured target (and a human-readable hint of the kind) INTO the text the
    gate classifies, alongside the description. The same ``classify_action``
    rules then judge the real target, so a risky target trips RISKY/BLOCKED even
    under a benign description, while the happy-path targets (System Settings,
    Accessibility, Display, the text-size control) stay ROUTINE.
    """
    kind_hint = {
        ActionKind.OPEN_APP: "open the app",
        ActionKind.CLICK_ELEMENT: "click",
        ActionKind.PRESS_KEY: "press the key",
        ActionKind.DONE: "",
    }.get(action.kind, "")
    parts = [action.human_description.strip()]
    target = action.target.strip()
    if kind_hint and target:
        # e.g. "...  || click Privacy & Security" — the gate sees the real target.
        parts.append(f"{kind_hint} {target}")
    return " || ".join(p for p in parts if p)


def gated_execute(
    action: Action,
    *,
    read_input=None,
    write_output=None,
) -> ActionOutcome:
    """The ONLY public way to perform an action — and it goes through the gate.

    Steps (M2-PLAN §"Where the gate sits"):
      1. Enforce the OPEN_APP allow-list (Fix 2): an OPEN_APP for anything other
         than an allow-listed app is an unexpected target we never activate, so
         it safe-stops here regardless of how benign its description reads.
      2. Ask :func:`safety.gate_action` whether this action may proceed, passing
         text that includes the structured ``target`` (and ``kind``), NOT just
         the narration (Fix 1). That function classifies the action, auto-allows
         ROUTINE, runs the informed typed-``yes`` confirmation for RISKY, and
         never allows BLOCKED. It touches no hardware.
      3. Touch the mouse/keyboard (via the private :func:`_perform`) ONLY when
         ``GateResult.allowed`` is True. Otherwise return without acting.

    The gate's I/O is injectable (``read_input`` / ``write_output``) so the
    confirmation prompt is testable; defaults wire to the real terminal.

    Returns an :class:`ActionOutcome` describing what the gate decided and
    whether the hardware moved. Raises :class:`ActionError` (plain-language) only
    if an *allowed* action couldn't be carried out (e.g. missing Accessibility
    permission) — never to report a refusal.
    """
    # Fix 2: an OPEN_APP may only ever activate an allow-listed app. An app name
    # outside the list is unexpected — we treat it as not-allowed and safe-stop,
    # so the guarantee holds no matter what the planner proposes. We do NOT route
    # it through the gate's confirm flow (there is no informed-yes that should
    # let an arbitrary app launch in M2); we simply refuse.
    if action.kind is ActionKind.OPEN_APP:
        if action.target.strip().lower() not in _OPEN_APP_ALLOW_LIST:
            return ActionOutcome(
                performed=False,
                allowed=False,
                decision=safety.ActionDecision(
                    risk=safety.Risk.RISKY,
                    reason=(
                        "That step wanted to open a program I'm not set up to "
                        "open for this task, so I stopped to be safe. The only "
                        "thing I open here is System Settings, to make the text "
                        "bigger. Nothing was changed."
                    ),
                ),
            )

    # Fix 1: classify the structured action (kind + target), not just narration,
    # so the gated decision covers exactly what `_perform` will do.
    gate = safety.gate_action(
        _gate_text(action),
        read_input=read_input,
        write_output=write_output,
    )

    if not gate.allowed:
        # RISKY-without-yes or BLOCKED. Do NOT touch the hardware. The loop turns
        # this into a unified safe-stop with the plain-language reason.
        return ActionOutcome(
            performed=False, allowed=False, decision=gate.decision
        )

    _perform(action)
    return ActionOutcome(performed=True, allowed=True, decision=gate.decision)

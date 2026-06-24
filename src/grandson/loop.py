"""The control loop: perceive -> plan -> gate -> narrate+act -> verify -> repeat.

This is M2's spine, wiring M1's eyes (``screen``) and voice (``narrator``) to the
new ``planner`` and the gated ``actor``. It owns the things the architect made
non-negotiable (M2-PLAN §3, §4):

- **One action per cycle.** We perceive again before proposing each step.
- **Bounded.** A hard step budget AND a wall-clock cap; hitting either is a calm
  safe-stop. No "retry until it works" — at most ONE gentle re-attempt.
- **Interruptible.** A hard-stop the person can trigger is checked between every
  action; nothing runs once it's set.
- **Slow + narrated.** Every action is announced in plain language *before* it
  happens, with a deliberate pace.
- **Scam shield on every perceive.** If it fires, we hard-stop before acting.
- **One unified safe-stop** for every surprise: scam, refused/blocked action,
  unexpected screen, low confidence, repeated failure, budget/time cap, or any
  permission/capture/think error. We stop, explain calmly, and offer to retry or
  fetch family — never a crash, never a retry-storm.

The gate itself is NOT re-implemented here. Every action goes through
``actor.gated_execute``, which calls ``safety.gate_action``. This module never
touches the mouse/keyboard directly.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from anthropic import Anthropic

from . import safety
from .actor import ActionError, ActionKind, ActionOutcome, gated_execute
from .narrator import NarrationError, describe_screen
from .planner import PlanError, PlanResult, plan_next_action
from .screen import ScreenCaptureError, capture_screen

# Bounds (M2-PLAN §3). Conservative on purpose: a task left unfinished is fine,
# a runaway loop on a real person's machine is not.
DEFAULT_STEP_BUDGET = 12
DEFAULT_TIME_CAP_SECONDS = 180.0

# A deliberate, followable pace before each action so the person can watch and
# intervene (M2-PLAN §3.1). Speed is never a goal here.
DEFAULT_PACE_SECONDS = 2.0

# The standard close-out offer attached to every safe-stop (SAFETY.md §3/§4).
RETRY_OR_FAMILY_OFFER = (
    "We can try again whenever you're ready, or I can help you reach a family "
    "member you trust so you can do it together. There's no rush at all."
)


@dataclass
class LoopConfig:
    """Knobs for the control loop. Defaults are the safe production values."""

    step_budget: int = DEFAULT_STEP_BUDGET
    time_cap_seconds: float = DEFAULT_TIME_CAP_SECONDS
    pace_seconds: float = DEFAULT_PACE_SECONDS


class SafeStop(Exception):
    """Internal signal that we must stop calmly. Carries a plain-language note.

    Routing everything unexpected through one exception keeps the "one unified
    safe-stop" promise (M2-PLAN §4): there is a single place that stops, explains,
    and offers retry/family.
    """


def _now() -> float:
    return time.monotonic()


def run_task(
    client: Anthropic,
    config: LoopConfig | None = None,
    *,
    say: Callable[[str], None] = print,
    read_input: Callable[[str], str] = input,
    should_stop: Callable[[], bool] | None = None,
    pause: Callable[[float], None] = time.sleep,
    capture: Callable[[], bytes] = capture_screen,
    describe: Callable[[Anthropic, bytes], str] = describe_screen,
    propose: Callable[[Anthropic, str], PlanResult] = plan_next_action,
    execute: Callable[..., ActionOutcome] = gated_execute,
) -> int:
    """Run the one M2 task end-to-end. Returns a process exit code.

    Every collaborator is injectable so the loop's *logic* (bounds, safe-stop,
    scam-fire, verify, hard-stop) is unit-testable without real hardware, screen
    capture, or the network. Production callers use the defaults.

    The loop never raises on a handled problem — it narrates a calm message and
    returns. The only thing it deliberately lets through is the hardware-touching
    step, and that only ever runs after ``gated_execute`` (and thus the safety
    gate) has allowed it.
    """
    cfg = config or LoopConfig()
    if should_stop is None:
        should_stop = lambda: False  # noqa: E731 — trivial default

    started = _now()
    used_steps = 0
    retried_once = False

    say(
        "Okay — I'll make the text on your screen bigger.\n"
        "I'll go one small step at a time and tell you what I'm doing before I "
        "do it. If you ever want me to stop, just say so."
    )

    try:
        while True:
            # --- Interrupt check: between every action, before anything else. ---
            if should_stop():
                raise SafeStop(
                    "You asked me to stop, so I have — right away. "
                    "Nothing more will happen."
                )

            # --- Bounds: step budget and wall-clock cap (M2-PLAN §3.3). ---
            if used_steps >= cfg.step_budget:
                raise SafeStop(
                    "I've taken several steps and I don't want to keep going on "
                    "my own, so I'm stopping here to be safe."
                )
            if _now() - started >= cfg.time_cap_seconds:
                raise SafeStop(
                    "This is taking longer than I'd like, so I'm stopping here "
                    "to be safe rather than carry on by myself."
                )

            # --- PERCEIVE: look, describe, run the scam shield (M2-PLAN §4). ---
            description = _perceive(client, capture, describe, say)
            _scam_check(description)  # hard-stop if it fires, before any action.

            # --- PLAN: propose exactly one next step. ---
            plan = _safe_propose(client, description, propose)

            if plan.is_done:
                say(
                    "\nThat's done — the text on your screen should be bigger and "
                    "easier to read now. If it's too big or not big enough, just "
                    "tell me and I'll adjust it."
                )
                return 0

            if not plan.confident:
                raise SafeStop(
                    plan.reason
                    or "I wasn't sure what to do next, so I stopped to be safe."
                )

            # --- NARRATE + ACT: say it first, pace, then ONE gated action. ---
            if should_stop():  # last check before we actually move anything.
                raise SafeStop(
                    "You asked me to stop, so I have — right away. "
                    "Nothing more will happen."
                )

            say(f"\nNext, I'm going to {plan.action.human_description}")
            pause(cfg.pace_seconds)

            outcome = _act(plan, execute, say, read_input)

            if not outcome.performed:
                # The gate refused (RISKY-without-yes or BLOCKED). gated_execute
                # / the confirmation flow already explained it in plain language.
                raise SafeStop(
                    "I stopped before that step because it wasn't something I "
                    "should do on my own."
                )

            used_steps += 1

            # --- VERIFY: re-perceive; did the screen move toward the goal? ---
            after = _perceive(client, capture, describe, say, announce=False)
            _scam_check(after)

            if _looks_unchanged(description, after):
                # The screen didn't move after the action. One gentle re-attempt
                # at most, then
                # safe-stop — never a retry-storm (M2-PLAN §4 "repeated failure").
                if retried_once:
                    raise SafeStop(
                        "That step didn't seem to change anything, even after I "
                        "tried once more, so I'm stopping rather than keep "
                        "guessing."
                    )
                retried_once = True
                say(
                    "Hmm, that didn't seem to change anything. Let me take "
                    "another look and try a gentle next step."
                )
            else:
                retried_once = False

    except SafeStop as stop:
        _emit_safe_stop(say, str(stop))
        return 1
    except (ScreenCaptureError, NarrationError, PlanError, ActionError) as exc:
        # Any permission/capture/think/act error: calm message, clean exit.
        _emit_safe_stop(say, str(exc))
        return 1
    except KeyboardInterrupt:
        _emit_safe_stop(
            say,
            "You stopped me, so I've stopped right away. Nothing more will happen.",
        )
        return 1


# ---------------------------------------------------------------------------
# Small helpers — each does one job so the loop above reads as the policy.
# ---------------------------------------------------------------------------


def _perceive(client, capture, describe, say, *, announce: bool = True) -> str:
    """Capture + describe one screen. Errors propagate to the safe-stop handler."""
    if announce:
        say("\nLet me look at your screen...")
    image = capture()
    return describe(client, image)


def _scam_check(description: str) -> None:
    """Run the always-on scam shield; a finding hard-stops the task (M2-PLAN §4)."""
    scan = safety.scan_for_scams(description)
    if not scan.is_clear:
        warnings = "\n".join(
            f"- This looks like a {f.label}. {f.explanation}"
            for f in scan.findings
        )
        raise SafeStop(
            "I need to stop right now. Something on the screen looks like a scam, "
            "and your safety comes before anything else:\n" + warnings
        )


def _safe_propose(client, description, propose) -> PlanResult:
    """Wrap planning so a PlanError becomes a clean safe-stop, not a crash."""
    return propose(client, description)


def _act(plan: PlanResult, execute, say, read_input) -> ActionOutcome:
    """Run ONE action through the gated executor (and thus the safety gate).

    The gate's prompt I/O is wired to the same terminal the loop speaks through,
    so an informed-yes confirmation reads naturally inline.
    """
    return execute(
        plan.action,
        read_input=read_input,
        write_output=say,
    )


def _looks_unchanged(before: str, after: str) -> bool:
    """Rough check: did the screen description meaningfully change?

    Cheap and conservative — used only to decide whether an action did *nothing*,
    which gates the single gentle re-attempt. Exact equality of the normalized
    text counts as unchanged.
    """
    if not before or not after:
        return False
    return _normalize(before) == _normalize(after)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _emit_safe_stop(say: Callable[[str], None], message: str) -> None:
    """The single place that delivers a safe-stop: explain calmly + offer help."""
    say("\n" + message)
    say("\n" + RETRY_OR_FAMILY_OFFER)

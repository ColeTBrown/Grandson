"""The chooser: propose exactly ONE next action toward the one M2 task.

The planner looks at the plain-language description of the current screen (from
``narrator``) and the goal, and proposes a single next ``Action`` — or says it's
not sure, or that the goal is done. It never batches actions and it never
touches the gate or the hardware (M2-PLAN §2: one action per cycle).

A crucial safety property lives here: the planner is *required and able* to say
"I'm not sure." Uncertainty routes to a safe-stop instead of a guess (M2-PLAN
§4). We surface that as ``PlanResult.confident`` / a ``DONE`` action, so the
control loop can stop calmly rather than improvise a wrong click on a real
person's machine.

We ask Claude for the next step as a small, constrained JSON object so the
output maps onto the actor's tiny vocabulary (``ActionKind``) and nothing else.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from anthropic import Anthropic, APIError

from .actor import Action, ActionKind

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 500

# The one task M2 ships (M2-PLAN §1). Stated plainly so the planner stays on it
# and treats anything off it as a reason to stop, not to wander.
GOAL = (
    "Make the text on the screen bigger by opening System Settings, going to "
    "Accessibility, then Display, and increasing the text size. This is the "
    "ONLY task. Do not buy, send, delete, install, sign in, type any password, "
    "or change any security or privacy setting."
)

# Names we expect to navigate. Kept here so the prompt can steer the planner
# toward the auditable named-element clicks the actor understands.
SYSTEM_PROMPT = """\
You are Grandson's planner. You help a person who is not comfortable with \
computers by proposing the SINGLE next small step toward one fixed goal, looking \
at a plain-language description of what is currently on their Mac screen.

Hard rules:
- Propose EXACTLY ONE next step. Never batch steps.
- Only these kinds of step exist:
  * open_app        — bring a named app to the front (target = the app name)
  * click_element   — click one named on-screen control (target = its visible \
name, e.g. "Accessibility", "Display", "Text size")
  * press_key       — press ONE navigation key only; target must be one of: \
right arrow, left arrow, down arrow, up arrow, tab, escape, return
  * done            — the goal is already achieved; nothing left to do
- You may NEVER type text, passwords, codes, or click anything about money, \
buying, sending, deleting, installing, signing in, or security/privacy settings. \
If the next sensible step would be any of those, set "confident" to false and \
explain why in "reason" — do not propose it.
- If you are not sure what you are looking at, or the screen is unexpected (a \
password box, a permission request, an error, a surprise dialog), set \
"confident" to false. It is always better to stop than to guess.
- Move slowly and pick the most obvious, reversible step.

Reply with ONLY a JSON object, no other text, in exactly this shape:
{
  "kind": "open_app" | "click_element" | "press_key" | "done",
  "target": "<app name, element name, or key name; empty for done>",
  "human_description": "<one short, plain sentence telling the person what you \
are about to do and why — no jargon>",
  "confident": true | false,
  "reason": "<if not confident, a short plain-language reason you are stopping>"
}\
"""


@dataclass
class PlanResult:
    """The planner's proposal for the next single step."""

    action: Action
    confident: bool
    # Plain-language note used when we stop because the planner is unsure.
    reason: str = ""

    @property
    def is_done(self) -> bool:
        return self.action.kind is ActionKind.DONE


class PlanError(Exception):
    """Raised when we couldn't get a usable plan back. Plain-language message."""


def _parse_kind(raw: str) -> ActionKind:
    for kind in ActionKind:
        if kind.value == raw:
            return kind
    raise ValueError(f"unknown action kind: {raw!r}")


def plan_next_action(client: Anthropic, screen_description: str) -> PlanResult:
    """Ask Claude for the single next step toward the goal (M2-PLAN §2).

    Returns a :class:`PlanResult`. If the planner is unsure, ``confident`` is
    False and the loop safe-stops rather than acting. Raises :class:`PlanError`
    with a plain-language message only if no usable plan could be obtained at all
    (which the loop also treats as a safe-stop).
    """
    user = (
        f"The goal is: {GOAL}\n\n"
        f"Here is what is on the screen right now:\n{screen_description}\n\n"
        "What is the single next step? Reply with only the JSON object."
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
    except APIError as exc:
        raise PlanError(
            "I couldn't think about the next step just now. This is usually the "
            "internet connection. Let's try again in a moment."
        ) from exc

    text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    data = _extract_json(text)
    if data is None:
        raise PlanError(
            "I got a bit confused working out the next step, so I stopped to be "
            "safe. Nothing was changed. Let's try again."
        )

    try:
        kind = _parse_kind(str(data.get("kind", "")).strip())
        human_description = str(data.get("human_description", "")).strip()
        target = str(data.get("target", "")).strip()
        confident = bool(data.get("confident", False))
        reason = str(data.get("reason", "")).strip()
    except (ValueError, AttributeError):
        # Malformed plan = treat as not-sure, never guess (M2-PLAN §4).
        return PlanResult(
            action=Action(kind=ActionKind.DONE, human_description=""),
            confident=False,
            reason=(
                "I wasn't sure what to do next, so I stopped to be safe. "
                "Nothing was changed."
            ),
        )

    # An empty human_description would sail past narration AND classify as RISKY
    # at the gate ("when in doubt"); treat it as low confidence up front so we
    # stop calmly instead.
    if kind is not ActionKind.DONE and not human_description:
        confident = False
        reason = reason or (
            "I couldn't clearly say what the next step would do, so I stopped "
            "to be safe."
        )

    return PlanResult(
        action=Action(
            kind=kind, human_description=human_description, target=target
        ),
        confident=confident,
        reason=reason,
    )


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of the model's reply, forgivingly."""
    if not text:
        return None
    # Strip a ```json ... ``` fence if present.
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[len("json"):].strip()
            if part.startswith("{"):
                text = part
                break
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None

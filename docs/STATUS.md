# Where we are — handoff note

_Read this first to catch up. Last updated: 2026-06-23._

## What Grandson is
An AI that helps elderly / non-tech-savvy people use their **Mac** like a patient
grandkid: it watches the screen, explains in plain language, and can take over the
mouse/keyboard to do a task. See `README.md` for the full vision and `docs/SAFETY.md`
for the safety policy (which overrides every other goal).

## Decisions locked (MVP)
- **Platform:** macOS
- **Core behavior:** guide the person *and* take over the screen to complete a task
- **Autonomy:** does routine actions freely; **stops and asks, in plain language,
  before anything risky** (money, passwords, deleting, sending, suspected scams)
- **Release plan:** repo private now → flip to public at launch, with a license

## Status
- **M0 — Foundation: DONE.** Project scaffold, 5-agent team (`.claude/agents/`),
  safety policy, git repo, pushed to private GitHub repo **ColeTBrown/Grandson**.
- Secrets handled: real keys go in a local `.env` (git-ignored); see `.env.example`.

## M1 — "See & Explain": DONE (built, reviewed, fixes applied)
Grandson takes a screenshot and narrates what's on the screen in plain language.
**No control yet** — zero risk, builds trust, proves the eyes + voice work before
we ever touch the mouse. macOS will prompt for **Screen Recording** permission.

**How to run it:**
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then put your real Anthropic key in .env
cd src && python -m grandson
```
It captures the screen -> sends it to Claude (vision) -> prints a plain-language
description. Missing key, missing/denied Screen Recording permission, blank
screenshots, and network failures all show a calm plain-language message instead
of a crash.

Code lives in `src/grandson/`: `screen.py` (capture via macOS `screencapture`),
`narrator.py` (Claude vision + the plain-language system prompt, SAFETY.md §4),
`safety.py` (the safety seam), `config.py` (loads the key), `__main__.py` (entry).

Division of labor (all done):
- **builder** — the see -> understand -> explain loop (Claude vision).
- **safety-security** — `src/grandson/safety.py` is now REAL, not stubbed:
  `scan_for_scams()` (always-on scam shield, runs on every narration) and
  `classify_action()` (the risky-action gate) are implemented as deterministic,
  auditable rules per SAFETY.md §1/§2.
- **reviewer-qa** — verified plain-language clarity, blank/odd-screen handling,
  and that the scam shield + gate actually fire. Must-fix bugs fixed (dead money
  regex, recall gaps, `.env.example` was gitignored — all corrected).
- Open: not yet run live (no API key present) — happy path unverified until a
  key is added to `.env`.

## M2 — "Guided Takeover": ARCHITECT SIGNED OFF — complete pending live verification
**Sign-off (2026-06-23, lead/architect):** M2 meets every acceptance gate in
`docs/M2-PLAN.md` §5 by structure + tests (39 green:
`PYTHONPATH=src .venv/bin/python -m unittest tests.test_loop_m2 tests.test_safety_m2`).
The no-bypass invariant is grep-proven: the only caller of the private hardware
primitive `actor._perform` is `actor.gated_execute`, which gates first
(`safety.gate_action` over kind+target, not just narration); no control library
is imported anywhere. RISKY needs a typed `yes` (bare Enter = no); BLOCKED is
terminal even with a yes; scam-on-perceive hard-stops before acting; the loop is
bounded (12 steps / 180s) and interruptible (`should_stop` checked between every
action + before acting, plus Ctrl-C); OPEN_APP is locked to a `{System Settings}`
allow-list a yes cannot override; missing Accessibility yields a calm walkthrough
and clean exit; all messages pass the §4 plain-language bar; README + STATUS carry
both permissions and the one-task scope.

**Still requires the user's LIVE verification on a Mac with both permissions
granted** (cannot be done here — no GUI/hardware/network):
1. The real happy path end-to-end: named-element osascript clicks actually land on
   System Settings → Accessibility → Display and raise the text size.
2. The hard-stop *feel* mid-action (type `stop` / Ctrl-C ends before the next step).
3. The Accessibility-permission prompt UX on a machine where it is NOT yet granted.
4. M1's `python -m grandson` narrate-only path with a real API key (still unrun live).
Once these four pass on a real Mac, M2 is fully DONE.

### M2 — build/review record (awaiting only the live verification above)
Grandson now controls the mouse/keyboard to do the one task — **make the text
bigger** (System Settings → Accessibility → Display) — through the full
perceive → plan → **gate** → informed-confirm → act → verify loop. Slow,
narrated, interruptible, and bounded. Every action goes through
`safety.gate_action`; nothing else touches the hardware.

**How to run it:** `cd src && python -m grandson --do bigger-text`
(plain `python -m grandson` is still M1's narrate-only mode, unchanged).
Needs **two** macOS permissions: Screen Recording (M1) **and** Accessibility
(new — to move the mouse/keyboard). A missing Accessibility permission produces
a calm plain-language walkthrough and a clean exit, mirroring `screen.py`.

New code in `src/grandson/`:
- `actor.py` — the hands. `gated_execute(action)` is the ONLY public way to act
  and it calls `safety.gate_action` first; the raw mouse/keyboard primitive is a
  **private** `_perform` that nothing else calls (grep-verifiable no-bypass).
  Tiny fixed vocabulary (open_app / click_element / press_key / done); **no
  text-typing primitive exists**, so a credential can't be typed even by mistake.
- `planner.py` — proposes exactly ONE next action with a confidence flag; "not
  sure" routes to safe-stop instead of guessing.
- `loop.py` — the control loop: one action per cycle, step budget (12) + wall-
  clock cap (180s), hard-stop checked between every action, scam shield on every
  perceive (fires → hard-stop), one gentle retry then stop, and one unified
  safe-stop for every surprise/error.

**Control mechanism chosen:** macOS built-in `osascript` / System Events UI
scripting against **named** elements (M2-PLAN §3 option #1 — most auditable, no
new dependency). `requirements.txt` documents this; no pip control lib added.

**Reviewed by reviewer-qa: SHIP.** No-bypass property proven by grep (only the
private `_perform` touches hardware; its sole caller is `gated_execute`, which
gates first; no control libs imported). One hardening item QA flagged was then
fixed: the gate now classifies the **structured action that executes** (kind +
target), not just the narration, so a risky `target` can't ride in under a benign
description; and `OPEN_APP` is restricted to a `System Settings` allow-list that a
typed `yes` can't override.

**Tested (no hardware/network), 39 tests green:** `tests/test_loop_m2.py` (18)
covers the no-bypass property, gate-sees-executed-action, the OPEN_APP allow-list,
scam-fire hard-stop, step-budget + time-cap, gate-refusal/low-confidence/hard-stop,
one-retry-then-stop, done success, calm error handling. `tests/test_safety_m2.py`
(21) covers the gate classification + the informed typed-`yes` confirm contract.

**Run the tests with the project venv** (system python 3.9 lacks `anthropic`):
`PYTHONPATH=src .venv/bin/python -m unittest tests.test_loop_m2 tests.test_safety_m2` The thin
`_perform` osascript primitive is the only untested-by-necessity piece; its
syntax + the missing-Accessibility-permission path were checked live.

**Needs live/manual verification:** the real end-to-end happy path on a Mac with
both permissions granted (named-element clicks land on the actual Settings
panes), the hard-stop mid-action feel, and the Accessibility prompt UX on a
machine without the permission.

### M2 — original plan (see `docs/M2-PLAN.md`)
Grandson takes over the mouse/keyboard to do **one** real task end-to-end with the
risky-action gate (`safety.classify_action`) live. **Chosen task: make the text on
screen bigger** (open System Settings → Accessibility → Display, raise text size) —
useful to a real 78-year-old, low-stakes, reversible, and it touches no money/
passwords/sending in the happy path, so the gate is exercised at the boundaries.

The plan locks: the perceive → plan → **gate** → informed-confirm → act → verify
loop; the gate as the single choke point to the mouse/keyboard; slow/narrated/
**interruptible**/**bounded** control (no free-running loops); scam shield on every
perceive with a hard-stop; safe-stop on any unexpected/ambiguous/low-confidence
state; the second macOS **Accessibility** permission (separate from M1's Screen
Recording); and the builder / safety-security / reviewer-qa split with M2
acceptance criteria. **Full detail and acceptance gates: `docs/M2-PLAN.md`.**
This plan is now IMPLEMENTED and reviewed (see the section above); the only
remaining gate is live verification on a Mac with both permissions, then
architect sign-off.

## Then
- **M3** — always-on scam shield + the tech-watcher self-update job.

## How to drive the team
From a Claude Code session opened in this folder, dispatch by name, e.g.
"have **builder** start M1" or "have **safety-security** review this." The agent
definitions are in `.claude/agents/`.

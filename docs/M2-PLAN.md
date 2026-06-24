# M2 — "Guided Takeover": scope & design

_Lead/architect plan. Last updated: 2026-06-23. Builder + safety-security execute this;
do not deviate from the safety constraints without a new architect sign-off._

**`docs/SAFETY.md` overrides everything in this doc.** Where capability and safety
conflict below, safety wins and it is called out explicitly.

---

## 0. What M2 is (and the one rule that shapes it)

M2 is the first time Grandson **touches the mouse and keyboard**. It completes
**one** real, useful task end-to-end, with the risky-action gate
(`safety.classify_action`) live and standing between every proposed action and the
hardware.

This is the project's biggest risk escalation. So M2 is deliberately tiny: **one
task, done slowly, narrated, interruptible, and bounded.** A narrow task done
safely beats broad, shaky control. (STATUS.md "Decisions locked"; SAFETY.md §3:
"A real person's trust is the product. Protect it over any single task.")

---

## 1. The first real task

### Chosen task: **"Make the text on my screen bigger / easier to read"**

Concretely: Grandson opens **System Settings → Accessibility → Display** and
increases **text size** (and, if asked, turns on **Bold text** / increases
**cursor size**) for the person — narrating every step and confirming at the
boundaries.

A close, equally acceptable variant the builder may pick if Display proves
fiddly across macOS versions: **raise the system font/zoom via
Accessibility → Zoom or Displays → "Larger Text" scaling.** The architect's
requirement is the *shape* of the task (navigate a known native settings pane and
flip a low-stakes, reversible toggle/slider), not the exact pane.

### Why this task

- **Genuinely useful to a real 78-year-old, not a demo.** Hard-to-read text is
  the single most common, most felt pain for elderly users. This is the kind of
  thing a grandkid actually gets asked to do.
- **Real control, real navigation.** It requires opening an app, clicking through
  a multi-level settings tree, and manipulating a slider/toggle — exercising
  perceive → act → verify for real, not a one-click trick.
- **Low-stakes and reversible.** Nothing is bought, sent, deleted, installed, or
  revealed. Worst realistic case is "text is now too big," which Grandson can
  walk back the same way it walked in. This is the safest possible place to earn
  the right to control the machine.
- **The happy path touches no money/passwords/sending** — exactly as the brief
  requires. That keeps the *core* loop in `ROUTINE` territory, so M2 proves the
  control loop works on its own merits.
- **The gate gets exercised at the boundaries, on purpose.** System Settings sits
  next to genuinely risky panes (Privacy & Security, Touch ID & Password, Apple
  Account/payment). If the model ever proposes navigating into one of those — or
  a "change a security setting" / "allow access" style step appears —
  `classify_action` must catch it and stop. So the gate is tested by *near misses
  around* the task, which is the right way to prove it holds, while the task
  itself stays safe.

### Explicit non-goals for M2 (do NOT build these now)

1. **No money, no purchases, no payment details.** Anything in §1 of SAFETY.md is
   out of the happy path by construction.
2. **No passwords / PINs / 2FA / SSN entry.** If macOS demands an admin password
   to apply a setting (it should not for these panes), Grandson STOPS and hands
   the keyboard to the person — it never types a credential.
3. **No sending anything** (email/message/post/submit).
4. **No installing/downloading**, no changing Privacy & Security or other security
   settings, no granting permissions on the user's behalf.
5. **No second task and no general "do whatever I ask" mode.** M2 ships exactly
   one task flow. A second task is M2.x or later.
6. **No free-running / autonomous loops.** Bounded steps only (see §3).
7. **No web/browser control.** Native macOS only; links and the open web are a
   later milestone with a heavier scam surface.
8. **No background/always-on operation.** Grandson runs, does the one task on
   request, finishes, and stops.

---

## 2. The act → gate → confirm loop

The control loop reuses M1's eyes (`screen.capture_screen`) and brain/voice
(`narrator`), and adds a **planner** (propose the next single action) and an
**actor** (execute one action). The safety gate sits **between planner and actor**
and is the *only* path to the actor.

```
                 ┌─────────────────────────────────────────────┐
                 │  goal: "make text bigger"  +  step budget    │
                 └─────────────────────────────────────────────┘
                                     │
        ┌────────────────────────────▼───────────────────────────┐
        │  PERCEIVE   capture_screen()  →  narrator describes      │
        │             scam shield runs here too (§4)               │
        └────────────────────────────┬───────────────────────────┘
                                      │  screen description
        ┌────────────────────────────▼───────────────────────────┐
        │  PLAN       propose exactly ONE next action as:          │
        │             { kind, target, human_description, done? }   │
        │             low confidence / "I'm not sure"  →  STOP     │
        └────────────────────────────┬───────────────────────────┘
                                      │  proposed action
        ┌────────────────────────────▼───────────────────────────┐
        │  GATE  safety.classify_action(human_description)         │   ← the choke point
        │        ROUTINE → continue                                │
        │        RISKY/BLOCKED → STOP, explain, get informed yes   │
        └───────┬─────────────────────────────────────┬───────────┘
            ROUTINE                            RISKY / BLOCKED
                │                                       │
                │                          ┌────────────▼───────────┐
                │                          │ CONFIRM (informed, §5)  │
                │                          │  read out the reason,   │
                │                          │  require explicit yes;  │
                │                          │  BLOCKED → never proceed │
                │                          └────────────┬───────────┘
                │                              yes │  no/anything-else
                │◄─────────────────────────────────┘        │
                │                                            ▼  safe-stop
        ┌───────▼───────┐
        │  NARRATE+ACT  │  say what it's about to do, then actor does ONE action,
        │               │  slowly; a hard-stop key can interrupt (§3)
        └───────┬───────┘
                │
        ┌───────▼───────┐
        │  VERIFY       │  re-perceive; did the screen change as expected?
        │               │  yes → next step (budget--).  no/odd → safe-stop (§4)
        └───────────────┘
```

### Where the gate sits (the non-negotiable invariant)

**No action reaches the actor except through `classify_action`.** Enforce this
structurally, not by convention:

- The **actor module exposes no public "do this action" function that the planner
  can call directly.** The single public entry to perform an action is a
  `gated_execute(action)` (name TBD) that *itself* calls
  `safety.classify_action(action.human_description)` first and refuses to run if
  the result is not `ROUTINE` **or** an informed-yes was captured for a `RISKY`
  action. There is no other code path to the mouse/keyboard.
- The raw mouse/keyboard primitives live in a private function (leading
  underscore) that only `gated_execute` calls. Reviewer-qa verifies by grep that
  nothing else imports or calls it.
- `BLOCKED` is terminal: there is **no confirmation that can unblock it.** A
  `RISKY` verdict can be cleared only by an informed yes (below). A `BLOCKED`
  verdict ends the task.

### How a "yes" is captured as *informed* (SAFETY.md §5)

A yes counts only if the person was shown, in plain language, exactly what will
happen. Concretely:

- On `RISKY`, Grandson **stops the loop**, reads out `decision.reason` (already
  written in plain language by safety-security) **plus** the specific
  `human_description` of the one action, then asks a clear question.
- The prompt must **not** be default-yes. **Require the person to type the full
  word `yes`** (case-insensitive, trimmed). Empty input, Enter alone, "y", "ok",
  or anything else = **no** → safe-stop. (Rationale: SAFETY.md §5 "never
  default-yes"; a lone Enter must never approve a risky step.)
- The confirmation text never rushes, never buries the risk, never bundles
  multiple actions into one yes. **One risky action = one explicit yes.** No
  "approve all."
- For M2's happy path this prompt should essentially never fire — if it fires
  often, the task or the planner is wrong, and that is a finding, not a feature.

### M2 interaction surface

M2 stays a **command-line program** (like M1): plain text narration printed, the
hard-stop and the yes/no read from the terminal. Voice and large-text GUI are
later milestones. Keeping the surface identical to M1 minimizes new risk; the new
risk in M2 is *control*, and that's where the attention goes.

---

## 3. The control mechanism (constraint for the builder; builder implements)

**Recommendation: drive macOS through the Accessibility API, preferring a
scriptable, inspectable approach over blind pixel-pushing.**

- **Preferred primitive: `cliclick` (a tiny, auditable CLI) or `pyautogui` for
  mouse-move/click and keystrokes**, OR — better for this specific task —
  **AppleScript/`osascript` System Events UI scripting**, which can target named
  UI elements ("click the button named 'Accessibility'") instead of guessing
  coordinates. The architect's preference order:
  1. **`osascript` UI scripting against named elements** where reliable — most
     robust to layout/screen-size differences and the most *auditable* (the
     script literally names what it clicks).
  2. **`cliclick`** for coordinate clicks/typing when element targeting isn't
     available — small, single-purpose, easy to review, no large dependency.
  3. **`pyautogui`** only if the above can't cover a step; it's heavier and more
     pixel-blind.

  Builder picks and justifies the final choice in code review. **This is the
  builder's call to implement; the architect sets the constraints below.** Add the
  chosen dependency to `requirements.txt` in this milestone (M1's requirements
  note explicitly reserved this for M2).

### Hard constraints on the control mechanism (safety, not preference)

1. **Slow and narrated.** Every action is announced in plain language *before* it
   happens, and there is a visible/deliberate pace (e.g. cursor moves are not
   instant; a short, fixed delay between steps) so the person can follow along and
   intervene. Speed is never a goal here (SAFETY.md §4; README "slowly and
   narrated").
2. **Interruptible — a hard stop.** There must be a single, always-available way
   to **stop everything immediately** — the action in progress and the whole loop.
   At minimum: pressing the hard-stop ends the run before the next action. The
   builder must ensure the stop is checked **between every action** and that no
   action can be mid-flight without a way to abort the run. (`pyautogui`'s
   fail-safe corner is a nice-to-have, not the primary stop.)
3. **Bounded — no free-running loops.** The loop has a **hard step budget**
   (e.g. ≤ 12 actions) and a **wall-clock cap**. Hitting either = safe-stop with a
   calm message. The loop also stops the moment the planner reports the goal is
   `done`. There is **no** "keep trying until it works."
4. **One action per cycle.** The planner proposes exactly one action; the loop
   perceives again before proposing the next. No batching, no "type all this and
   click these three things."
5. **macOS Accessibility permission.** Controlling the mouse/keyboard requires the
   user to grant **Accessibility** permission (System Settings → Privacy &
   Security → Accessibility), which is **separate from M1's Screen Recording**
   permission. On the first control attempt macOS will block input and may show a
   prompt. The builder must detect this failure and show a **calm, plain-language**
   message that walks the person through granting it (mirroring `screen.py`'s
   Screen-Recording message), then exit cleanly — never crash, never loop.
   Document this in README/STATUS alongside the Screen-Recording note.

---

## 4. Safety integration points & failure modes

### Scam shield during a task (where it runs)

- The scam shield (`safety.scan_for_scams`) **runs on every PERCEIVE**, on the
  fresh narration of the current screen — the same wiring M1 already has in
  `narrator.narrate`. So it is checked **before every single action**, not just at
  the start.
- **If the shield fires mid-task: stop the whole task immediately,** read the
  finding(s) and the standard family-contact advice, and do **not** perform the
  pending action. This is independent of the planner's confidence — a scam
  finding always wins (SAFETY.md §2; §1 "Anything on a page the scam shield
  flagged" is always risky → here we go further and hard-stop the task).
- Belt-and-suspenders: `classify_action` *also* re-runs the scam scan on the
  action description (it already does, see `safety.py`), so a flagged action is
  caught at the gate even if perception missed it.

### Safe-stop is the default response to anything unexpected

Define one **safe-stop** behavior and route all of the following to it: stop the
loop, do not act, narrate calmly what happened and that we stopped to be safe,
offer to try again or to fetch a family member, exit cleanly (no crash, no
retry-storm).

Trigger safe-stop on:

- **Scam shield fires** (above) — hard, always.
- **Risky/blocked action** without an informed yes (gate) — including a "no".
- **Unexpected screen.** After acting, VERIFY re-perceives and the screen is not
  what the plan expected (wrong pane, an unanticipated dialog, an admin-password
  prompt, a permission request). → safe-stop. **Never improvise** through a
  surprise dialog.
- **Ambiguous state / low confidence.** The planner is unsure what it's looking
  at or what to do next. The planner must be *required and able* to say "I'm not
  sure" — and that routes to safe-stop rather than a guess. (`classify_action`
  already treats an empty/unclear description as `RISKY`; the planner should also
  surface its own uncertainty explicitly.)
- **Repeated failure.** If an action doesn't move the screen toward the goal,
  **do not retry blindly.** One gentle re-attempt at most, then safe-stop. The
  step budget (§3) is the backstop.
- **Budget / time cap reached** (§3).
- **Any control-permission or capture error** (Accessibility / Screen Recording).

> Architect's stance, explicit: **when confidence is low or the state is
> ambiguous, we stop rather than press on.** A task left unfinished is fine; a
> wrong click on a real person's machine is not (SAFETY.md §3).

### Ownership — safety-security vs. builder

**safety-security OWNS:**
- The gate contract and its enforcement that **nothing reaches the actor without
  `classify_action`** (reviews the actor's structure for this invariant).
- The informed-confirmation flow (the exact prompt wording, the require-typed-`yes`
  rule, no-default-yes, one-yes-per-action, BLOCKED-is-terminal).
- `classify_action` coverage for the panes near this task (esp. that navigating
  toward Privacy & Security / password / Apple-Account/payment panes, or any
  "allow access" / "change security setting" step, returns `RISKY`/`BLOCKED`).
- The scam-shield placement in the loop and the "scam fires → hard stop" rule.
- The plain-language wording of every stop/confirm message (SAFETY.md §4, §5).

**builder OWNS:**
- The planner (propose one action + confidence + done-flag), the actor
  (`gated_execute` + the private primitive), the perceive/verify wiring, the
  hard-stop mechanism, the step/time bounds, the pacing, and the Accessibility
  permission detection + plain-language guidance. Builder must call the gate;
  builder must NOT add bypasses or its own confirmation logic.

If the two ever disagree, **safety-security's call stands** and the architect
arbitrates.

---

## 5. Division of labor, sequence, and acceptance criteria

Run it like M1: builder pass → safety-security pass → reviewer-qa pass, with the
architect holding scope.

### Sequence

1. **architect (this doc):** scope, task, loop, constraints — DONE.
2. **safety-security (first, before control code touches hardware):**
   - Confirm/extend `classify_action` so the near-the-task risky panes and any
     "allow/permission/security-setting/credential" step classify as
     `RISKY`/`BLOCKED`. Add unit tests for these.
   - Specify the informed-confirmation contract (typed `yes`, no default-yes,
     one-yes-per-action, BLOCKED terminal) as a small, testable helper the builder
     must call — so the builder cannot get the confirmation semantics wrong.
   - Write the gate-placement requirement the reviewer will check.
3. **builder:** implement the planner, the gated actor, perceive→gate→confirm→
   act→verify loop for the *one* task, bounds, hard-stop, pacing, and the
   Accessibility-permission path. Reuse `screen` + `narrator`. Add the chosen
   control dependency to `requirements.txt`.
4. **safety-security (review):** verify the gate is the sole path to the actor,
   the confirmation is truly informed, scam-fires-hard-stop works, no bypass
   exists, all stop messages are plain-language.
5. **reviewer-qa:** test on messy real cases (below). Verify clean handling, not
   just the happy path.
6. **architect:** sign off against the acceptance criteria; update STATUS.

### Acceptance criteria — "M2 done"

**Functional**
- [ ] On request, Grandson completes the one task end-to-end on a real Mac:
      opens the settings pane and increases text size, narrating each step.
- [ ] It announces each action in plain language **before** doing it, and moves at
      a deliberate, followable pace.

**Safety (these are pass/fail gates, not nice-to-haves)**
- [ ] **No action can execute without passing `classify_action`.** Demonstrated by
      code structure + reviewer grep: the only path to the mouse/keyboard
      primitive is the gated executor.
- [ ] A `RISKY` action stops the loop and requires an **informed, typed `yes`**;
      a bare Enter / "y" / empty / anything-not-`yes` is treated as **no** →
      safe-stop. (test)
- [ ] A `BLOCKED` action is **never** executed, with or without confirmation. (test)
- [ ] If the scam shield fires at any PERCEIVE, the task **hard-stops** before the
      pending action and gives the §2 plain-language warning + family-contact
      offer. (test, with a simulated scammy screen description)
- [ ] **Hard stop works:** the run can be interrupted and ends before the next
      action; no action is left un-abortable. (manual)
- [ ] **Bounded:** the loop cannot run past its step budget or time cap; both
      lead to a calm safe-stop. (test)
- [ ] **Unexpected screen / low confidence / repeated failure → safe-stop**, no
      improvising, no retry-storm. (test on a deliberately wrong/surprise screen)
- [ ] Missing **Accessibility** permission produces a calm, plain-language,
      step-by-step message and a clean exit (no crash, no loop). (manual on a
      machine without the permission)

**Quality / UX**
- [ ] Every narration, stop, and confirmation message passes the SAFETY.md §4
      plain-language bar (no jargon, short sentences, warm, unrushed).
- [ ] Failures (capture error, network error, permission denied, surprise dialog)
      all show a calm message instead of a stack trace, exactly like M1.
- [ ] README + STATUS updated: M2 how-to-run, **both** required permissions
      (Screen Recording + Accessibility), and the one-task scope + non-goals.

### Out of scope for M2 (restated so it isn't quietly added)
Second task, general command mode, web/browser control, voice, GUI, always-on/
background mode, any §1 risky action in the happy path, and any autonomous loop.
These are later milestones.

# Grandson 👴💛

**An AI that helps people use their computer the way a patient grandkid would.**

Grandson watches the screen, explains what's happening in plain language with no
jargon, and — when asked — takes over the mouse and keyboard to do the hard part.
It's built for elderly and non-tech-savvy people, to close the growing gap between
them and a world that keeps changing faster than anyone can keep up with.

## The promise
- **No judgment, no jargon.** It explains like family, not like a manual.
- **It does the doing.** Not just "click here" — it can actually take the wheel.
- **It protects, not just helps.** The same eyes that guide also catch scams.

## First version (MVP) — scope
- **Platform:** macOS
- **Core behavior:** Guides the person *and* can take over the screen to complete a task.
- **Autonomy:** Does routine actions freely; **stops and asks, in plain language,
  before anything risky** (money, passwords, deleting, sending, suspected scams).

## How it works (the loop)
1. **Look** — screenshot + understand the screen
2. **Explain** — say what it sees / is about to do, simply
3. **Safety gate** — routine → proceed; risky → stop and ask (see `docs/SAFETY.md`)
4. **Act** — move/click/type, slowly and narrated
5. **Repeat**, checking in like a patient person would

## Running M1 — See & Explain
M1 looks at your screen and explains it in plain language. It does **not** control
anything yet. On a Mac:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then put your real Anthropic key in .env
cd src && python -m grandson
```

The first time, macOS will ask for **Screen Recording** permission (System
Settings → Privacy & Security → Screen Recording). Grant it, then run again.

## Running M2 — Guided Takeover
M2 is the first time Grandson controls the mouse and keyboard. It does **one**
real task end-to-end: **make the text on your screen bigger** (open System
Settings → Accessibility → Display and raise the text size), going slowly and
narrating each step. Every action passes through the safety gate first.

```bash
cd src && python -m grandson --do bigger-text
```

What to expect:
- It announces each step in plain language **before** it does it, and moves at a
  deliberate pace so you can follow along.
- **To stop at any time:** type `stop` and press Enter, or hold Control and
  press C. The run ends before the next action.
- It is **bounded** — it takes a small number of steps then stops on its own; it
  never runs free or "keeps trying until it works."
- If anything unexpected happens (a surprise window, a password box, a scam, a
  step it's unsure about), it **stops calmly**, explains why, and offers to try
  again or fetch a family member. It never improvises through a surprise.
- It will **never** type a password, PIN, or code, spend money, send anything,
  delete, or install — those stop and hand control back to you.

M2 needs **two** macOS permissions, both one-time:
1. **Screen Recording** (as in M1) — so Grandson can see the screen.
2. **Accessibility** (System Settings → Privacy & Security → Accessibility) — so
   Grandson can move the mouse and keyboard. The first control attempt will be
   blocked until this is on; Grandson detects that and walks you through turning
   it on, then exits cleanly. Grant it and run again.

The plain old `python -m grandson` (no flags) still just looks and explains — it
takes no actions.

Control mechanism: M2 drives macOS through the built-in `osascript` (System
Events UI scripting against **named** elements), the most auditable option — the
script literally names what it clicks. No extra control library is installed.

## Milestones
- **M0 — Foundation** ✅ project + 5-agent dev team + safety policy
- **M1 — See & Explain** ✅ screen narration, no control yet (zero risk, builds trust)
- **M2 — Guided takeover** ✅ one real task end-to-end with risky-action gates live
- **M3 — Scam shield + self-update** always-on scam detection + the Tech-Watcher

## The dev team
Five specialized Claude Code subagents live in `.claude/agents/`:
| Agent | Role |
|-------|------|
| `lead-architect` | Scope, system design, accessibility-first UX |
| `builder` | Implementation — app + computer-control engine |
| `safety-security` | Scam detection, permissions, privacy, the risky-action gate |
| `reviewer-qa` | Code review + testing on messy real-world cases |
| `tech-watcher` | Keeps Grandson current as macOS/apps change (the self-update job) |

**The safety policy in `docs/SAFETY.md` overrides every other goal.**

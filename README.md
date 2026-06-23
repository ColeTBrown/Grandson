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

## Milestones
- **M0 — Foundation** ✅ project + 5-agent dev team + safety policy
- **M1 — See & Explain** screen narration, no control yet (zero risk, builds trust)
- **M2 — Guided takeover** one real task end-to-end with risky-action gates live
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

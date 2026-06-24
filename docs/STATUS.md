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

## Next up — M1: "See & Explain"
Grandson takes a screenshot and narrates what's on the screen in plain language.
**No control yet** — zero risk, builds trust, proves the eyes + voice work before
we ever touch the mouse. macOS will prompt for **Screen Recording** permission.

Suggested division of labor:
- **builder** — implement the see -> understand -> explain loop (Claude vision).
- **safety-security** — stub the risky-action gate now so safety is wired in from
  the start, even though M1 has no control yet.
- **reviewer-qa** — check it explains clearly and handles a blank/odd screen.

## Then
- **M2** — guided takeover of one real task end-to-end, with the risky-action gates live.
- **M3** — always-on scam shield + the tech-watcher self-update job.

## How to drive the team
From a Claude Code session opened in this folder, dispatch by name, e.g.
"have **builder** start M1" or "have **safety-security** review this." The agent
definitions are in `.claude/agents/`.

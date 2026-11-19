# Grandson — browser extension

Grandson for the web browser. It works in Chrome and Edge, on Windows, Mac, and Chromebook.

- **Scam shield, always on.** Every page is checked for common scam tricks. If a page
  looks like a scam, a large warning covers the top of it with plain advice and the phone
  number of a trusted family member. This check runs inside the browser; nothing is sent anywhere.
- **Explain this page.** Click the Grandson icon to open a panel beside the page. One button
  explains the page in plain words. Another answers "Is this page safe?". You can also type a
  question, and have any answer read aloud.

Grandson only looks and explains. It cannot click, type, buy, or send anything.

## Try it (before it is in the Chrome Web Store)

1. Download this repository and unzip it.
2. In Chrome, go to `chrome://extensions` and switch on **Developer mode** (top right).
3. Click **Load unpacked** and choose the `extension` folder.
4. The settings page opens. Paste an Anthropic API key, add a family contact, and click **Save**.
5. Click the puzzle-piece icon in the toolbar and pin **Grandson**. Click its icon on any page.

The scam shield works without an API key. Explanations need one.

## What leaves the computer

| When | What is sent | To whom |
|------|--------------|---------|
| Browsing normally | Nothing | — |
| Pressing **Explain this page**, **Is this page safe?**, or **Ask** | A picture of the visible part of the page, up to 20,000 characters of its text, and its web address | Anthropic (Claude) |

The API key and family contact are kept in this browser's local extension storage. They are
not synced and web pages cannot read them.

## How the scam shield decides

The rules are in `src/scam-rules.js`. Each rule has **strong** signs (phrases scammers use and
honest pages rarely do) and **weak** signs (words like "gift card" that only matter in
combination).

- **Red banner:** two strong signs, or one strong sign plus other signs, or a web address
  that imitates a well-known company and asks for a password or card number.
- **Amber note** (toolbar badge and side panel only, no interruption): one strong sign, or
  several weak ones.
- Pages that talk *about* scams (news, advice) are stepped down one level.

This is deliberately stricter than the Mac app's shield, which flags any single keyword. A
shield that looks at every page all day must stay quiet on honest pages, or people learn to
ignore it.

## For developers

```bash
cd extension
npm install
npm run build      # bundles src/ into js/ (js/ is committed so the extension loads as-is)
npm test           # scam-rule unit tests
npm run test:e2e   # loads the extension in Chromium with a stand-in for Claude
```

The end-to-end test needs Playwright available to Node. It needs no API key.

| File | Job |
|------|-----|
| `src/scam-rules.js` | The shield's rules and scoring. No browser APIs, so it is unit-tested directly. |
| `src/content.js` | Runs on each page: scans it, shows the banner, hands page text to the panel on request. |
| `src/background.js` | Toolbar badge, closing a scam tab, opening the panel. |
| `src/sidepanel.js` | The panel: buttons, answers, read-aloud, text size. |
| `src/prompts.js` | Grandson's voice and safety instructions for Claude. |
| `src/claude.js` | Calls Claude through the official Anthropic SDK; turns errors into plain words. |
| `src/options.js` | Settings page. |

## Known limits

- Each person needs their own API key for now. A shared key cannot be hidden safely inside
  an extension; a small server would be needed for that.
- The shield knows common English-language tricks. It will miss some scams and can be wrong
  about honest pages. "No warning signs" is not a promise that a page is safe.
- It reads the main page only, not content inside embedded frames.
- It cannot read the browser's own pages (settings, new tab, the Web Store) or PDF files.

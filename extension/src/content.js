// Runs on every web page. Two jobs:
//   1. The always-on scam shield: read the page, and if it looks like a scam,
//      put a large, calm warning across the top (docs/SAFETY.md §2).
//   2. Hand the page's text to the side panel when the person asks Grandson to
//      explain it.
// The shield works entirely inside the browser. Nothing is sent anywhere.
import { scanPage, LEVEL } from "./scam-rules.js";

const SCAN_TEXT_LIMIT = 60000; // characters the shield reads
const SHARE_TEXT_LIMIT = 20000; // characters shared with Claude when asked
const RESCAN_GAP_MS = 2000;

let lastScan = { level: LEVEL.NONE, score: 0, findings: [] };
let dismissed = false;
let bannerHost = null;

function pageText() {
  return (document.body?.innerText || "").replace(/\n{3,}/g, "\n\n");
}

function pageFields() {
  const card =
    'input[autocomplete^="cc-"], input[name*="card" i][name*="num" i], input[id*="card" i][id*="num" i], input[name*="cvv" i], input[name*="cvc" i], input[placeholder*="card number" i]';
  return {
    password: Boolean(document.querySelector('input[type="password"]')),
    card: Boolean(document.querySelector(card)),
  };
}

function pageLinks() {
  return Array.from(document.links)
    .slice(0, 400)
    .map((a) => ({ text: (a.innerText || "").slice(0, 120), href: a.href }));
}

function runScan() {
  lastScan = scanPage({
    text: pageText().slice(0, SCAN_TEXT_LIMIT),
    url: location.href,
    links: pageLinks(),
    fields: pageFields(),
  });
  chrome.runtime.sendMessage({ type: "scan", result: lastScan }).catch(() => {});
  if (lastScan.level === LEVEL.DANGER && !dismissed) showBanner(lastScan);
  else if (lastScan.level !== LEVEL.DANGER) removeBanner();
}

// ---- The warning banner ----------------------------------------------------

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of children) node.append(child);
  return node;
}

function removeBanner() {
  bannerHost?.remove();
  bannerHost = null;
}

async function showBanner(scan) {
  if (bannerHost) return;
  // Reserve the spot immediately so two scans cannot both build a banner.
  const host = (bannerHost = document.createElement("div"));
  host.id = "grandson-scam-warning";
  // A closed shadow root keeps the page from restyling or hiding the warning.
  const root = host.attachShadow({ mode: "closed" });

  let family = {};
  try {
    family = (await chrome.storage.local.get(["familyName", "familyPhone"])) || {};
  } catch {
    /* extension was reloaded; show the banner without the contact */
  }
  if (bannerHost !== host) return; // cleared while we were waiting

  const style = el("style", {
    textContent: `
      :host { all: initial; }
      .wrap {
        position: fixed; top: 0; left: 0; right: 0; z-index: 2147483647;
        max-height: 80vh; overflow: auto; box-sizing: border-box;
        background: #7a1712; color: #fff; padding: 20px 24px 22px;
        font: 20px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        box-shadow: 0 6px 24px rgba(0,0,0,.5); border-bottom: 6px solid #ffd54a;
      }
      .inner { max-width: 900px; margin: 0 auto; }
      h1 { font-size: 28px; line-height: 1.25; margin: 0 0 8px; font-weight: 700; }
      p { margin: 8px 0; }
      ul { margin: 8px 0 8px 0; padding-left: 26px; }
      li { margin: 4px 0; }
      .do { background: rgba(0,0,0,.25); border-radius: 10px; padding: 10px 16px; margin: 12px 0; }
      .family { font-weight: 700; color: #ffe58a; }
      .buttons { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; }
      button {
        font: inherit; font-weight: 700; padding: 12px 20px; border-radius: 10px;
        border: 3px solid #fff; cursor: pointer; min-height: 52px;
      }
      button:focus-visible { outline: 4px solid #ffd54a; outline-offset: 2px; }
      .primary { background: #fff; color: #7a1712; }
      .secondary { background: transparent; color: #fff; }
      .quiet { background: transparent; color: #fff; border-color: transparent; text-decoration: underline; font-weight: 400; }
    `,
  });

  const reasons = el(
    "ul",
    {},
    scan.findings.slice(0, 3).map((f) => el("li", { textContent: f.reason })),
  );

  const advice = el("div", { className: "do" }, [
    el("p", {
      textContent:
        "Please do not call any phone number on this page, do not type a password or card number, and do not download anything.",
    }),
    el("p", { textContent: "You are safe. Nothing bad happens if you simply close this page." }),
  ]);

  if (family.familyName || family.familyPhone) {
    const who = family.familyName || "your family";
    const phone = family.familyPhone ? ` at ${family.familyPhone}` : "";
    advice.append(
      el("p", {
        className: "family",
        textContent: `Not sure? Call ${who}${phone} before you do anything.`,
      }),
    );
  }

  const closeBtn = el("button", { className: "primary", textContent: "Close this page" });
  closeBtn.addEventListener("click", () => chrome.runtime.sendMessage({ type: "closeTab" }));

  const askBtn = el("button", { className: "secondary", textContent: "Ask Grandson about it" });
  askBtn.addEventListener("click", () => chrome.runtime.sendMessage({ type: "openPanel" }).catch(() => {}));

  const hideBtn = el("button", { className: "quiet", textContent: "Hide this warning" });
  hideBtn.addEventListener("click", () => {
    dismissed = true;
    removeBanner();
  });

  root.append(
    style,
    el("div", { className: "wrap", role: "alertdialog", ariaLabel: "Scam warning from Grandson" }, [
      el("div", { className: "inner" }, [
        el("h1", { textContent: "Careful. This page looks like a scam." }),
        el("p", { textContent: "Grandson noticed these warning signs:" }),
        reasons,
        advice,
        el("div", { className: "buttons" }, [closeBtn, askBtn, hideBtn]),
      ]),
    ]),
  );
  document.documentElement.append(host);
}

// ---- Answer the side panel -------------------------------------------------

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== "getPage") return;
  const text = pageText();
  sendResponse({
    url: location.href,
    title: document.title,
    text: text.slice(0, SHARE_TEXT_LIMIT),
    truncated: text.length > SHARE_TEXT_LIMIT,
    fields: pageFields(),
    scan: lastScan,
  });
});

// ---- Keep watching: scam popups often appear a few seconds after loading ----

let timer = null;
let lastRun = 0;
function scheduleScan() {
  if (timer) return;
  const wait = Math.max(300, RESCAN_GAP_MS - (Date.now() - lastRun));
  timer = setTimeout(() => {
    timer = null;
    lastRun = Date.now();
    try {
      runScan();
    } catch {
      /* never let the shield break the page */
    }
  }, wait);
}

if (window.top === window) {
  runScan();
  lastRun = Date.now();
  new MutationObserver((records) => {
    // Ignore our own banner being added or removed.
    if (records.every((r) => r.target === document.documentElement && bannerHost)) return;
    scheduleScan();
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
}

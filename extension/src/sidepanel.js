// The side panel: three big buttons and a plain-language answer.
import { ask, makeClient, FriendlyError } from "./claude.js";
import { buildPageMessage } from "./prompts.js";

const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const talkEl = $("talk");

let conversation = null; // { tabId, url, messages: [] }
let busy = null; // AbortController while an answer is on its way
let lastAnswer = "";

// ---- Small helpers ---------------------------------------------------------

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of children) node.append(child);
  return node;
}

// Tests open this page in an ordinary tab and name the tab to look at.
const forcedTabId = Number(new URLSearchParams(location.search).get("tabId")) || null;

async function activeTab() {
  if (forcedTabId) return chrome.tabs.get(forcedTabId).catch(() => null);
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab || null;
}

const openSettings = (e) => {
  e?.preventDefault();
  chrome.runtime.openOptionsPage();
};

// ---- Text size -------------------------------------------------------------

async function applySize(change = 0) {
  const { textSize = 20 } = await chrome.storage.local.get("textSize");
  const size = Math.min(32, Math.max(16, textSize + change));
  document.documentElement.style.setProperty("--size", `${size}px`);
  if (change) chrome.storage.local.set({ textSize: size });
}

// ---- The safety card at the top --------------------------------------------

async function renderStatus() {
  const tab = await activeTab();
  const { familyName, familyPhone } = await chrome.storage.local.get(["familyName", "familyPhone"]);
  let scan = null;
  if (tab) {
    const key = `scan:${tab.id}`;
    scan = (await chrome.storage.session.get(key))[key] || null;
    // A verdict for a page the tab has since left is no verdict.
    if (scan && tab.url && scan.url !== tab.url) scan = null;
  }

  statusEl.replaceChildren();
  if (!scan) {
    statusEl.className = "card";
    statusEl.append(
      el("h2", { textContent: "I can't check this page" }),
      el("p", { textContent: "This is a kind of page I'm not able to read. Ordinary websites work fine." }),
    );
    return;
  }

  if (scan.level === "none") {
    statusEl.className = "card ok";
    statusEl.append(
      el("h2", { textContent: "No warning signs here" }),
      el("p", {
        textContent:
          "I don't see any of the usual scam tricks on this page. Still take care with passwords and money.",
      }),
    );
    return;
  }

  const danger = scan.level === "danger";
  statusEl.className = danger ? "card danger" : "card caution";
  statusEl.append(
    el("h2", { textContent: danger ? "Careful. This page looks like a scam." : "Take a little care here" }),
    el("p", {
      textContent: danger
        ? "Please don't call any number on it, don't type passwords or card numbers, and don't download anything. It is safe to simply close the page."
        : scan.educational
          ? "This page talks about scams. It is probably advice or news, but I noticed:"
          : "It may be perfectly fine, but I noticed:",
    }),
    el("ul", {}, scan.findings.slice(0, 3).map((f) => el("li", { textContent: f.reason }))),
  );
  if (familyName || familyPhone) {
    statusEl.append(
      el("p", {
        className: "family",
        textContent: `Not sure? Call ${familyName || "your family"}${familyPhone ? ` at ${familyPhone}` : ""} first.`,
      }),
    );
  }
}

// ---- Reading aloud ---------------------------------------------------------

function stopSpeaking() {
  speechSynthesis.cancel();
  $("stop").hidden = true;
  $("read").hidden = false;
}

function speak(text) {
  if (!text) return;
  speechSynthesis.cancel();
  const words = new SpeechSynthesisUtterance(text);
  words.rate = 0.9; // a touch slower than normal
  words.onend = words.onerror = stopSpeaking;
  $("read").hidden = true;
  $("stop").hidden = false;
  speechSynthesis.speak(words);
}

// ---- Asking Grandson -------------------------------------------------------

function setBusy(controller) {
  busy = controller;
  for (const id of ["explain", "safety", "ask"]) $(id).disabled = Boolean(controller);
}

async function readPage(tab) {
  let page = null;
  let screenshot = null;
  try {
    page = await chrome.tabs.sendMessage(tab.id, { type: "getPage" });
  } catch {
    /* browser's own pages, or a page opened before Grandson was installed */
  }
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "jpeg", quality: 70 });
    screenshot = dataUrl.split(",")[1] || null;
  } catch {
    /* some pages cannot be photographed */
  }
  return { page, screenshot };
}

async function run(mode, question = "") {
  if (busy) return;
  stopSpeaking();

  const { apiKey, autoRead } = await chrome.storage.local.get(["apiKey", "autoRead"]);
  if (!apiKey) {
    $("setup").hidden = false;
    $("setup").scrollIntoView({ behavior: "smooth" });
    return;
  }
  $("setup").hidden = true;

  const controller = new AbortController();
  setBusy(controller);

  const label = mode === "explain" ? "Explain this page" : mode === "safety" ? "Is this page safe?" : question;
  const reply = el("div", { className: "reply thinking", textContent: "Let me have a look…" });
  const turn = el("div", {}, [el("p", { className: "you", textContent: label }), reply]);
  talkEl.prepend(turn);
  $("controls").hidden = true;

  try {
    const tab = await activeTab();
    if (!tab) throw new FriendlyError("I couldn't find the page you're looking at. Click on the page and try again.");

    // A follow-up question about the same page continues the conversation;
    // anything else starts fresh with a new look at the page.
    const followUp =
      mode === "question" && conversation && conversation.tabId === tab.id && conversation.url === tab.url;

    if (followUp) {
      conversation.messages.push({ role: "user", content: question });
    } else {
      const { page, screenshot } = await readPage(tab);
      if (!page && !screenshot) {
        throw new FriendlyError(
          "I'm not able to look at this kind of page. If you just installed me, try reloading the page. Ordinary websites work fine.",
        );
      }
      conversation = {
        tabId: tab.id,
        url: tab.url,
        messages: [buildPageMessage({ mode, question, page, screenshot })],
      };
    }

    let text = "";
    const content = await ask({
      client: makeClient(apiKey),
      messages: conversation.messages,
      signal: controller.signal,
      onText: (delta) => {
        if (!text) reply.className = "reply";
        text += delta;
        reply.textContent = text;
      },
    });
    conversation.messages.push({ role: "assistant", content });

    lastAnswer = text.trim();
    reply.textContent = lastAnswer;
    $("controls").hidden = false;
    if (autoRead) speak(lastAnswer);
  } catch (err) {
    // The question that failed must not stay in the conversation.
    if (conversation?.messages.at(-1)?.role === "user") {
      if (conversation.messages.length === 1) conversation = null;
      else conversation.messages.pop();
    }
    const friendly = err instanceof FriendlyError ? err : new FriendlyError("Something went wrong. Let's try that again.");
    reply.className = "reply error";
    reply.textContent = friendly.message;
    if (friendly.needsSetup) $("setup").hidden = false;
  } finally {
    setBusy(null);
  }
}

// ---- Wiring ----------------------------------------------------------------

$("explain").addEventListener("click", () => run("explain"));
$("safety").addEventListener("click", () => run("safety"));
$("askForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const question = $("question").value.trim();
  if (!question) return $("question").focus();
  $("question").value = "";
  run("question", question);
});
$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("askForm").requestSubmit();
  }
});
$("read").addEventListener("click", () => speak(lastAnswer));
$("stop").addEventListener("click", stopSpeaking);
$("bigger").addEventListener("click", () => applySize(2));
$("smaller").addEventListener("click", () => applySize(-2));
$("openSettings").addEventListener("click", openSettings);
$("settingsLink").addEventListener("click", openSettings);

chrome.tabs.onActivated.addListener(renderStatus);
chrome.tabs.onUpdated.addListener((_id, change, tab) => {
  if (tab.active && (change.status || change.url)) renderStatus();
});
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session") renderStatus();
  if (area === "local") {
    if (changes.apiKey?.newValue) $("setup").hidden = true;
    if (changes.familyName || changes.familyPhone) renderStatus();
  }
});
window.addEventListener("pagehide", () => {
  speechSynthesis.cancel();
  busy?.abort();
});

applySize();
renderStatus();
chrome.storage.local.get("apiKey").then(({ apiKey }) => {
  $("setup").hidden = Boolean(apiKey);
});

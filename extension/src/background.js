// Background worker: keeps the toolbar badge in step with the scam shield and
// does the few things a page script is not allowed to do itself.
import { LEVEL } from "./scam-rules.js";

const scanKey = (tabId) => `scan:${tabId}`;

chrome.runtime.onInstalled.addListener(({ reason }) => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  // First install: go straight to the short setup page.
  if (reason === "install") chrome.runtime.openOptionsPage();
});

function setBadge(tabId, level) {
  const text = level === LEVEL.DANGER ? "!" : level === LEVEL.CAUTION ? "?" : "";
  const color = level === LEVEL.DANGER ? "#b3261e" : "#b26a00";
  chrome.action.setBadgeText({ tabId, text }).catch(() => {});
  if (text) chrome.action.setBadgeBackgroundColor({ tabId, color }).catch(() => {});
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const tabId = sender.tab?.id;
  if (!msg || tabId == null) return;

  if (msg.type === "scan") {
    // Only the top page reports; remember the verdict for the side panel.
    chrome.storage.session.set({ [scanKey(tabId)]: { ...msg.result, url: sender.tab.url } });
    setBadge(tabId, msg.result.level);
  } else if (msg.type === "closeTab") {
    // Open a fresh tab first so closing the last tab does not close the browser.
    chrome.tabs.create({}).finally(() => chrome.tabs.remove(tabId).catch(() => {}));
  } else if (msg.type === "openPanel") {
    chrome.sidePanel.open({ tabId }).then(
      () => sendResponse({ ok: true }),
      () => sendResponse({ ok: false }),
    );
    return true; // answer comes later
  }
});

chrome.tabs.onUpdated.addListener((tabId, change) => {
  // A new page is loading: the old verdict no longer applies.
  if (change.status === "loading" && change.url) {
    chrome.storage.session.remove(scanKey(tabId));
    setBadge(tabId, LEVEL.NONE);
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.session.remove(scanKey(tabId));
});

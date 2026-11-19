(() => {
  // src/scam-rules.js
  var LEVEL = { NONE: "none", CAUTION: "caution", DANGER: "danger" };

  // src/background.js
  var scanKey = (tabId) => `scan:${tabId}`;
  chrome.runtime.onInstalled.addListener(({ reason }) => {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {
    });
    if (reason === "install") chrome.runtime.openOptionsPage();
  });
  function setBadge(tabId, level) {
    const text = level === LEVEL.DANGER ? "!" : level === LEVEL.CAUTION ? "?" : "";
    const color = level === LEVEL.DANGER ? "#b3261e" : "#b26a00";
    chrome.action.setBadgeText({ tabId, text }).catch(() => {
    });
    if (text) chrome.action.setBadgeBackgroundColor({ tabId, color }).catch(() => {
    });
  }
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    const tabId = sender.tab?.id;
    if (!msg || tabId == null) return;
    if (msg.type === "scan") {
      chrome.storage.session.set({ [scanKey(tabId)]: { ...msg.result, url: sender.tab.url } });
      setBadge(tabId, msg.result.level);
    } else if (msg.type === "closeTab") {
      chrome.tabs.create({}).finally(() => chrome.tabs.remove(tabId).catch(() => {
      }));
    } else if (msg.type === "openPanel") {
      chrome.sidePanel.open({ tabId }).then(
        () => sendResponse({ ok: true }),
        () => sendResponse({ ok: false })
      );
      return true;
    }
  });
  chrome.tabs.onUpdated.addListener((tabId, change) => {
    if (change.status === "loading" && change.url) {
      chrome.storage.session.remove(scanKey(tabId));
      setBadge(tabId, LEVEL.NONE);
    }
  });
  chrome.tabs.onRemoved.addListener((tabId) => {
    chrome.storage.session.remove(scanKey(tabId));
  });
})();

// The settings page: API key, trusted family contact, read-aloud.
import { checkKey } from "./claude.js";

const $ = (id) => document.getElementById(id);

function notice(id, text, kind = "") {
  $(id).textContent = text;
  $(id).className = `notice ${kind}`;
}

async function load() {
  const saved = await chrome.storage.local.get(["apiKey", "familyName", "familyPhone", "autoRead"]);
  $("apiKey").value = saved.apiKey || "";
  $("familyName").value = saved.familyName || "";
  $("familyPhone").value = saved.familyPhone || "";
  $("autoRead").checked = Boolean(saved.autoRead);
}

async function save() {
  const apiKey = $("apiKey").value.trim();
  notice("keyNotice", "");
  notice("saveNotice", "");

  // Local storage, not synced storage: the key stays on this computer.
  await chrome.storage.local.set({
    apiKey,
    familyName: $("familyName").value.trim(),
    familyPhone: $("familyPhone").value.trim(),
    autoRead: $("autoRead").checked,
  });
  notice("saveNotice", "Saved.", "good");

  if (!apiKey) {
    notice("keyNotice", "No key yet. Scam warnings still work; explanations need a key.");
    return;
  }
  notice("keyNotice", "Checking the key…");
  try {
    await checkKey(apiKey);
    notice("keyNotice", "The key works. Grandson is ready.", "good");
  } catch (err) {
    notice("keyNotice", err.message, "bad");
  }
}

$("save").addEventListener("click", save);
$("showKey").addEventListener("change", (e) => {
  $("apiKey").type = e.target.checked ? "text" : "password";
});
load();

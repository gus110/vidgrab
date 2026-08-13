const APP_ENDPOINT = "http://127.0.0.1:8743";

async function sendToApp(url) {
  try {
    const res = await fetch(`${APP_ENDPOINT}/add-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    return res.ok;
  } catch (err) {
    return false;
  }
}

async function isAppRunning() {
  try {
    const res = await fetch(`${APP_ENDPOINT}/ping`, { method: "GET" });
    return res.ok;
  } catch (err) {
    return false;
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SEND_URL") {
    sendToApp(message.url)
      .then((ok) => sendResponse({ ok }))
      .catch(() => sendResponse({ ok: false }));
    return true; // async
  }
  if (message.type === "CHECK_APP") {
    isAppRunning()
      .then((ok) => sendResponse({ ok }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
});

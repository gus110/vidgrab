const dot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const listEl = document.getElementById("list");
const countLabel = document.getElementById("countLabel");
const sendBtn = document.getElementById("sendBtn");
const refreshBtn = document.getElementById("refreshBtn");
const selectAllBtn = document.getElementById("selectAllBtn");
const selectNoneBtn = document.getElementById("selectNoneBtn");

let currentVideos = [];

function checkAppRunning() {
  chrome.runtime.sendMessage({ type: "CHECK_APP" }, (response) => {
    if (response && response.ok) {
      dot.classList.add("ok");
      statusText.textContent = "VidGrab is running";
    } else {
      dot.classList.remove("ok");
      statusText.textContent = "Open the VidGrab app on your PC";
    }
  });
}

function renderList(videos) {
  currentVideos = videos;
  countLabel.textContent = `${videos.length} video${videos.length === 1 ? "" : "s"} found`;

  if (videos.length === 0) {
    listEl.innerHTML = `<div class="empty">No videos detected. Scroll through the feed and scan again.</div>`;
    sendBtn.disabled = true;
    return;
  }

  listEl.innerHTML = "";
  videos.forEach((v, idx) => {
    const item = document.createElement("label");
    item.className = "video-item";
    const thumbHtml = v.thumbnail
      ? `<img class="thumb" src="${v.thumbnail}" onerror="this.outerHTML='<div class=&quot;thumb-placeholder&quot;>🎬</div>'" />`
      : `<div class="thumb-placeholder">🎬</div>`;
    item.innerHTML = `
      <input type="checkbox" data-idx="${idx}" checked />
      ${thumbHtml}
      <div class="info">
        <span class="title" title="${v.title || v.url}">${v.title || v.url}</span>
        <span class="url" title="${v.url}">${v.url}</span>
      </div>
    `;
    listEl.appendChild(item);
  });
  sendBtn.disabled = false;
}

function setAllChecked(checked) {
  listEl.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = checked));
}

async function fetchDetectedVideos() {
  countLabel.textContent = "Scanning...";
  listEl.innerHTML = `<div class="empty">Scanning the page for videos...</div>`;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return renderList([]);

  chrome.tabs.sendMessage(tab.id, { type: "GET_DETECTED_VIDEOS" }, (response) => {
    if (chrome.runtime.lastError || !response) {
      listEl.innerHTML = `<div class="empty">Open an Instagram or TikTok page first.</div>`;
      countLabel.textContent = "0 videos found";
      sendBtn.disabled = true;
      return;
    }
    renderList(response.videos || []);
  });
}

sendBtn.addEventListener("click", () => {
  const checkboxes = listEl.querySelectorAll("input[type=checkbox]:checked");
  const selected = Array.from(checkboxes).map((cb) => currentVideos[Number(cb.dataset.idx)]);
  if (selected.length === 0) return;

  sendBtn.disabled = true;
  sendBtn.textContent = `Sending 0/${selected.length}...`;

  let sent = 0;
  let ok = 0;
  selected.forEach((v) => {
    chrome.runtime.sendMessage({ type: "SEND_URL", url: v.url }, (response) => {
      sent++;
      if (response && response.ok) ok++;
      sendBtn.textContent = `Sending ${sent}/${selected.length}...`;
      if (sent === selected.length) {
        sendBtn.textContent = `✅ ${ok}/${selected.length} sent to VidGrab`;
        setTimeout(() => {
          sendBtn.textContent = "Download selected";
          sendBtn.disabled = false;
        }, 2500);
      }
    });
  });
});

selectAllBtn.addEventListener("click", () => setAllChecked(true));
selectNoneBtn.addEventListener("click", () => setAllChecked(false));
refreshBtn.addEventListener("click", fetchDetectedVideos);

checkAppRunning();
fetchDetectedVideos();

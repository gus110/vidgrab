// Inyecta un botón "Descargar con VidGrab" sobre CADA video visible en pantalla
// (feed, perfil, reels, etc.) y detecta el enlace específico de cada publicación,
// no solo el de la página actual. También mantiene una lista de todos los videos
// detectados para que la extensión pueda mostrarlos y descargarlos en lote.

const detectedVideos = new Map(); // url -> { url, platform, label }

function normalizeInstagramUrl(href) {
  try {
    const u = new URL(href, window.location.origin);
    const match = u.pathname.match(/\/(p|reel|reels)\/[^/]+/);
    if (match) return `https://www.instagram.com${match[0]}/`;
  } catch (e) {}
  return null;
}

function normalizeTiktokUrl(href) {
  try {
    const u = new URL(href, window.location.origin);
    const match = u.pathname.match(/\/@[^/]+\/video\/\d+/);
    if (match) return `https://www.tiktok.com${match[0]}`;
  } catch (e) {}
  return null;
}

function normalizeUrl(href) {
  if (window.location.hostname.includes("instagram.com")) return normalizeInstagramUrl(href);
  if (window.location.hostname.includes("tiktok.com")) return normalizeTiktokUrl(href);
  return null;
}

function currentPageUrl() {
  return normalizeUrl(window.location.href) || window.location.href;
}

/**
 * Encuentra el contenedor visual de la publicación que envuelve un <video>,
 * ya sea en Instagram (<article>) o TikTok (tarjetas con data-e2e / clases
 * DivItemContainer). Se usa tanto para hallar el link del post como para
 * anclar el botón flotante — antes cada uso tenía su propia lógica
 * (una de ellas solo funcionaba en Instagram), por eso el botón no
 * aparecía en TikTok.
 */
function findContainerForVideo(videoEl) {
  return (
    videoEl.closest("article") ||
    videoEl.closest("div[data-e2e='recommend-list-item-container']") ||
    videoEl.closest("div[data-e2e]") ||
    videoEl.closest("[class*='DivItemContainer']") ||
    videoEl.closest("[class*='DivContainer']") ||
    videoEl.parentElement
  );
}

/**
 * Busca el enlace de publicación (post/reel) más cercano a un elemento <video>,
 * ya sea subiendo por sus ancestros o revisando los <a> dentro del mismo contenedor.
 * Si no encuentra ninguno específico, usa la URL de la página actual (caso de
 * estar ya dentro de un solo video/reel abierto).
 */
function findPostUrlForVideo(videoEl) {
  const container = findContainerForVideo(videoEl);

  if (container) {
    const links = container.querySelectorAll("a[href]");
    for (const a of links) {
      const normalized = normalizeUrl(a.href);
      if (normalized) return normalized;
    }
  }
  return currentPageUrl();
}

function firstUsableImgSrc(img) {
  if (!img) return "";
  // Instagram/TikTok a veces cargan la miniatura real en atributos "lazy"
  // (data-src) o en srcset en lugar de src, o como fondo CSS.
  const candidates = [img.currentSrc, img.src, img.getAttribute("data-src")];
  for (const c of candidates) {
    if (c && !c.startsWith("data:")) return c;
  }
  const srcset = img.getAttribute("srcset");
  if (srcset) {
    const first = srcset.split(",")[0].trim().split(" ")[0];
    if (first && !first.startsWith("data:")) return first;
  }
  return "";
}

function findThumbnailIn(container, videoEl) {
  if (videoEl && videoEl.poster) return videoEl.poster;
  if (!container) return "";

  const img = container.querySelector("img");
  const fromImg = firstUsableImgSrc(img);
  if (fromImg) return fromImg;

  const video = container.querySelector("video[poster]");
  if (video && video.poster) return video.poster;

  // Última opción: alguna miniatura usa background-image por CSS en vez de <img>.
  const withBg = container.querySelector("[style*='background-image']");
  if (withBg) {
    const match = withBg.style.backgroundImage.match(/url\(["']?(.*?)["']?\)/);
    if (match && match[1] && !match[1].startsWith("data:")) return match[1];
  }
  return "";
}

function findTitleIn(container, url) {
  const img = container && container.querySelector("img[alt]");
  const alt = img && img.getAttribute("alt");
  if (alt && alt.trim() && !/^photo by/i.test(alt.trim())) {
    return alt.trim().slice(0, 90);
  }
  // No description available: fall back to the post's short code as a name.
  const match = url.match(/\/(?:p|reel|reels|video)\/([^/?]+)/);
  return match ? `Post ${match[1]}` : url;
}

function registerVideo(url, thumbnail, title) {
  if (!url) return;
  const platform = url.includes("tiktok.com") ? "TikTok" : "Instagram";
  const existing = detectedVideos.get(url);
  detectedVideos.set(url, {
    url,
    platform,
    thumbnail: thumbnail || (existing && existing.thumbnail) || "",
    title: title || (existing && existing.title) || url,
  });
}

function createButton(targetVideo) {
  if (targetVideo.dataset.vidgrabAttached) return;
  targetVideo.dataset.vidgrabAttached = "true";

  const postUrl = findPostUrlForVideo(targetVideo);
  const container = findContainerForVideo(targetVideo);
  registerVideo(postUrl, findThumbnailIn(container, targetVideo), findTitleIn(container, postUrl));

  const btn = document.createElement("button");
  btn.className = "vidgrab-download-btn";
  btn.innerText = "⬇ VidGrab";
  btn.title = "Download this video with VidGrab";

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = findPostUrlForVideo(targetVideo);
    btn.innerText = "Sending...";
    chrome.runtime.sendMessage({ type: "SEND_URL", url }, (response) => {
      if (response && response.ok) {
        btn.innerText = "✅ Sent";
      } else {
        btn.innerText = "⚠ Open VidGrab";
      }
      setTimeout(() => (btn.innerText = "⬇ VidGrab"), 2000);
    });
  });

  // El botón se posiciona con position:fixed anclado a la posición real del
  // <video> en pantalla (en vez de insertarlo dentro de la tarjeta del post).
  // Esto evita que quede oculto/recortado por contenedores con overflow
  // hidden o layouts distintos entre Instagram y TikTok.
  const wrapper = document.createElement("div");
  wrapper.className = "vidgrab-btn-wrapper vidgrab-fixed";
  wrapper.appendChild(btn);
  document.body.appendChild(wrapper);

  const reposition = () => {
    const rect = targetVideo.getBoundingClientRect();
    const visible = rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight;
    if (!visible) {
      wrapper.style.display = "none";
      return;
    }
    wrapper.style.display = "block";
    wrapper.style.top = `${rect.top + 12}px`;
    wrapper.style.left = `${Math.max(8, rect.right - wrapper.offsetWidth - 12)}px`;
  };

  reposition();
  window.addEventListener("scroll", reposition, true);
  window.addEventListener("resize", reposition);
  const repositionInterval = setInterval(() => {
    if (!document.body.contains(targetVideo)) {
      clearInterval(repositionInterval);
      wrapper.remove();
      // TikTok reutiliza/recicla el mismo <video> al desplazarse entre
      // clips: si este nodo desaparece del DOM (aunque sea temporalmente),
      // liberamos la marca "ya tiene botón" para que, si vuelve a
      // aparecer (mismo nodo u otro), el próximo escaneo le cree uno nuevo.
      delete targetVideo.dataset.vidgrabAttached;
      return;
    }
    reposition();
  }, 400);
}

function scanForVideos() {
  document.querySelectorAll("video").forEach((v) => createButton(v));
  scanForVideoLinks();
}

/**
 * En cuadrículas (explorar, perfil) los videos no tienen <video> hasta que se
 * abren: son miniaturas <a href="/reel/xxx/"> o <a href="/p/xxx/"> con un
 * ícono de reproducción. Las detectamos igual para poder listarlas.
 */
function scanForVideoLinks() {
  const selectors =
    window.location.hostname.includes("tiktok.com")
      ? "a[href*='/video/']"
      : "a[href*='/reel/'], a[href*='/p/']";

  document.querySelectorAll(selectors).forEach((a) => {
    const normalized = normalizeUrl(a.href);
    if (normalized) {
      registerVideo(normalized, findThumbnailIn(a, null), findTitleIn(a, normalized));
    }
  });
}

const observer = new MutationObserver(() => scanForVideos());
observer.observe(document.body, { childList: true, subtree: true });

scanForVideos();
// Vuelve a escanear periódicamente porque Instagram/TikTok cargan video
// perezosamente al hacer scroll, y a veces sin disparar MutationObserver a tiempo.
setInterval(scanForVideos, 2000);

// Responde a la extensión (popup) cuando pide la lista de videos detectados
// en la página actual.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_DETECTED_VIDEOS") {
    scanForVideos();
    sendResponse({ videos: Array.from(detectedVideos.values()) });
    return true;
  }
});

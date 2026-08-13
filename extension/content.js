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

function normalizeFacebookUrl(href) {
  try {
    const u = new URL(href, window.location.origin);
    if (u.hostname.includes("fb.watch")) return u.href;

    // /watch/?v=123, o cualquier link con ?v= (a veces viene en la home "/")
    const watchId = u.searchParams.get("v");
    if (watchId) return `https://www.facebook.com/watch/?v=${watchId}`;

    // /permalink.php?story_fbid=X&id=Y  ó  /story.php?story_fbid=X&id=Y
    const storyFbid = u.searchParams.get("story_fbid");
    const ownerId = u.searchParams.get("id");
    if (storyFbid && ownerId) {
      return `https://www.facebook.com/permalink.php?story_fbid=${storyFbid}&id=${ownerId}`;
    }

    // /<user>/videos/<id>/, /videos/<id>/, /reel/<id>/
    const match = u.pathname.match(/\/(videos|reel)\/([^/?]+)/);
    if (match) return `https://www.facebook.com${match[0]}/`;
  } catch (e) {}
  return null;
}

function normalizeAmazonUrl(href) {
  try {
    const u = new URL(href, window.location.origin);
    // /dp/ASIN o /gp/product/ASIN -> URL canónica que yt-dlp reconoce.
    const match = u.pathname.match(/\/(?:[^/]+\/)?(dp|gp\/product)\/([A-Z0-9]{10})/i);
    if (match) return `${u.origin}/dp/${match[2]}/`;
  } catch (e) {}
  return null;
}

function normalizeUrl(href) {
  if (window.location.hostname.includes("instagram.com")) return normalizeInstagramUrl(href);
  if (window.location.hostname.includes("tiktok.com")) return normalizeTiktokUrl(href);
  if (window.location.hostname.includes("facebook.com") || window.location.hostname.includes("fb.watch")) {
    return normalizeFacebookUrl(href);
  }
  if (window.location.hostname.includes("amazon.")) return normalizeAmazonUrl(href);
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
  let platform = "Instagram";
  if (url.includes("tiktok.com")) platform = "TikTok";
  else if (url.includes("facebook.com") || url.includes("fb.watch")) platform = "Facebook";
  else if (url.includes("amazon.")) platform = "Amazon";
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
  scanAmazonShopVideos();
}

/**
 * Páginas de tienda de influencer en Amazon (amazon.com/shop/usuario)
 * muestran decenas de videos en cuadrícula, pero casi ninguno tiene un
 * <video> montado hasta que se reproduce (carga perezosa) ni un enlace
 * de página individual — solo existe un link directo al stream HLS,
 * embebido en el HTML de la página. Los detectamos ahí directamente.
 * No se puede emparejar cada uno con su miniatura exacta de forma
 * confiable (Amazon no expone esa relación en el marcado), así que se
 * listan de forma genérica.
 */
function scanAmazonShopVideos() {
  if (!window.location.hostname.includes("amazon.")) return;
  if (window.location.pathname.match(/\/(dp|gp\/product)\//i)) return; // ya cubierto por createButton

  const html = document.documentElement.innerHTML;
  const matches = [
    ...new Set(html.match(/https:\/\/m\.media-amazon\.com\/images\/S\/vse-vms-transcoding-artifact[^"'\\]+\.m3u8/g) || []),
  ];
  matches.forEach((url, i) => {
    registerVideo(url, "", `Amazon video ${i + 1}`);
  });
}

/**
 * En cuadrículas (explorar, perfil) los videos no tienen <video> hasta que se
 * abren: son miniaturas <a href="/reel/xxx/"> o <a href="/p/xxx/"> con un
 * ícono de reproducción. Las detectamos igual para poder listarlas.
 */
function scanForVideoLinks() {
  const host = window.location.hostname;
  // Amazon: cada página de producto es un único recurso descargable
  // (el reproductor se detecta como <video> vía scanForVideos, no como
  // enlaces sueltos), así que no hay nada que escanear aquí.
  if (host.includes("amazon.")) return;

  let selectors = "a[href*='/reel/'], a[href*='/p/']"; // Instagram default
  if (host.includes("tiktok.com")) {
    selectors = "a[href*='/video/']";
  } else if (host.includes("facebook.com") || host.includes("fb.watch")) {
    selectors = "a[href*='/videos/'], a[href*='/watch/'], a[href*='/watch?'], a[href*='/reel/']";
  }

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

/**
 * TikTok e Instagram son SPAs: navegar "atrás" o entre secciones casi nunca
 * recarga la página completa, solo cambia la URL con la History API. Eso
 * puede reutilizar/ocultar y volver a mostrar nodos <video> de formas que
 * el MutationObserver no detecta como "nuevos". Para no depender solo del
 * intervalo de 2s, forzamos un reescaneo inmediato cada vez que la URL
 * cambia, interceptando pushState/replaceState y el evento popstate
 * (botón atrás/adelante del navegador).
 */
let lastUrl = location.href;
function onPossibleNavigation() {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    setTimeout(scanForVideos, 300);
    setTimeout(scanForVideos, 1000);
  }
}
const _pushState = history.pushState;
history.pushState = function (...args) {
  _pushState.apply(this, args);
  onPossibleNavigation();
};
const _replaceState = history.replaceState;
history.replaceState = function (...args) {
  _replaceState.apply(this, args);
  onPossibleNavigation();
};
window.addEventListener("popstate", onPossibleNavigation);

// Responde a la extensión (popup) cuando pide la lista de videos detectados
// en la página actual.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_DETECTED_VIDEOS") {
    scanForVideos();
    sendResponse({ videos: Array.from(detectedVideos.values()) });
    return true;
  }
});

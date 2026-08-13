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

function normalizeYoutubeUrl(href) {
  try {
    const u = new URL(href, window.location.origin);
    if (u.hostname.includes("youtu.be")) {
      const id = u.pathname.slice(1);
      if (id) return `https://youtu.be/${id}`;
    }
    const v = u.searchParams.get("v");
    if (v) return `https://www.youtube.com/watch?v=${v}`;
    const shorts = u.pathname.match(/\/shorts\/([^/?]+)/);
    if (shorts) return `https://www.youtube.com/shorts/${shorts[1]}`;
  } catch (e) {}
  return null;
}

function normalizePinterestUrl(href) {
  try {
    const u = new URL(href, window.location.origin);
    if (u.hostname.includes("pin.it")) return u.href;
    const match = u.pathname.match(/\/pin\/(\d+)/);
    if (match) return `${u.origin}/pin/${match[1]}/`;
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
  if (window.location.hostname.includes("youtube.com") || window.location.hostname.includes("youtu.be")) {
    return normalizeYoutubeUrl(href);
  }
  if (window.location.hostname.includes("pinterest.") || window.location.hostname.includes("pin.it")) {
    return normalizePinterestUrl(href);
  }
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
  else if (url.includes("youtube.com") || url.includes("youtu.be")) platform = "YouTube";
  else if (url.includes("pinterest.") || url.includes("pin.it")) platform = "Pinterest";
  const existing = detectedVideos.get(url);
  detectedVideos.set(url, {
    url,
    platform,
    thumbnail: thumbnail || (existing && existing.thumbnail) || "",
    title: title || (existing && existing.title) || url,
  });
}

/**
 * Crea el botón flotante "⬇ VidGrab" anclado (position:fixed) sobre la
 * posición real en pantalla de `anchorEl`. Se reutiliza tanto para <video>
 * (Instagram/TikTok/Facebook) como para miniaturas estáticas sin <video>
 * montado (tarjetas de tienda de Amazon) — `resolveUrl` es una función que
 * devuelve la URL a enviar, evaluada en el momento del clic.
 */
function createFixedButton(anchorEl, resolveUrl) {
  const btn = document.createElement("button");
  btn.className = "vidgrab-download-btn";
  btn.innerText = "⬇ VidGrab";
  btn.title = "Download this video with VidGrab";

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = resolveUrl();
    if (!url) {
      btn.innerText = "⚠ No link found";
      setTimeout(() => (btn.innerText = "⬇ VidGrab"), 2000);
      return;
    }
    btn.innerText = "Sending...";

    // Si la extensión se recargó (chrome://extensions) mientras esta
    // pestaña seguía abierta, el canal de mensajes queda roto y
    // sendMessage lanza "Extension context invalidated" de forma
    // SÍNCRONA — sin este try/catch, el botón se quedaba congelado en
    // "Sending..." para siempre, sin ningún aviso de qué pasó.
    let responded = false;
    try {
      chrome.runtime.sendMessage({ type: "SEND_URL", url }, (response) => {
        responded = true;
        if (chrome.runtime.lastError) {
          btn.innerText = "⚠ Reload page";
          setTimeout(() => (btn.innerText = "⬇ VidGrab"), 2500);
          return;
        }
        if (response && response.ok) {
          btn.innerText = "✅ Sent";
        } else {
          btn.innerText = "⚠ Open VidGrab";
        }
        setTimeout(() => (btn.innerText = "⬇ VidGrab"), 2000);
      });
    } catch (err) {
      btn.innerText = "⚠ Reload page";
      setTimeout(() => (btn.innerText = "⬇ VidGrab"), 2500);
      return;
    }

    // Salvaguarda adicional: si por algún motivo el callback nunca llega
    // (puerto cerrado sin error explícito), no dejar el botón colgado
    // más de unos segundos.
    setTimeout(() => {
      if (!responded) btn.innerText = "⚠ Reload page";
    }, 6000);
  });

  const wrapper = document.createElement("div");
  wrapper.className = "vidgrab-btn-wrapper vidgrab-fixed";
  wrapper.appendChild(btn);
  document.body.appendChild(wrapper);

  const reposition = () => {
    const rect = anchorEl.getBoundingClientRect();
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
    if (!document.body.contains(anchorEl)) {
      clearInterval(repositionInterval);
      wrapper.remove();
      // TikTok reutiliza/recicla el mismo <video> al desplazarse entre
      // clips: si este nodo desaparece del DOM (aunque sea temporalmente),
      // liberamos la marca "ya tiene botón" para que, si vuelve a
      // aparecer (mismo nodo u otro), el próximo escaneo le cree uno nuevo.
      delete anchorEl.dataset.vidgrabAttached;
      return;
    }
    reposition();
  }, 400);
}

/**
 * Crea el botón "⬇ VidGrab" pegado DENTRO del propio elemento (miniatura o
 * tarjeta), en vez de flotando por separado con position:fixed. Se usa para
 * cuadrículas con muchos videos a la vez (Pinterest, explorar de
 * Instagram/TikTok/Facebook, tienda de Amazon): con decenas de botones
 * flotantes independientes reposicionándose cada 400ms, el reacomodo
 * constante del layout (masonry) hacía que dos terminaran superpuestos en
 * el mismo lugar de la pantalla — el usuario creía hacer clic en un video
 * nuevo, pero en realidad tocaba el botón viejo que había quedado encima,
 * y por eso siempre bajaba el mismo video. Al vivir dentro del propio
 * elemento, el botón se mueve exactamente con su tarjeta, sin drift.
 */
function createInlineButton(anchorEl, resolveUrl) {
  const btn = document.createElement("button");
  btn.className = "vidgrab-download-btn";
  btn.innerText = "⬇ VidGrab";
  // El tooltip muestra el link exacto detectado para ESTE botón — sirve
  // para diagnosticar si dos botones distintos resuelven, por error, a la
  // misma URL (bug de detección) en vez de a URLs distintas (bug en otra
  // parte). Se recalcula en cada hover para reflejar el estado más actual.
  btn.addEventListener("mouseenter", () => {
    const u = resolveUrl();
    btn.title = u ? `Download: ${u}` : "No link detected";
  });

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = resolveUrl();
    console.log("[VidGrab click]", "sending:", url, "| anchor element:", anchorEl);
    if (!url) {
      btn.innerText = "⚠ No link found";
      setTimeout(() => (btn.innerText = "⬇ VidGrab"), 2000);
      return;
    }
    btn.innerText = "Sending...";
    let responded = false;
    try {
      chrome.runtime.sendMessage({ type: "SEND_URL", url }, (response) => {
        responded = true;
        if (chrome.runtime.lastError) {
          btn.innerText = "⚠ Reload page";
          setTimeout(() => (btn.innerText = "⬇ VidGrab"), 2500);
          return;
        }
        btn.innerText = response && response.ok ? "✅ Sent" : "⚠ Open VidGrab";
        setTimeout(() => (btn.innerText = "⬇ VidGrab"), 2000);
      });
    } catch (err) {
      btn.innerText = "⚠ Reload page";
      setTimeout(() => (btn.innerText = "⬇ VidGrab"), 2500);
      return;
    }
    setTimeout(() => {
      if (!responded) btn.innerText = "⚠ Reload page";
    }, 6000);
  });

  const wrapper = document.createElement("div");
  wrapper.className = "vidgrab-btn-wrapper";
  wrapper.appendChild(btn);

  const computedPosition = getComputedStyle(anchorEl).position;
  if (computedPosition === "static") {
    anchorEl.style.position = "relative";
  }
  anchorEl.appendChild(wrapper);
}

function createButton(targetVideo) {
  if (targetVideo.dataset.vidgrabAttached) return;
  targetVideo.dataset.vidgrabAttached = "true";

  const postUrl = findPostUrlForVideo(targetVideo);
  const container = findContainerForVideo(targetVideo);
  registerVideo(postUrl, findThumbnailIn(container, targetVideo), findTitleIn(container, postUrl));

  createFixedButton(targetVideo, () => findPostUrlForVideo(targetVideo));
}

function scanForVideos() {
  // En Pinterest, cada miniatura ya trae su propio <a href="/pin/..."> y
  // eso es lo único confiable para saber a qué pin corresponde. Los <video>
  // de vista previa que Pinterest reproduce en la cuadrícula NO están
  // dentro de un contenedor que nuestra búsqueda genérica (pensada para
  // Instagram/TikTok) sepa asociar correctamente a su pin — terminaba
  // cayendo al link de la página actual (el pin principal abierto) para
  // CUALQUIER video, creando además un segundo botón invisible superpuesto
  // al correcto. Por eso aquí se salta por completo la detección basada en
  // <video> y se deja solo la basada en <a href> (scanForVideoLinks).
  if (!window.location.hostname.includes("pinterest.") && !window.location.hostname.includes("pin.it")) {
    document.querySelectorAll("video").forEach((v) => createButton(v));
  }
  scanForVideoLinks();
  scanAmazonShopVideos();
}

/**
 * Páginas de tienda de influencer en Amazon (amazon.com/shop/usuario) y sus
 * colecciones filtradas ("curation") muestran videos en cuadrícula sin
 * <video> montado ni link de página individual. Cada tarjeta SÍ trae un
 * atributo "data-video-item-click" con un JSON exacto: el link real del
 * video (.m3u8), su miniatura y su título — mucho más confiable que tratar
 * de emparejar por orden en la página (que falla al filtrar/navegar, ya
 * que Amazon deja datos de vistas anteriores mezclados en el HTML).
 */
function scanAmazonShopVideos() {
  if (!window.location.hostname.includes("amazon.")) return;
  if (window.location.pathname.match(/\/(dp|gp\/product)\//i)) return; // ya cubierto por createButton

  document.querySelectorAll("[data-video-item-click]").forEach((el) => {
    if (el.dataset.vidgrabAttached) return;

    let data;
    try {
      data = JSON.parse(el.getAttribute("data-video-item-click"));
    } catch (e) {
      return;
    }
    const params = data && data.lightboxParams;
    const url = params && params.videoUrl;
    if (!url) return;

    el.dataset.vidgrabAttached = "true";
    registerVideo(url, params.imageUrl || "", params.title || "Amazon video");

    // El botón se ancla sobre la miniatura visible más cercana dentro de
    // esta tarjeta (si no hay una, se usa el propio elemento con los datos).
    const anchor = el.closest("[class*='thumbnail-container'], [class*='item-thumbnail']") || el;
    createInlineButton(anchor, () => url);
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
  } else if (host.includes("youtube.com") || host.includes("youtu.be")) {
    selectors = "a[href*='watch?v='], a[href*='/shorts/']";
  } else if (host.includes("pinterest.") || host.includes("pin.it")) {
    selectors = "a[href*='/pin/']";
  }

  document.querySelectorAll(selectors).forEach((a) => {
    const normalized = normalizeUrl(a.href);
    if (!normalized) return;
    console.log("[VidGrab detect]", a.href, "->", normalized, a);
    registerVideo(normalized, findThumbnailIn(a, null), findTitleIn(a, normalized));

    // Ancla el botón flotante directamente sobre esta miniatura de la
    // cuadrícula (antes solo se listaba en el popup sin marca visual sobre
    // el video — pasaba en Pinterest, y en general en cualquier cuadrícula
    // donde el video aún no tiene un <video> montado).
    //
    // IMPORTANTE: Pinterest (y otros feeds infinitos) reciclan el mismo
    // elemento <a> para pines distintos al hacer scroll (igual que TikTok
    // recicla su <video>). Si el link a enviar se "congela" al crear el
    // botón, terminaba descargando el video viejo que tenía ese elemento
    // reciclado la primera vez, no el que se ve ahora. Por eso se vuelve a
    // leer `a.href` en el momento del clic en vez de guardar un valor fijo.
    if (!a.dataset.vidgrabAttached) {
      a.dataset.vidgrabAttached = "true";
      // Ancla el botón a la <img> visible dentro del link, no al <a>
      // completo: en Pinterest el <a> de cada pin a veces envuelve un área
      // más grande que la miniatura que realmente se ve (padding/gutter de
      // la cuadrícula incluido), así que el botón terminaba dibujado
      // encima de la tarjeta vecina aunque su link fuera el correcto.
      const img = a.querySelector("img");
      const positionHost = img || a;
      if (positionHost !== a) positionHost.dataset.vidgrabAttached = "true";
      createInlineButton(positionHost, () => normalizeUrl(a.href) || normalized);
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

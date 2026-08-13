"""Motor de descarga basado en yt-dlp, con soporte para Instagram y TikTok."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

SUPPORTED_DOMAINS = (
    "instagram.com", "tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
    "facebook.com", "fb.watch",
    "amazon.com", "amazon.co.uk", "amazon.de", "amazon.ca", "amazon.es",
    "youtube.com", "youtu.be",
)


def _find_ffmpeg() -> str | None:
    """Busca ffmpeg en el PATH y, si no está, en la ubicación típica de winget."""
    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).parent)
    winget_root = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget_root.exists():
        for exe in winget_root.rglob("ffmpeg.exe"):
            return str(exe.parent)
    return None


FFMPEG_LOCATION = _find_ffmpeg()


def is_supported_url(url: str) -> bool:
    url = url.strip().lower()
    return url.startswith("http") and any(d in url for d in SUPPORTED_DOMAINS)


def detect_platform(url: str) -> str:
    url = url.lower()
    if "tiktok" in url:
        return "TikTok"
    if "instagram" in url:
        return "Instagram"
    if "facebook" in url or "fb.watch" in url:
        return "Facebook"
    if "amazon." in url:
        return "Amazon"
    if "youtube.com" in url or "youtu.be" in url:
        return "YouTube"
    return "Unknown"


@dataclass
class DownloadJob:
    id: str
    url: str
    platform: str
    status: str = "en cola"       # en cola | descargando | completado | error
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    title: str = ""
    filepath: str = ""
    error: str = ""
    thumbnail_url: str = ""
    uploader: str = ""


class DownloadManager:
    """Gestiona la cola de descargas en hilos separados para no bloquear la UI."""

    def __init__(self, download_dir: str, quality: str = "best", sharpen: bool = False):
        self.download_dir = download_dir
        self.quality = quality
        self.sharpen = sharpen
        self.jobs: dict[str, DownloadJob] = {}
        self._lock = threading.Lock()

    def set_download_dir(self, path: str):
        self.download_dir = path

    def set_quality(self, quality: str):
        self.quality = quality

    def set_sharpen(self, enabled: bool):
        self.sharpen = enabled

    def _format_selector(self) -> str:
        mapping = {
            "best": "bestvideo+bestaudio/best",
            "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "audio": "bestaudio/best",
        }
        return mapping.get(self.quality, mapping["best"])

    def enqueue(self, url: str, on_update: Callable[[DownloadJob], None]) -> str:
        job_id = str(uuid.uuid4())[:8]
        job = DownloadJob(id=job_id, url=url, platform=detect_platform(url))
        with self._lock:
            self.jobs[job_id] = job
        thread = threading.Thread(
            target=self._run_download, args=(job, on_update), daemon=True
        )
        thread.start()
        return job_id

    def _run_download(self, job: DownloadJob, on_update: Callable[[DownloadJob], None]):
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)
        job.status = "descargando"

        # Trae primero solo los metadatos (título, miniatura, autor) para que
        # la fila se vea completa desde el inicio, no solo al terminar.
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl_meta:
                meta = ydl_meta.extract_info(job.url, download=False)
                job.title = meta.get("title") or job.url
                job.thumbnail_url = meta.get("thumbnail") or ""
                job.uploader = meta.get("uploader") or meta.get("channel") or ""
        except Exception:
            pass
        on_update(job)

        def progress_hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total:
                    job.progress = downloaded / total
                job.speed = _human_speed(d.get("speed"))
                job.eta = _human_eta(d.get("eta"))
                on_update(job)
            elif d.get("status") == "finished":
                job.progress = 1.0
                on_update(job)

        is_amazon = job.platform == "Amazon"

        # Amazon no trae un "autor/uploader" real (siempre sale "NA"), así
        # que ahí se omite ese prefijo del nombre de archivo. En su lugar
        # se agrega el ID corto del job: varios videos de una misma tienda
        # suelen compartir el MISMO título exacto, y sin este ID sus
        # archivos chocan/se sobrescriben entre sí al descargar varios casi
        # al mismo tiempo (causaba errores intermitentes en lotes de Amazon).
        outtmpl = str(
            Path(self.download_dir) / (
                f"%(title).70s [{job.id}].%(ext)s" if is_amazon
                else "%(uploader)s - %(title).80s.%(ext)s"
            )
        )

        ydl_opts = {
            # Amazon sirve el video como HLS (.m3u8) con un único formato
            # combinado; el selector bestvideo+bestaudio no aplica ahí.
            "format": "best" if is_amazon else (
                self._format_selector() if job_quality_is_video(self.quality) else "bestaudio/best"
            ),
            "outtmpl": outtmpl,
            "progress_hooks": [progress_hook],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            "restrictfilenames": False,
            "windowsfilenames": True,
        }
        if is_amazon:
            # Fuerza a FFmpeg a descargar/remuxear el HLS en vez del
            # descargador nativo, que en Amazon solo bajaba el índice
            # .m3u8 sin los fragmentos de video reales.
            ydl_opts["hls_prefer_native"] = False
        if FFMPEG_LOCATION:
            ydl_opts["ffmpeg_location"] = FFMPEG_LOCATION
        if self.quality == "audio":
            ydl_opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(job.url, download=True)
                job.title = info.get("title", job.url)
                job.filepath = ydl.prepare_filename(info)
                job.filepath = _fix_hls_extension(job.filepath)
                job.status = "completado"
                job.progress = 1.0

            if self.sharpen and self.quality != "audio" and job.filepath:
                job.status = "descargando"
                job.speed = "sharpening..."
                on_update(job)
                _apply_sharpen_filter(job.filepath)
                job.status = "completado"
                job.speed = ""
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = _friendly_error(str(exc))
        finally:
            on_update(job)

    def get_job(self, job_id: str) -> Optional[DownloadJob]:
        return self.jobs.get(job_id)


def job_quality_is_video(quality: str) -> bool:
    return quality != "audio"


_BOGUS_EXTENSIONS = {".m3u8", ".na", ""}


def _fix_hls_extension(filepath: str) -> str:
    """Fuentes HLS (como Amazon) a veces reportan un nombre de archivo con
    extensión inválida (.m3u8, .NA) aunque el contenido real ya sea un
    .mp4 válido (FFmpeg remuxeó el stream) — y a veces ese nombre ni
    siquiera coincide exactamente con el archivo que quedó en disco. Si
    detectamos una extensión "rara", buscamos el archivo real por su
    nombre base y lo renombramos a .mp4."""
    path = Path(filepath)
    if path.suffix.lower() not in _BOGUS_EXTENSIONS:
        return filepath

    candidate = path if path.exists() else None
    if candidate is None:
        # El nombre reportado no coincide exactamente con el real (yt-dlp
        # a veces usa metadata distinta para el archivo final que para el
        # nombre "oficial" en streams HLS). Busca por coincidencia parcial
        # del inicio del nombre, y si no hay match, cae al archivo más
        # reciente de la carpeta (recién escrito por esta misma descarga).
        prefix = path.stem[:20].lower()
        try:
            all_files = [p for p in path.parent.glob("*.*") if p.is_file()]
            all_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            all_files = []
        candidate = next(
            (p for p in all_files if p.stem.lower().startswith(prefix)), None
        ) or (all_files[0] if all_files else None)

    if not candidate or not candidate.exists():
        return filepath

    new_path = candidate.with_suffix(".mp4")
    try:
        if new_path.exists() and new_path != candidate:
            new_path.unlink()
        candidate.rename(new_path)
        return str(new_path)
    except OSError:
        return str(candidate)


def _apply_sharpen_filter(filepath: str) -> None:
    """Pasa el video ya descargado por un filtro de nitidez de FFmpeg
    (unsharp) y reemplaza el archivo original. Si algo falla (FFmpeg no
    disponible, formato no soportado), deja el archivo original intacto
    en vez de romper la descarga."""
    if not FFMPEG_LOCATION:
        return
    src = Path(filepath)
    if not src.exists():
        return

    ffmpeg_exe = str(Path(FFMPEG_LOCATION) / "ffmpeg.exe")
    tmp_out = src.with_name(src.stem + "_sharpened" + src.suffix)

    cmd = [
        ffmpeg_exe, "-y", "-i", str(src),
        "-vf", "unsharp=5:5:0.8:5:5:0.4",
        "-c:a", "copy",
        str(tmp_out),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0 and tmp_out.exists() and tmp_out.stat().st_size > 0:
            src.unlink()
            tmp_out.rename(src)
        else:
            tmp_out.unlink(missing_ok=True)
    except Exception:
        tmp_out.unlink(missing_ok=True)


def _human_speed(speed_bytes) -> str:
    if not speed_bytes:
        return ""
    mb = speed_bytes / 1024 / 1024
    return f"{mb:.1f} MB/s"


def _human_eta(seconds) -> str:
    if not seconds:
        return ""
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s" if m else f"{s}s"


def _friendly_error(msg: str) -> str:
    msg_low = msg.lower()
    if "private" in msg_low:
        return "This content is private or unavailable."
    if "login" in msg_low or "rate-limit" in msg_low:
        return "The platform blocked the request (rate limit). Try again later."
    if "unsupported url" in msg_low:
        return "This link isn't from Instagram or TikTok, or isn't valid."
    return "Couldn't download this video. Check the link and try again."

"""
VidGrab — Descargador profesional de videos de Instagram y TikTok para Windows.
Interfaz de escritorio (CustomTkinter) + servidor local para la extensión de navegador.
"""
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

import io
import threading

import customtkinter as ctk
import requests
from PIL import Image
from tkinter import filedialog, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    load_config, save_config, load_history, save_history,
    APP_NAME, APP_VERSION, FREE_DAILY_LIMIT,
)
from downloader import DownloadManager, DownloadJob, is_supported_url, detect_platform
from server import run_server, incoming_queue
from license import validate_key
from datetime import date

GUMROAD_URL = "https://gumroad.com"  # reemplaza por tu link real de venta

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT = "#6C5CE7"
ACCENT_HOVER = "#5849C4"
BG_CARD = "#1E1E2A"
BG_MAIN = "#141420"
SUCCESS = "#2ECC71"
ERROR = "#E74C3C"
TEXT_MUTED = "#8A8AA3"


class JobRow(ctk.CTkFrame):
    """Fila visual que representa una descarga en curso o finalizada."""

    THUMB_SIZE = (56, 56)

    def __init__(self, master, job: DownloadJob, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10, **kwargs)
        self.job = job
        self._thumb_loaded_url = None

        self.grid_columnconfigure(1, weight=1)

        badge = "🎵" if job.platform == "TikTok" else ("📷" if job.platform == "Instagram" else "🎬")
        self.icon_lbl = ctk.CTkLabel(
            self, text=badge, font=("Segoe UI", 22), width=self.THUMB_SIZE[0],
            height=self.THUMB_SIZE[1], fg_color="#26263A", corner_radius=8,
        )
        self.icon_lbl.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=10)

        self.title_lbl = ctk.CTkLabel(
            self, text=job.url, font=("Segoe UI", 12, "bold"),
            anchor="w", justify="left", text_color="white",
        )
        self.title_lbl.grid(row=0, column=1, sticky="ew", padx=6, pady=(10, 0))

        self.status_lbl = ctk.CTkLabel(
            self, text=f"{job.platform} · queued", font=("Segoe UI", 10),
            anchor="w", text_color=TEXT_MUTED,
        )
        self.status_lbl.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 10))

        self.progress = ctk.CTkProgressBar(self, width=140, height=6, progress_color=ACCENT)
        self.progress.set(0)
        self.progress.grid(row=0, column=2, rowspan=2, padx=(6, 12))

        self.action_btn = ctk.CTkButton(
            self, text="⏳", width=32, height=32, fg_color="transparent",
            hover_color="#2A2A3C", command=self._on_action,
        )
        self.action_btn.grid(row=0, column=3, rowspan=2, padx=(0, 12))

    def _on_action(self):
        if self.job.status == "completado" and self.job.filepath:
            folder = str(Path(self.job.filepath).parent)
            if os.name == "nt":
                subprocess.Popen(f'explorer /select,"{self.job.filepath}"')
            else:
                webbrowser.open(folder)

    def update_view(self, job: DownloadJob):
        self.job = job
        self.progress.set(job.progress)

        if job.title:
            self.title_lbl.configure(text=job.title)
        source = job.uploader or job.platform

        if job.status == "en cola":
            self.status_lbl.configure(text=f"{source} · queued", text_color=TEXT_MUTED)
            self.action_btn.configure(text="⏳")
        elif job.status == "descargando":
            extra = f" · {job.speed}" if job.speed else ""
            eta = f" · ETA {job.eta}" if job.eta else ""
            self.status_lbl.configure(
                text=f"{source} · downloading {int(job.progress*100)}%{extra}{eta}",
                text_color=ACCENT,
            )
            self.action_btn.configure(text="⬇")
        elif job.status == "completado":
            self.status_lbl.configure(text=f"{source} · ✅ done", text_color=SUCCESS)
            self.action_btn.configure(text="📂")
        elif job.status == "error":
            self.status_lbl.configure(text=f"{source} · ❌ {job.error}", text_color=ERROR)
            self.action_btn.configure(text="⚠")

        self._maybe_load_thumbnail()

    def _maybe_load_thumbnail(self):
        url = self.job.thumbnail_url
        if not url or url == self._thumb_loaded_url:
            return
        self._thumb_loaded_url = url
        threading.Thread(target=self._fetch_thumbnail, args=(url,), daemon=True).start()

    def _fetch_thumbnail(self, url: str):
        try:
            resp = requests.get(url, timeout=6)
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            img = img.resize(self.THUMB_SIZE)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=self.THUMB_SIZE)
        except Exception:
            return

        def _apply():
            if self.winfo_exists():
                self.icon_lbl.configure(image=ctk_img, text="")
        try:
            self.after(0, _apply)
        except Exception:
            pass


class VidGrabApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.history = load_history()

        self.title(f"{APP_NAME} — Instagram & TikTok Downloader")
        self.geometry("760x620")
        self.minsize(640, 480)
        self.configure(fg_color=BG_MAIN)

        self.manager = DownloadManager(self.cfg["download_dir"], self.cfg["quality"])
        self.rows: dict[str, JobRow] = {}

        self._build_ui()
        run_server(self.cfg["server_port"])
        self.after(500, self._poll_extension_queue)

    # ---------- UI ----------
    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))

        ctk.CTkLabel(
            header, text="VidGrab", font=("Segoe UI", 26, "bold"), text_color="white"
        ).pack(side="left")
        ctk.CTkLabel(
            header, text=f"v{APP_VERSION}", font=("Segoe UI", 11), text_color=TEXT_MUTED
        ).pack(side="left", padx=(8, 0), pady=(10, 0))

        if self.cfg.get("is_pro"):
            ctk.CTkLabel(
                header, text="✨ PRO", font=("Segoe UI", 11, "bold"), text_color="#FFD166",
                fg_color="#3A3220", corner_radius=6, padx=8, pady=2,
            ).pack(side="left", padx=(10, 0))
        else:
            self.upgrade_btn = ctk.CTkButton(
                header, text="✨ Go Pro", width=110, fg_color="#3A3220",
                text_color="#FFD166", hover_color="#4A4228",
                command=self._open_upgrade_dialog,
            )
            self.upgrade_btn.pack(side="right", padx=(8, 0))

        settings_btn = ctk.CTkButton(
            header, text="⚙ Settings", width=90, fg_color="transparent",
            border_width=1, border_color="#3A3A4E", hover_color="#2A2A3C",
            command=self._open_settings,
        )
        settings_btn.pack(side="right")

        self.quota_label = ctk.CTkLabel(
            header, text="", font=("Segoe UI", 11), text_color=TEXT_MUTED
        )
        if not self.cfg.get("is_pro"):
            self.quota_label.pack(side="right", padx=(0, 10))
            self._refresh_quota_label()

        # Input row
        input_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        input_frame.pack(fill="x", padx=24, pady=10)

        self.url_entry = ctk.CTkEntry(
            input_frame, placeholder_text="Paste Instagram or TikTok link here...",
            height=44, font=("Segoe UI", 13), fg_color="#26263A", border_width=0,
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=12)
        self.url_entry.bind("<Return>", lambda e: self._on_download_click())

        self.download_btn = ctk.CTkButton(
            input_frame, text="Download", width=120, height=44,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, font=("Segoe UI", 13, "bold"),
            command=self._on_download_click,
        )
        self.download_btn.pack(side="right", padx=(0, 12), pady=12)

        # Quality selector
        options_frame = ctk.CTkFrame(self, fg_color="transparent")
        options_frame.pack(fill="x", padx=24, pady=(0, 10))

        ctk.CTkLabel(options_frame, text="Quality:", text_color=TEXT_MUTED).pack(side="left")
        self.quality_var = ctk.StringVar(value=self.cfg["quality"])
        quality_menu = ctk.CTkOptionMenu(
            options_frame, values=["best", "1080", "720", "480", "audio"],
            variable=self.quality_var, width=110, fg_color="#26263A",
            button_color="#3A3A4E", command=self._on_quality_change,
        )
        quality_menu.pack(side="left", padx=8)

        info_label = ctk.CTkLabel(
            options_frame,
            text="💡 Install the browser extension to download with one click from the web",
            text_color=TEXT_MUTED, font=("Segoe UI", 11),
        )
        info_label.pack(side="right")

        # Downloads list
        list_label = ctk.CTkLabel(
            self, text="Downloads", font=("Segoe UI", 14, "bold"), text_color="white"
        )
        list_label.pack(anchor="w", padx=24, pady=(10, 6))

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        self.empty_label = ctk.CTkLabel(
            self.scroll_frame, text="No downloads yet. Paste a link above to get started.",
            text_color=TEXT_MUTED, font=("Segoe UI", 12),
        )
        self.empty_label.pack(pady=40)

    # ---------- Actions ----------
    def _on_download_click(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        if not is_supported_url(url):
            messagebox.showwarning(
                APP_NAME, "That link doesn't look like Instagram or TikTok."
            )
            return
        self.url_entry.delete(0, "end")
        self._start_download(url)

    def _start_download(self, url: str):
        if not self.cfg.get("is_pro") and not self._consume_quota():
            self._open_upgrade_dialog(limit_reached=True)
            return

        if self.empty_label.winfo_manager():
            self.empty_label.pack_forget()

        job_id = self.manager.enqueue(url, self._on_job_update)
        job = self.manager.get_job(job_id)
        row = JobRow(self.scroll_frame, job)
        row.pack(fill="x", pady=4)
        self.rows[job_id] = row

    # ---------- Freemium / licencia ----------
    def _reset_quota_if_new_day(self):
        today = date.today().isoformat()
        if self.cfg.get("daily_date") != today:
            self.cfg["daily_date"] = today
            self.cfg["daily_count"] = 0
            save_config(self.cfg)

    def _consume_quota(self) -> bool:
        """Devuelve True y descuenta 1 del cupo diario si aún queda; False si
        ya se agotó el límite gratuito de hoy."""
        self._reset_quota_if_new_day()
        if self.cfg.get("daily_count", 0) >= FREE_DAILY_LIMIT:
            return False
        self.cfg["daily_count"] = self.cfg.get("daily_count", 0) + 1
        save_config(self.cfg)
        self._refresh_quota_label()
        return True

    def _refresh_quota_label(self):
        self._reset_quota_if_new_day()
        if not hasattr(self, "quota_label"):
            return
        remaining = max(0, FREE_DAILY_LIMIT - self.cfg.get("daily_count", 0))
        self.quota_label.configure(text=f"{remaining}/{FREE_DAILY_LIMIT} free downloads today")

    def _open_upgrade_dialog(self, limit_reached: bool = False):
        UpgradeDialog(self, self.cfg, on_activated=self._on_pro_activated, limit_reached=limit_reached)

    def _on_pro_activated(self):
        self.cfg["is_pro"] = True
        save_config(self.cfg)
        messagebox.showinfo(APP_NAME, "License activated! Restart VidGrab to see the changes.")

    def _on_job_update(self, job: DownloadJob):
        def _apply():
            row = self.rows.get(job.id)
            if row:
                row.update_view(job)
            if job.status == "completado":
                self.history.append({"url": job.url, "title": job.title, "path": job.filepath})
                save_history(self.history)
                if self.cfg.get("notify_on_complete"):
                    pass  # (se podría integrar plyer/toast aquí)
        self.after(0, _apply)

    def _on_quality_change(self, value):
        self.cfg["quality"] = value
        self.manager.set_quality(value)
        save_config(self.cfg)

    def _poll_extension_queue(self):
        try:
            while True:
                url = incoming_queue.get_nowait()
                if is_supported_url(url):
                    self.deiconify()
                    self.lift()
                    self._start_download(url)
        except Exception:
            pass
        self.after(500, self._poll_extension_queue)

    def _open_settings(self):
        SettingsDialog(self, self.cfg, on_save=self._apply_settings)

    def _apply_settings(self, new_cfg: dict):
        self.cfg.update(new_cfg)
        save_config(self.cfg)
        self.manager.set_download_dir(self.cfg["download_dir"])
        self.manager.set_quality(self.cfg["quality"])
        self.quality_var.set(self.cfg["quality"])


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, cfg: dict, on_save):
        super().__init__(master)
        self.title("VidGrab Settings")
        self.geometry("460x260")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        self.on_save = on_save
        self.cfg = cfg
        self.grab_set()

        ctk.CTkLabel(self, text="Download folder", text_color=TEXT_MUTED).pack(
            anchor="w", padx=20, pady=(20, 4)
        )
        path_row = ctk.CTkFrame(self, fg_color="transparent")
        path_row.pack(fill="x", padx=20)
        self.path_entry = ctk.CTkEntry(path_row, fg_color="#26263A", border_width=0)
        self.path_entry.insert(0, cfg["download_dir"])
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=6)
        ctk.CTkButton(
            path_row, text="Choose...", width=80, command=self._choose_dir,
            fg_color="#3A3A4E", hover_color="#4A4A5E",
        ).pack(side="left", padx=(8, 0))

        self.notify_var = ctk.BooleanVar(value=cfg.get("notify_on_complete", True))
        ctk.CTkCheckBox(
            self, text="Notify when download completes", variable=self.notify_var,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        ).pack(anchor="w", padx=20, pady=16)

        ctk.CTkButton(
            self, text="Save", fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._save,
        ).pack(padx=20, pady=20, fill="x")

    def _choose_dir(self):
        chosen = filedialog.askdirectory()
        if chosen:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, chosen)

    def _save(self):
        new_cfg = {
            "download_dir": self.path_entry.get().strip() or self.cfg["download_dir"],
            "notify_on_complete": self.notify_var.get(),
        }
        self.on_save(new_cfg)
        self.destroy()


class UpgradeDialog(ctk.CTkToplevel):
    """Pantalla 'Hazte Pro': explica los beneficios y permite activar una
    clave de licencia comprada (Gumroad/Ko-fi/etc.)."""

    def __init__(self, master, cfg: dict, on_activated, limit_reached: bool = False):
        super().__init__(master)
        self.title("VidGrab Pro")
        self.geometry("420x420")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        self.cfg = cfg
        self.on_activated = on_activated
        self.grab_set()

        if limit_reached:
            ctk.CTkLabel(
                self, text="You've reached today's free limit",
                font=("Segoe UI", 15, "bold"), text_color="#FFD166",
            ).pack(pady=(20, 4))
        else:
            ctk.CTkLabel(
                self, text="✨ VidGrab Pro", font=("Segoe UI", 20, "bold"), text_color="white"
            ).pack(pady=(20, 4))

        ctk.CTkLabel(
            self,
            text=f"The free version allows {FREE_DAILY_LIMIT} downloads per day.\nUnlock unlimited downloads with Pro:",
            text_color=TEXT_MUTED, font=("Segoe UI", 12), justify="center",
        ).pack(pady=(0, 12))

        benefits = [
            "🚀 Unlimited downloads per day",
            "🎬 Best available quality (no restrictions)",
            "📦 Unlimited batch downloads from the extension",
            "🙌 Support ongoing app development",
        ]
        for b in benefits:
            ctk.CTkLabel(self, text=b, text_color="white", font=("Segoe UI", 12), anchor="w").pack(
                anchor="w", padx=40, pady=2
            )

        ctk.CTkButton(
            self, text="Buy Pro License", fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=lambda: webbrowser.open(GUMROAD_URL),
        ).pack(padx=30, pady=(20, 10), fill="x")

        ctk.CTkLabel(self, text="Already have a key?", text_color=TEXT_MUTED, font=("Segoe UI", 11)).pack()

        key_row = ctk.CTkFrame(self, fg_color="transparent")
        key_row.pack(fill="x", padx=30, pady=(6, 0))
        self.key_entry = ctk.CTkEntry(
            key_row, placeholder_text="VIDGRAB-XXXX-XXXX-XXXX", fg_color="#26263A", border_width=0,
        )
        self.key_entry.pack(side="left", fill="x", expand=True, ipady=6)

        self.error_lbl = ctk.CTkLabel(self, text="", text_color=ERROR, font=("Segoe UI", 11))
        self.error_lbl.pack(pady=(4, 0))

        ctk.CTkButton(
            self, text="Activate", fg_color="#3A3A4E", hover_color="#4A4A5E",
            command=self._activate,
        ).pack(padx=30, pady=(10, 20), fill="x")

    def _activate(self):
        key = self.key_entry.get().strip()
        if validate_key(key):
            self.cfg["license_key"] = key
            self.on_activated()
            self.destroy()
        else:
            self.error_lbl.configure(text="Invalid key. Make sure you copied the whole thing.")


import msvcrt

_lock_file = None


def _acquire_single_instance_lock() -> bool:
    """Bloquea un archivo en %APPDATA%\\VidGrab durante toda la vida de la
    app. El bloqueo de archivos de Windows es atómico: si dos copias se
    abren al mismo tiempo, solo una consigue el candado, sin condiciones
    de carrera (a diferencia de comprobar el puerto/servidor)."""
    global _lock_file
    from config import CONFIG_DIR

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = CONFIG_DIR / ".vidgrab.lock"
    try:
        _lock_file = open(lock_path, "w")
        msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        if _lock_file:
            _lock_file.close()
            _lock_file = None
        return False


def main():
    if not _acquire_single_instance_lock():
        messagebox.showinfo(
            APP_NAME,
            "VidGrab is already open in another window.\n\n"
            "Look for it in your taskbar — that's where downloads arrive.\n"
            "(If you don't see it, close all VidGrab windows from Task "
            "Manager and open it again just once.)",
        )
        return

    app = VidGrabApp()
    app.mainloop()


if __name__ == "__main__":
    main()

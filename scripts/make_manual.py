"""Genera el manual en PDF de VidGrab Pro para incluir en Gumroad."""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle,
)
from reportlab.lib.enums import TA_CENTER

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUT = ROOT / "VidGrab_Manual.pdf"

PURPLE = colors.HexColor("#6C5CE7")
DARK = colors.HexColor("#141420")
MUTED = colors.HexColor("#5A5A6E")

styles = getSampleStyleSheet()
h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=PURPLE, fontSize=28, spaceAfter=6)
h2 = ParagraphStyle("h2", parent=styles["Heading1"], textColor=DARK, fontSize=18, spaceBefore=14, spaceAfter=8)
body = ParagraphStyle("body", parent=styles["Normal"], fontSize=11, leading=16, textColor=DARK)
muted = ParagraphStyle("muted", parent=styles["Normal"], fontSize=10, textColor=MUTED, alignment=TA_CENTER)
step_num = ParagraphStyle("stepnum", parent=styles["Normal"], fontSize=13, textColor=colors.white, alignment=TA_CENTER)

doc = SimpleDocTemplate(
    str(OUT), pagesize=letter,
    topMargin=0.9 * inch, bottomMargin=0.9 * inch,
    leftMargin=0.9 * inch, rightMargin=0.9 * inch,
)
story = []

# ---------- Portada ----------
story.append(Spacer(1, 1.2 * inch))
icon_path = ASSETS / "app_icon.png"
if icon_path.exists():
    img = Image(str(icon_path), width=1.3 * inch, height=1.3 * inch)
    img.hAlign = "CENTER"
    story.append(img)
story.append(Spacer(1, 0.3 * inch))
title = Paragraph("VidGrab Pro", ParagraphStyle("cover", parent=h1, alignment=TA_CENTER, fontSize=36))
story.append(title)
story.append(Paragraph("User Manual & Setup Guide", ParagraphStyle("coversub", parent=body, alignment=TA_CENTER, fontSize=14, textColor=MUTED)))
story.append(Spacer(1, 2.5 * inch))
story.append(Paragraph("Desktop App + Browser Extension for Instagram & TikTok", muted))
story.append(PageBreak())


def step_row(number, title_text, description):
    badge = Table([[Paragraph(str(number), step_num)]], colWidths=[0.4 * inch], rowHeights=[0.4 * inch])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PURPLE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    text = [Paragraph(f"<b>{title_text}</b>", body), Paragraph(description, body)]
    row = Table([[badge, text]], colWidths=[0.55 * inch, 5.6 * inch])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    return row


# ---------- Instalar la app ----------
story.append(Paragraph("1. Installing the Desktop App", h2))
story.append(step_row(1, "Extract the ZIP file", "Unzip the VidGrab package you downloaded. You'll find VidGrab.exe and a folder called VidGrab-Extension."))
story.append(step_row(2, "Install FFmpeg", "Open PowerShell and run: <font face='Courier'>winget install ffmpeg</font>. This is required to merge audio and video."))
story.append(step_row(3, "Open VidGrab.exe", "Double-click the file. No installation needed — it runs directly. Windows SmartScreen may show a warning the first time; click \"More info\" then \"Run anyway\"."))
story.append(step_row(4, "Paste a link and download", "Copy a video link from Instagram or TikTok, paste it into VidGrab, and click Download."))
story.append(PageBreak())

# ---------- Instalar extensión ----------
story.append(Paragraph("2. Installing the Browser Extension", h2))
story.append(step_row(1, "Open your browser's extensions page", "Go to chrome://extensions (Chrome) or edge://extensions (Edge)."))
story.append(step_row(2, "Enable Developer Mode", "Toggle \"Developer mode\" on, usually found in the top-right corner."))
story.append(step_row(3, "Load unpacked", "Click \"Load unpacked\" and select the VidGrab-Extension folder from the ZIP you extracted."))
story.append(step_row(4, "Browse & download", "With VidGrab.exe running, browse Instagram or TikTok. Click the extension icon to see every video detected on screen, with thumbnails — select the ones you want and send them to the app."))
story.append(PageBreak())

# ---------- Activar Pro ----------
story.append(Paragraph("3. Activating Your Pro License", h2))
story.append(step_row(1, "Open VidGrab", "Launch the desktop app."))
story.append(step_row(2, "Click \"Hazte Pro\" / \"Go Pro\"", "Found in the top-right corner of the main window."))
story.append(step_row(3, "Enter your license key", "Paste the key you received by email after purchase (format: VIDGRAB-XXXX-XXXX-XXXX) and click Activate."))
story.append(step_row(4, "Enjoy unlimited downloads", "Restart the app — the daily 5-download limit is now removed, permanently."))
story.append(Spacer(1, 0.3 * inch))

story.append(Paragraph("Frequently Asked Questions", h2))
faqs = [
    ("Do I need Instagram/TikTok accounts?", "No — public content can be downloaded without logging in."),
    ("Does this work on Mac or Linux?", "The desktop app is Windows-only. The browser extension works on any OS, but needs a Windows machine running VidGrab.exe to actually download."),
    ("I lost my license key.", "Contact support with your purchase email and we'll resend it."),
    ("Is this legal?", "This tool is intended for personal use with content you own or have explicit permission to download. Downloading and redistributing others' content without authorization may violate the platforms' Terms of Service and copyright law."),
]
for q, a in faqs:
    story.append(Paragraph(f"<b>{q}</b>", body))
    story.append(Paragraph(a, body))
    story.append(Spacer(1, 10))

story.append(Spacer(1, 0.3 * inch))
story.append(Paragraph("Need help? Contact us at loganparkers2022@gmail.com", muted))

doc.build(story)
print(f"Manual generado en {OUT}")

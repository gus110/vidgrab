"""Genera una imagen de portada para el listado de Gumroad (1280x720)."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
W, H = 1280, 720

PURPLE_A = (20, 20, 32)
PURPLE_B = (30, 22, 60)
ACCENT = (108, 92, 231)
ACCENT_LIGHT = (139, 124, 246)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


img = Image.new("RGB", (W, H), PURPLE_A)
draw = ImageDraw.Draw(img)

# Fondo degradado diagonal simple
for y in range(H):
    t = y / H
    color = lerp(PURPLE_A, PURPLE_B, t)
    draw.line([(0, y), (W, y)], fill=color)

# Círculo decorativo de acento (logo simplificado)
cx, cy, r = 220, 360, 130
draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ACCENT)
arrow_w, arrow_h = 90, 100
draw.polygon(
    [
        (cx - arrow_w / 2, cy - arrow_h / 2),
        (cx + arrow_w / 2, cy - arrow_h / 2),
        (cx + arrow_w / 2, cy + arrow_h / 10),
        (cx + arrow_w * 0.9, cy + arrow_h / 10),
        (cx, cy + arrow_h * 0.75),
        (cx - arrow_w * 0.9, cy + arrow_h / 10),
        (cx - arrow_w / 2, cy + arrow_h / 10),
    ],
    fill="white",
)


def load_font(size, bold=True):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


title_font = load_font(72)
sub_font = load_font(30, bold=False)
badge_font = load_font(24)

draw.text((430, 250), "VidGrab Pro", font=title_font, fill="white")
draw.text(
    (432, 335),
    "Unlimited Instagram & TikTok\nvideo downloads",
    font=sub_font, fill=(200, 200, 220), spacing=10,
)

# Badge inferior
badge_text = "⚡ ONE-TIME PAYMENT   •   LIFETIME LICENSE"
draw.rounded_rectangle((430, 460, 950, 505), radius=22, fill=(38, 38, 58))
draw.text((452, 470), badge_text, font=badge_font, fill=ACCENT_LIGHT)

img.save(ASSETS / "gumroad_cover.png")
print("Guardado en assets/gumroad_cover.png")

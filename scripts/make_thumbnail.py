"""Genera un thumbnail cuadrado (600x600) para Gumroad, distinto de la portada rectangular."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
S = 600

PURPLE_A = (20, 20, 32)
PURPLE_B = (34, 24, 66)
ACCENT = (108, 92, 231)
ACCENT_LIGHT = (139, 124, 246)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


img = Image.new("RGB", (S, S), PURPLE_A)
draw = ImageDraw.Draw(img)

for y in range(S):
    t = y / S
    draw.line([(0, y), (S, y)], fill=lerp(PURPLE_A, PURPLE_B, t))

cx, cy, r = S // 2, 230, 110
draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ACCENT)
aw, ah = 76, 84
draw.polygon(
    [
        (cx - aw / 2, cy - ah / 2), (cx + aw / 2, cy - ah / 2),
        (cx + aw / 2, cy + ah / 10), (cx + aw * 0.9, cy + ah / 10),
        (cx, cy + ah * 0.75), (cx - aw * 0.9, cy + ah / 10),
        (cx - aw / 2, cy + ah / 10),
    ],
    fill="white",
)


def load_font(size, bold=True):
    for c in (
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ):
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


title_font = load_font(56)
sub_font = load_font(24, bold=False)

title = "VidGrab Pro"
bbox = draw.textbbox((0, 0), title, font=title_font)
tw = bbox[2] - bbox[0]
draw.text(((S - tw) / 2, 370), title, font=title_font, fill="white")

sub = "App + Browser Extension"
bbox2 = draw.textbbox((0, 0), sub, font=sub_font)
sw = bbox2[2] - bbox2[0]
draw.text(((S - sw) / 2, 445), sub, font=sub_font, fill=ACCENT_LIGHT)

img.save(ASSETS / "gumroad_thumbnail.png")
print("Guardado en assets/gumroad_thumbnail.png")

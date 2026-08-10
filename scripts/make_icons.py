"""Genera los íconos de la extensión y de la app a partir de un diseño simple."""
from PIL import Image, ImageDraw
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT_ICONS = ROOT / "extension" / "icons"
ASSETS = ROOT / "assets"
EXT_ICONS.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

PURPLE_A = (108, 92, 231, 255)
PURPLE_B = (139, 124, 246, 255)


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fondo circular con degradado simple (aproximado con capas)
    for i in range(size):
        t = i / size
        r = int(PURPLE_A[0] + (PURPLE_B[0] - PURPLE_A[0]) * t)
        g = int(PURPLE_A[1] + (PURPLE_B[1] - PURPLE_A[1]) * t)
        b = int(PURPLE_A[2] + (PURPLE_B[2] - PURPLE_A[2]) * t)
        draw.line([(0, i), (size, i)], fill=(r, g, b, 255))

    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse((0, 0, size, size), fill=255)
    circle = Image.composite(img, Image.new("RGBA", (size, size), (0, 0, 0, 0)), mask)

    draw2 = ImageDraw.Draw(circle)
    cx, cy = size / 2, size / 2
    arrow_w = size * 0.32
    arrow_h = size * 0.34
    draw2.polygon(
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
    return circle


for size in (16, 48, 128):
    make_icon(size).save(EXT_ICONS / f"icon{size}.png")

make_icon(256).save(ASSETS / "app_icon.png")

# Generar .ico para el ejecutable de Windows
icon_256 = Image.open(ASSETS / "app_icon.png")
icon_256.save(ASSETS / "app_icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])

print("Íconos generados en extension/icons/ y assets/")

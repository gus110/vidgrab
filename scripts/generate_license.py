"""
Genera claves de licencia Pro para VidGrab.
Uso: cuando alguien te compre en Gumroad/Ko-fi, corre este script y
mándale la clave que te da por correo.

    python scripts\\generate_license.py
    python scripts\\generate_license.py 10   (genera 10 claves de una vez)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from license import generate_key  # noqa: E402

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for _ in range(count):
        print(generate_key())

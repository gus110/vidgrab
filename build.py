"""
Empaqueta VidGrab en un único ejecutable de Windows (VidGrab.exe) usando PyInstaller.
Uso:  venv\\Scripts\\python build.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pyinstaller"], check=True)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "VidGrab",
        "--onefile",
        "--windowed",
        "--icon", str(ROOT / "assets" / "app_icon.ico"),
        "--add-data", f"{ROOT / 'assets'};assets",
        str(ROOT / "app" / "main.py"),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)
    print("\nListo. Ejecutable en dist/VidGrab.exe")

if __name__ == "__main__":
    main()

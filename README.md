# VidGrab

Descargador profesional de videos de **Instagram** y **TikTok** para Windows, compuesto por dos partes:

1. **App de escritorio** (Python + CustomTkinter): interfaz donde pegas un enlace y se descarga el video en tu carpeta elegida, con barra de progreso, historial y control de calidad.
2. **Extensión de navegador** (Chrome/Edge, Manifest V3): agrega un botón "⬇ VidGrab" sobre los videos de Instagram/TikTok y en el popup, para enviar el enlace a la app con un clic.

La app y la extensión se comunican por un servidor HTTP local (`127.0.0.1:8743`), que no expone nada a internet.

El motor de descarga es [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), la librería open-source estándar para extracción de video.

## Requisitos

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) instalado y en el PATH (necesario para unir audio/video y exportar mp3)

## Puesta en marcha (modo desarrollo)

```bash
cd VidGrab
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app\main.py
```

## Generar los íconos (ya incluidos, solo si los cambias)

```bash
python scripts\make_icons.py
```

## Empaquetar como VidGrab.exe

```bash
venv\Scripts\activate
python build.py
```

El ejecutable queda en `dist\VidGrab.exe`. Es standalone: se puede copiar a cualquier PC Windows sin instalar Python (FFmpeg sí debe estar disponible en el sistema).

## Instalar la extensión de navegador

1. Abre `chrome://extensions` (o `edge://extensions`)
2. Activa "Modo de desarrollador"
3. Clic en "Cargar descomprimida" (Load unpacked)
4. Selecciona la carpeta `extension/`
5. Con la app **VidGrab.exe abierta**, navega a un video de Instagram o TikTok y usa el botón flotante o el ícono de la extensión

## Estructura del proyecto

```
VidGrab/
├── app/
│   ├── main.py         # Interfaz gráfica (CustomTkinter)
│   ├── downloader.py    # Motor de descarga (yt-dlp) en hilos
│   ├── server.py         # Servidor local para la extensión
│   └── config.py         # Configuración y persistencia
├── extension/
│   ├── manifest.json
│   ├── background.js
│   ├── content.js / content.css
│   ├── popup.html / popup.js
│   └── icons/
├── scripts/make_icons.py
├── build.py               # Empaquetado a .exe
└── requirements.txt
```

## Nota legal

Esta herramienta está pensada para descargar contenido propio o de uso autorizado (por ejemplo, respaldar tus propios videos, o contenido con permiso explícito del creador). Descargar y redistribuir contenido de terceros sin autorización puede infringir los Términos de Servicio de Instagram/TikTok y derechos de autor — el uso es responsabilidad de quien opera la herramienta.

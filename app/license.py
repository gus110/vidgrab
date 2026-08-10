"""
Sistema de licencias sin servidor (offline).

Las claves tienen el formato:  VIDGRAB-XXXX-XXXX-XXXX
Los primeros 3 grupos son aleatorios; el sistema valida la clave calculando
un HMAC con un secreto embebido en la app y comparándolo contra el propio
código de la clave (ver generate_key). No requiere internet ni backend.

IMPORTANTE: este esquema es "seguridad por oscuridad" — alguien con tiempo
puede decompilar el .exe y encontrar SECRET, o generar claves válidas.
Es el estándar razonable para una app indie de este tamaño; si el negocio
crece, migrar a validación de licencia contra un servidor propio.
"""
import hashlib
import hmac
import secrets
import string

# El secreto real vive en license_secret.py, que está en .gitignore y nunca
# se sube al repositorio público. Si alguien clona el repo sin ese archivo
# (por ejemplo, para desarrollo), se usa un valor de relleno inseguro que
# NO debe usarse para vender licencias reales.
try:
    from license_secret import SECRET
except ImportError:
    SECRET = b"DEV-INSECURE-PLACEHOLDER-CHANGE-ME"

ALPHABET = string.ascii_uppercase + string.digits


def _checksum(payload: str) -> str:
    digest = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest().upper()
    return digest[:4]


def generate_key() -> str:
    """Genera una clave de licencia válida (usar solo desde tu propia
    herramienta de venta, nunca exponer esta función dentro de la app)."""
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(2)]
    payload = "-".join(groups)
    checksum = _checksum(payload)
    return f"VIDGRAB-{payload}-{checksum}"


def validate_key(key: str) -> bool:
    key = (key or "").strip().upper()
    parts = key.split("-")
    if len(parts) != 4 or parts[0] != "VIDGRAB":
        return False
    payload = f"{parts[1]}-{parts[2]}"
    expected = _checksum(payload)
    return hmac.compare_digest(expected, parts[3])

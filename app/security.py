"""Claves (PBKDF2, stdlib) y tokens JWT de corta duración."""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from app import config

ITERACIONES = 600_000  # recomendación OWASP 2023 para PBKDF2-SHA256


def hash_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${base64.b64encode(sal).decode()}${base64.b64encode(dk).decode()}"


def verificar_clave(clave: str, guardada: str) -> bool:
    try:
        _, iteraciones, sal, dk = guardada.split("$")
        calculado = hashlib.pbkdf2_hmac("sha256", clave.encode(), base64.b64decode(sal), int(iteraciones))
        return hmac.compare_digest(calculado, base64.b64decode(dk))
    except ValueError:
        return False


def crear_token(usuario_id: int, rol: str, socio_id: int | None) -> str:
    ahora = datetime.now(UTC)
    payload = {"sub": str(usuario_id), "rol": rol, "socio": socio_id, "iat": ahora, "exp": ahora + timedelta(minutes=config.JWT_MINUTES)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def leer_token(token: str) -> dict:
    """Lanza jwt.PyJWTError si el token es inválido o venció."""
    return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])

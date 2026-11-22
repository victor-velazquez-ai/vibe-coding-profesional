"""Contraseñas y cookie de sesión firmada.

Contraseñas con `hashlib.scrypt` (stdlib: una dependencia menos que mantener).
Cookie con `itsdangerous`: firmada y con marca de tiempo, nunca cifrada — así que
dentro solo van identificadores, nunca datos del candidato.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.configuracion import ajustes

_N = 2**14
_R = 8
_P = 1
_LARGO = 32


def hash_contrasena(contrasena: str) -> str:
    sal = os.urandom(16)
    derivada = hashlib.scrypt(
        contrasena.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=_LARGO, maxmem=64 * 1024 * 1024
    )
    return f"scrypt${_N}${_R}${_P}${sal.hex()}${derivada.hex()}"


def verificar_contrasena(contrasena: str, guardado: str) -> bool:
    try:
        algoritmo, n, r, p, sal_hex, esperado_hex = guardado.split("$")
    except ValueError:
        return False
    if algoritmo != "scrypt":
        return False
    derivada = hashlib.scrypt(
        contrasena.encode(),
        salt=bytes.fromhex(sal_hex),
        n=int(n),
        r=int(r),
        p=int(p),
        dklen=len(esperado_hex) // 2,
        maxmem=64 * 1024 * 1024,
    )
    return hmac.compare_digest(derivada.hex(), esperado_hex)


def _serializador() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(ajustes().secreto_sesion, salt="criba-sesion")


def firmar_sesion(datos: dict[str, Any]) -> str:
    return _serializador().dumps(datos)


def leer_sesion(token: str) -> dict[str, Any] | None:
    try:
        datos = _serializador().loads(token, max_age=ajustes().horas_de_sesion * 3600)
    except (BadSignature, SignatureExpired):
        return None
    return datos if isinstance(datos, dict) else None

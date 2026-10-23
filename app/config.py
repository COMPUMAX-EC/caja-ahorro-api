"""Configuración desde variables de entorno."""

import os
import secrets
import warnings

DB_PATH = os.environ.get("CAJA_DB_PATH", "caja.db")

# En producción JWT_SECRET viene de Secret Manager; en desarrollo se genera uno por proceso
JWT_SECRET = os.environ.get("JWT_SECRET") or ""
if not JWT_SECRET:
    JWT_SECRET = secrets.token_urlsafe(48)
    warnings.warn("JWT_SECRET no está definido: se usa uno temporal (solo para desarrollo)", stacklevel=1)
JWT_MINUTES = int(os.environ.get("JWT_MINUTES", "15"))

# Reglas de la caja (las define su asamblea general; estos son valores de ejemplo)
APORTE_MENSUAL_CENTS = int(os.environ.get("APORTE_MENSUAL_CENTS", "500"))  # $5 de certificado de aportación
VECES_AHORRO_PRESTAMO = int(os.environ.get("VECES_AHORRO_PRESTAMO", "3"))  # préstamo máximo = 3 × lo ahorrado
TASA_MORA_ANUAL = float(os.environ.get("TASA_MORA_ANUAL", "0.10"))  # recargo sobre la cuota vencida

# Alertas: en Ecuador las operaciones en efectivo desde USD 10.000 se reportan a la UAFE
UMBRAL_UAFE_CENTS = 10_000_00
UMBRAL_RETIRO_ALTO_CENTS = int(os.environ.get("UMBRAL_RETIRO_ALTO_CENTS", "200000"))  # $2.000

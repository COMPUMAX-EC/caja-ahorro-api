"""Alertas de operaciones inusuales, para que el tesorero las revise (no bloquean la operación)."""

import sqlite3

from app import config
from app.metrics import ALERTAS


def revisar(conn: sqlite3.Connection, socio_id: int, tipo: str, monto_cents: int, efectivo: bool) -> list[str]:
    reglas = []
    if efectivo and monto_cents >= config.UMBRAL_UAFE_CENTS:
        reglas.append(("uafe_efectivo", "Operación en efectivo desde USD 10.000: preparar el reporte a la UAFE"))
    if efectivo and tipo == "deposito":
        # Fraccionamiento: varios depósitos en efectivo en 7 días que juntos llegan al umbral. Se llama después de
        # registrar el movimiento, así que la suma ya incluye el depósito actual
        semana = conn.execute(
            """SELECT COALESCE(SUM(monto_cents), 0) FROM movimientos
               WHERE socio_id = ? AND tipo = 'deposito' AND efectivo = 1 AND fecha >= datetime('now', '-7 days')""",
            (socio_id,),
        ).fetchone()[0]
        if monto_cents < config.UMBRAL_UAFE_CENTS <= semana:
            reglas.append(("fraccionamiento", "Depósitos en efectivo de 7 días suman USD 10.000 o más"))
    if tipo == "retiro" and monto_cents >= config.UMBRAL_RETIRO_ALTO_CENTS:
        reglas.append(("retiro_alto", "Retiro mayor al umbral de la caja"))
    for regla, detalle in reglas:
        conn.execute("INSERT INTO alertas (socio_id, regla, detalle) VALUES (?, ?, ?)", (socio_id, regla, detalle))
        ALERTAS.labels(regla=regla).inc()
    return [regla for regla, _ in reglas]

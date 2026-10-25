"""Alertas de cumplimiento y de operaciones inusuales, para que el tesorero las revise (no bloquean la operación).

Reglas UAFE alineadas con el módulo de cumplimiento de DevIALabs Finanzas: el RESU incluye operaciones individuales
desde el umbral y las de una misma persona que juntas lo alcanzan en 30 días, en efectivo o no.
"""

import sqlite3

from app import config
from app.metrics import ALERTAS


# Ventanas de `dias` días que terminan hoy. Se consultan después de registrar el movimiento, así que lo incluyen
def _suma_ventana(conn: sqlite3.Connection, socio_id: int, dias: int) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(monto_cents), 0) FROM movimientos WHERE socio_id = ? AND date(fecha) >= date('now', ?)",
        (socio_id, f"-{dias - 1} days"),
    ).fetchone()[0]


def _efectivo_bajo_umbral(conn: sqlite3.Connection, socio_id: int, dias: int, umbral: int) -> tuple[int, int]:
    return conn.execute(
        """SELECT COUNT(*), COALESCE(SUM(monto_cents), 0) FROM movimientos
           WHERE socio_id = ? AND date(fecha) >= date('now', ?) AND efectivo = 1 AND monto_cents < ?""",
        (socio_id, f"-{dias - 1} days", umbral),
    ).fetchone()


def _alerta_resu_reciente(conn: sqlite3.Connection, socio_id: int) -> bool:
    return (
        conn.execute(
            """SELECT 1 FROM alertas WHERE socio_id = ? AND regla IN ('resu_individual', 'resu_acumulado')
           AND date(fecha) >= date('now', ?) LIMIT 1""",
            (socio_id, f"-{config.VENTANA_RESU_DIAS - 1} days"),
        ).fetchone()
        is not None
    )


def revisar(conn: sqlite3.Connection, socio_id: int, tipo: str, monto_cents: int, efectivo: bool) -> list[str]:
    umbral = config.UMBRAL_UAFE_CENTS
    reglas = []
    if monto_cents >= umbral:
        reglas.append(("resu_individual", f"{tipo} desde USD 10.000: va al RESU de la UAFE"))
    else:
        total = _suma_ventana(conn, socio_id, config.VENTANA_RESU_DIAS)
        # Una alerta por racha: si ya hay una en la ventana, la operación nueva solo se suma al reporte
        if total >= umbral and not _alerta_resu_reciente(conn, socio_id):
            reglas.append(("resu_acumulado", f"Operaciones de {config.VENTANA_RESU_DIAS} días suman USD 10.000 o más: van al RESU"))
        if efectivo:
            # Fraccionamiento: varias operaciones en efectivo bajo el umbral que juntas lo superan en pocos días.
            # Es una señal para revisar (posible reporte de operación sospechosa), no un reporte automático
            n, suma = _efectivo_bajo_umbral(conn, socio_id, config.FRACC_VENTANA_DIAS, umbral)
            if n >= config.FRACC_MIN_OPERACIONES and suma >= umbral > suma - monto_cents:
                reglas.append(("fraccionamiento", f"{n} operaciones en efectivo bajo el umbral en {config.FRACC_VENTANA_DIAS} días superan USD 10.000"))
    if tipo == "retiro" and monto_cents >= config.UMBRAL_RETIRO_ALTO_CENTS:
        reglas.append(("retiro_alto", "Retiro mayor al umbral de la caja"))
    for regla, detalle in reglas:
        conn.execute("INSERT INTO alertas (socio_id, regla, detalle) VALUES (?, ?, ?)", (socio_id, regla, detalle))
        ALERTAS.labels(regla=regla).inc()
    return [regla for regla, _ in reglas]

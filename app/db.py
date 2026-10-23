"""Base de datos SQLite (stdlib). Los montos se guardan en centavos enteros para no perder precisión."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY,
  usuario TEXT UNIQUE NOT NULL,
  clave_hash TEXT NOT NULL,
  rol TEXT NOT NULL CHECK (rol IN ('tesorero', 'socio')),
  socio_id INTEGER REFERENCES socios(id)
);
CREATE TABLE IF NOT EXISTS socios (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL,
  ingreso TEXT NOT NULL DEFAULT (date('now')),
  activo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS movimientos (
  id INTEGER PRIMARY KEY,
  socio_id INTEGER NOT NULL REFERENCES socios(id),
  tipo TEXT NOT NULL CHECK (tipo IN ('deposito', 'retiro', 'aporte', 'desembolso', 'pago_prestamo')),
  monto_cents INTEGER NOT NULL CHECK (monto_cents > 0),
  efectivo INTEGER NOT NULL DEFAULT 1,
  fecha TEXT NOT NULL DEFAULT (datetime('now')),
  registrado_por INTEGER REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS prestamos (
  id INTEGER PRIMARY KEY,
  socio_id INTEGER NOT NULL REFERENCES socios(id),
  monto_cents INTEGER NOT NULL,
  tasa_anual REAL NOT NULL,
  plazo_meses INTEGER NOT NULL,
  metodo TEXT NOT NULL CHECK (metodo IN ('frances', 'aleman')),
  estado TEXT NOT NULL CHECK (estado IN ('solicitado', 'aprobado', 'rechazado', 'pagado')),
  fecha_desembolso TEXT
);
CREATE TABLE IF NOT EXISTS cuotas (
  prestamo_id INTEGER NOT NULL REFERENCES prestamos(id),
  numero INTEGER NOT NULL,
  vence TEXT NOT NULL,
  capital_cents INTEGER NOT NULL,
  interes_cents INTEGER NOT NULL,
  pagada INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (prestamo_id, numero)
);
CREATE TABLE IF NOT EXISTS alertas (
  id INTEGER PRIMARY KEY,
  socio_id INTEGER REFERENCES socios(id),
  regla TEXT NOT NULL,
  detalle TEXT NOT NULL,
  fecha TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS auditoria (
  id INTEGER PRIMARY KEY,
  usuario_id INTEGER,
  accion TEXT NOT NULL,
  detalle TEXT NOT NULL,
  fecha TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Una operación completa o nada (p. ej. desembolsar y generar la tabla de cuotas)."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def saldo_ahorro(conn: sqlite3.Connection, socio_id: int) -> int:
    """Ahorro disponible: depósitos y desembolsos menos retiros. Los aportes van aparte y los pagos de préstamos
    se hacen en ventanilla, sin tocar el ahorro."""
    row = conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN tipo IN ('deposito', 'desembolso') THEN monto_cents
                                    WHEN tipo = 'retiro' THEN -monto_cents ELSE 0 END), 0)
           FROM movimientos WHERE socio_id = ?""",
        (socio_id,),
    ).fetchone()
    return int(row[0])


def total_aportes(conn: sqlite3.Connection, socio_id: int) -> int:
    row = conn.execute("SELECT COALESCE(SUM(monto_cents), 0) FROM movimientos WHERE socio_id = ? AND tipo = 'aporte'", (socio_id,)).fetchone()
    return int(row[0])

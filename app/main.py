"""API REST de una caja de ahorro y crédito comunitaria.

Roles: el tesorero registra socios, movimientos de ventanilla y aprueba préstamos; cada socio ve su estado de cuenta
y solicita préstamos. Todo lo que cambia saldos queda en la auditoría.
"""

import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app import alertas, amortizacion, config, db, security
from app.metrics import CARTERA, LATENCIA, LOGIN_FALLIDO, MOROSIDAD, OPERACIONES, PETICIONES


def crear_tesorero_inicial() -> None:
    """Primer tesorero desde variables de entorno (solo si aún no hay usuarios)."""
    usuario, clave = os.environ.get("CAJA_TESORERO_USUARIO"), os.environ.get("CAJA_TESORERO_CLAVE")
    if usuario and clave:
        with db.transaction() as conn:
            if not conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
                conn.execute("INSERT INTO usuarios (usuario, clave_hash, rol) VALUES (?, ?, 'tesorero')", (usuario, security.hash_clave(clave)))


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    crear_tesorero_inicial()
    yield


app = FastAPI(
    title="Caja de Ahorro Comunitaria API",
    version="0.1.0",
    lifespan=lifespan,
    description="Demo: socios, ahorros, aportes, préstamos con tabla de amortización, mora y alertas UAFE.",
)
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")


@app.middleware("http")
async def metricas_y_cabeceras(request: Request, call_next):
    inicio = time.perf_counter()
    response = await call_next(request)
    ruta = request.scope.get("route").path if request.scope.get("route") else "desconocida"
    PETICIONES.labels(ruta=ruta, metodo=request.method, estado=response.status_code).inc()
    LATENCIA.labels(ruta=ruta).observe(time.perf_counter() - inicio)
    response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
    return response


# --- Autenticación

INTENTOS: dict[str, deque] = defaultdict(deque)
MAX_INTENTOS, VENTANA_S = 5, 60


def limitar_intentos(request: Request) -> None:
    """Máximo 5 intentos de inicio de sesión por minuto e IP (contra fuerza bruta)."""
    ip = request.client.host if request.client else "?"
    ahora, cola = time.monotonic(), INTENTOS[ip]
    while cola and ahora - cola[0] > VENTANA_S:
        cola.popleft()
    if len(cola) >= MAX_INTENTOS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos; espera un minuto")
    cola.append(ahora)


@app.post("/auth/token", tags=["auth"], dependencies=[Depends(limitar_intentos)])
def token(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict:
    conn = db.connect()
    row = conn.execute("SELECT id, clave_hash, rol, socio_id FROM usuarios WHERE usuario = ?", (form.username,)).fetchone()
    conn.close()
    if not row or not security.verificar_clave(form.password, row["clave_hash"]):
        LOGIN_FALLIDO.inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o clave incorrectos", headers={"WWW-Authenticate": "Bearer"})
    # "bearer" es el tipo de token de OAuth2, no una clave (bandit lo confunde)
    return {"access_token": security.crear_token(row["id"], row["rol"], row["socio_id"]), "token_type": "bearer"}  # nosec B105


def usuario_actual(token: Annotated[str, Depends(oauth2)]) -> dict:
    try:
        return security.leer_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o vencido", headers={"WWW-Authenticate": "Bearer"}) from None


def tesorero(user: Annotated[dict, Depends(usuario_actual)]) -> dict:
    if user["rol"] != "tesorero":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el tesorero puede hacer esta operación")
    return user


Usuario = Annotated[dict, Depends(usuario_actual)]
Tesorero = Annotated[dict, Depends(tesorero)]


def auditar(conn, user: dict, accion: str, detalle: str) -> None:
    conn.execute("INSERT INTO auditoria (usuario_id, accion, detalle) VALUES (?, ?, ?)", (int(user["sub"]), accion, detalle))


def cents(monto: Decimal) -> int:
    return int((monto * 100).to_integral_value())


def dolares(valor: int) -> str:
    return f"{valor / 100:.2f}"


# --- Socios


class NuevoSocio(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    usuario: str = Field(min_length=3, max_length=40, pattern=r"^[a-z0-9._-]+$")
    clave: str = Field(min_length=10, max_length=128)


@app.post("/socios", status_code=201, tags=["socios"])
def crear_socio(datos: NuevoSocio, user: Tesorero) -> dict:
    with db.transaction() as conn:
        if conn.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (datos.usuario,)).fetchone():
            raise HTTPException(status.HTTP_409_CONFLICT, "El usuario ya existe")
        socio_id = conn.execute("INSERT INTO socios (nombre) VALUES (?)", (datos.nombre,)).lastrowid
        conn.execute(
            "INSERT INTO usuarios (usuario, clave_hash, rol, socio_id) VALUES (?, ?, 'socio', ?)", (datos.usuario, security.hash_clave(datos.clave), socio_id)
        )
        auditar(conn, user, "crear_socio", f"socio {socio_id}")
    return {"id": socio_id, "nombre": datos.nombre}


def estado_de_cuenta(conn, socio_id: int) -> dict:
    socio = conn.execute("SELECT id, nombre, ingreso, activo FROM socios WHERE id = ?", (socio_id,)).fetchone()
    if not socio:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Socio no encontrado")
    prestamos = conn.execute("SELECT id, monto_cents, estado FROM prestamos WHERE socio_id = ?", (socio_id,)).fetchall()
    return {
        **dict(socio),
        "ahorro": dolares(db.saldo_ahorro(conn, socio_id)),
        "aportes": dolares(db.total_aportes(conn, socio_id)),
        "prestamos": [{"id": p["id"], "monto": dolares(p["monto_cents"]), "estado": p["estado"]} for p in prestamos],
    }


@app.get("/socios", tags=["socios"])
def listar_socios(user: Tesorero) -> list[dict]:
    conn = db.connect()
    ids = [r["id"] for r in conn.execute("SELECT id FROM socios ORDER BY id")]
    resultado = [estado_de_cuenta(conn, i) for i in ids]
    conn.close()
    return resultado


@app.get("/socios/yo", tags=["socios"])
def mi_estado(user: Usuario) -> dict:
    if not user.get("socio"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Este usuario no es socio")
    conn = db.connect()
    try:
        return estado_de_cuenta(conn, user["socio"])
    finally:
        conn.close()


# --- Movimientos de ventanilla


class Movimiento(BaseModel):
    socio_id: int
    tipo: Literal["deposito", "retiro", "aporte"]
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    efectivo: bool = True


@app.post("/movimientos", status_code=201, tags=["ahorros"])
def registrar_movimiento(mov: Movimiento, user: Tesorero) -> dict:
    monto = cents(mov.monto)
    with db.transaction() as conn:
        estado_de_cuenta(conn, mov.socio_id)  # 404 si no existe
        if mov.tipo == "retiro" and monto > db.saldo_ahorro(conn, mov.socio_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "Saldo de ahorro insuficiente")
        mov_id = conn.execute(
            "INSERT INTO movimientos (socio_id, tipo, monto_cents, efectivo, registrado_por) VALUES (?, ?, ?, ?, ?)",
            (mov.socio_id, mov.tipo, monto, int(mov.efectivo), int(user["sub"])),
        ).lastrowid
        disparadas = alertas.revisar(conn, mov.socio_id, mov.tipo, monto, mov.efectivo)
        auditar(conn, user, mov.tipo, f"movimiento {mov_id} socio {mov.socio_id} {dolares(monto)}")
        saldo = db.saldo_ahorro(conn, mov.socio_id)
    OPERACIONES.labels(tipo=mov.tipo).inc()
    return {"id": mov_id, "saldo_ahorro": dolares(saldo), "alertas": disparadas}


# --- Préstamos


class Solicitud(BaseModel):
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    plazo_meses: int = Field(ge=1, le=60)
    tasa_anual: float = Field(ge=0, le=0.30, description="Tasa nominal anual, p. ej. 0.15")
    metodo: Literal["frances", "aleman"] = "frances"
    socio_id: int | None = Field(None, description="Solo el tesorero puede solicitar a nombre de otro socio")


def cuotas_json(cuotas) -> list[dict]:
    return [
        {
            "numero": c.numero,
            "vence": c.vence.isoformat(),
            "capital": dolares(c.capital_cents),
            "interes": dolares(c.interes_cents),
            "cuota": dolares(c.total_cents),
        }
        for c in cuotas
    ]


@app.post("/prestamos/simular", tags=["préstamos"])
def simular(s: Solicitud, user: Usuario) -> dict:
    cuotas = amortizacion.tabla(cents(s.monto), s.tasa_anual, s.plazo_meses, s.metodo, date.today())
    return {"total_intereses": dolares(sum(c.interes_cents for c in cuotas)), "cuotas": cuotas_json(cuotas)}


@app.post("/prestamos", status_code=201, tags=["préstamos"])
def solicitar(s: Solicitud, user: Usuario) -> dict:
    socio_id = s.socio_id if user["rol"] == "tesorero" and s.socio_id else user.get("socio")
    if not socio_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indica el socio")
    with db.transaction() as conn:
        estado_de_cuenta(conn, socio_id)
        pid = conn.execute(
            "INSERT INTO prestamos (socio_id, monto_cents, tasa_anual, plazo_meses, metodo, estado) VALUES (?, ?, ?, ?, ?, 'solicitado')",
            (socio_id, cents(s.monto), s.tasa_anual, s.plazo_meses, s.metodo),
        ).lastrowid
        auditar(conn, user, "solicitar_prestamo", f"préstamo {pid} socio {socio_id}")
    return {"id": pid, "estado": "solicitado"}


@app.post("/prestamos/{pid}/aprobar", tags=["préstamos"])
def aprobar(pid: int, user: Tesorero) -> dict:
    with db.transaction() as conn:
        p = conn.execute("SELECT * FROM prestamos WHERE id = ?", (pid,)).fetchone()
        if not p:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Préstamo no encontrado")
        if p["estado"] != "solicitado":
            raise HTTPException(status.HTTP_409_CONFLICT, f"El préstamo está {p['estado']}")
        # Encaje: se presta hasta N veces lo que el socio tiene ahorrado y aportado
        respaldo = db.saldo_ahorro(conn, p["socio_id"]) + db.total_aportes(conn, p["socio_id"])
        if p["monto_cents"] > config.VECES_AHORRO_PRESTAMO * respaldo:
            conn.execute("UPDATE prestamos SET estado = 'rechazado' WHERE id = ?", (pid,))
            auditar(conn, user, "rechazar_prestamo", f"préstamo {pid}: supera {config.VECES_AHORRO_PRESTAMO} veces el ahorro")
            return {"id": pid, "estado": "rechazado", "motivo": f"Supera {config.VECES_AHORRO_PRESTAMO} veces el ahorro y aportes ({dolares(respaldo)})"}
        hoy = date.today()
        for c in amortizacion.tabla(p["monto_cents"], p["tasa_anual"], p["plazo_meses"], p["metodo"], hoy):
            conn.execute(
                "INSERT INTO cuotas (prestamo_id, numero, vence, capital_cents, interes_cents) VALUES (?, ?, ?, ?, ?)",
                (pid, c.numero, c.vence.isoformat(), c.capital_cents, c.interes_cents),
            )
        conn.execute("UPDATE prestamos SET estado = 'aprobado', fecha_desembolso = ? WHERE id = ?", (hoy.isoformat(), pid))
        conn.execute(
            "INSERT INTO movimientos (socio_id, tipo, monto_cents, efectivo, registrado_por) VALUES (?, 'desembolso', ?, 0, ?)",
            (p["socio_id"], p["monto_cents"], int(user["sub"])),
        )
        auditar(conn, user, "aprobar_prestamo", f"préstamo {pid} desembolsado {dolares(p['monto_cents'])}")
    OPERACIONES.labels(tipo="desembolso").inc()
    return {"id": pid, "estado": "aprobado"}


def detalle_prestamo(conn, pid: int, hoy: date) -> dict:
    p = conn.execute("SELECT * FROM prestamos WHERE id = ?", (pid,)).fetchone()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Préstamo no encontrado")
    cuotas = []
    for c in conn.execute("SELECT * FROM cuotas WHERE prestamo_id = ? ORDER BY numero", (pid,)):
        total = c["capital_cents"] + c["interes_cents"]
        atraso = 0 if c["pagada"] else max((hoy - date.fromisoformat(c["vence"])).days, 0)
        cuotas.append(
            {
                "numero": c["numero"],
                "vence": c["vence"],
                "cuota": dolares(total),
                "pagada": bool(c["pagada"]),
                "dias_atraso": atraso,
                "mora": dolares(amortizacion.interes_mora(total, atraso, config.TASA_MORA_ANUAL)),
            }
        )
    return {
        "id": p["id"],
        "socio_id": p["socio_id"],
        "monto": dolares(p["monto_cents"]),
        "tasa_anual": p["tasa_anual"],
        "plazo_meses": p["plazo_meses"],
        "metodo": p["metodo"],
        "estado": p["estado"],
        "cuotas": cuotas,
    }


@app.get("/prestamos/{pid}", tags=["préstamos"])
def ver_prestamo(pid: int, user: Usuario) -> dict:
    conn = db.connect()
    try:
        d = detalle_prestamo(conn, pid, date.today())
    finally:
        conn.close()
    # Un socio solo ve sus préstamos (404 para no revelar que existen otros)
    if user["rol"] != "tesorero" and d["socio_id"] != user.get("socio"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Préstamo no encontrado")
    return d


@app.post("/prestamos/{pid}/pagar", tags=["préstamos"])
def pagar_cuota(pid: int, user: Tesorero) -> dict:
    """Cobra en ventanilla la cuota pendiente más antigua, con su recargo por mora."""
    hoy = date.today()
    with db.transaction() as conn:
        d = detalle_prestamo(conn, pid, hoy)
        pendiente = next((c for c in d["cuotas"] if not c["pagada"]), None)
        if d["estado"] != "aprobado" or not pendiente:
            raise HTTPException(status.HTTP_409_CONFLICT, "No hay cuotas pendientes")
        cobro = cents(Decimal(pendiente["cuota"])) + cents(Decimal(pendiente["mora"]))
        conn.execute("UPDATE cuotas SET pagada = 1 WHERE prestamo_id = ? AND numero = ?", (pid, pendiente["numero"]))
        conn.execute(
            "INSERT INTO movimientos (socio_id, tipo, monto_cents, efectivo, registrado_por) VALUES (?, 'pago_prestamo', ?, 1, ?)",
            (d["socio_id"], cobro, int(user["sub"])),
        )
        if pendiente["numero"] == d["plazo_meses"]:
            conn.execute("UPDATE prestamos SET estado = 'pagado' WHERE id = ?", (pid,))
        auditar(conn, user, "pago_cuota", f"préstamo {pid} cuota {pendiente['numero']} {dolares(cobro)}")
    OPERACIONES.labels(tipo="pago_prestamo").inc()
    return {"cuota": pendiente["numero"], "cobrado": dolares(cobro), "mora": pendiente["mora"]}


# --- Reportes


@app.get("/reportes/cartera", tags=["reportes"])
def cartera(user: Tesorero) -> dict:
    """Cartera de préstamos e índice de morosidad (capital vencido / capital pendiente)."""
    conn = db.connect()
    hoy = date.today().isoformat()
    pendiente = conn.execute(
        "SELECT COALESCE(SUM(capital_cents), 0) FROM cuotas c JOIN prestamos p ON p.id = c.prestamo_id WHERE p.estado = 'aprobado' AND c.pagada = 0"
    ).fetchone()[0]
    vencido = conn.execute(
        "SELECT COALESCE(SUM(capital_cents), 0) FROM cuotas c JOIN prestamos p ON p.id = c.prestamo_id "
        "WHERE p.estado = 'aprobado' AND c.pagada = 0 AND c.vence < ?",
        (hoy,),
    ).fetchone()[0]
    conn.close()
    ratio = vencido / pendiente if pendiente else 0.0
    CARTERA.set(pendiente)
    MOROSIDAD.set(ratio)
    return {"cartera": dolares(pendiente), "vencido": dolares(vencido), "morosidad": round(ratio, 4)}


@app.get("/alertas", tags=["reportes"])
def listar_alertas(user: Tesorero) -> list[dict]:
    conn = db.connect()
    filas = [dict(r) for r in conn.execute("SELECT * FROM alertas ORDER BY id DESC LIMIT 200")]
    conn.close()
    return filas


# --- Operación


@app.get("/salud", tags=["operación"])
def salud() -> dict:
    return {"estado": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

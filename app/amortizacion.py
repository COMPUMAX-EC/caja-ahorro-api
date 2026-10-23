"""Tablas de amortización: método francés (cuota fija) y alemán (capital fijo), en centavos."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Cuota:
    numero: int
    vence: date
    capital_cents: int
    interes_cents: int

    @property
    def total_cents(self) -> int:
        return self.capital_cents + self.interes_cents


def _sumar_meses(inicio: date, meses: int) -> date:
    mes = inicio.month - 1 + meses
    anio, mes = inicio.year + mes // 12, mes % 12 + 1
    # Día 31 en un mes de 30 días: último día del mes
    dias = [31, 29 if anio % 4 == 0 and (anio % 100 or anio % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1]
    return date(anio, mes, min(inicio.day, dias))


def tabla(monto_cents: int, tasa_anual: float, plazo_meses: int, metodo: str, inicio: date) -> list[Cuota]:
    if monto_cents <= 0 or plazo_meses <= 0 or tasa_anual < 0:
        raise ValueError("monto, plazo y tasa deben ser positivos")
    i = tasa_anual / 12
    saldo = monto_cents
    cuotas = []
    cuota_fija = round(monto_cents / plazo_meses) if i == 0 else round(monto_cents * i / (1 - (1 + i) ** -plazo_meses))
    for n in range(1, plazo_meses + 1):
        interes = round(saldo * i)
        if n == plazo_meses:
            capital = saldo  # la última cuota absorbe el redondeo
        elif metodo == "frances":
            capital = cuota_fija - interes
        elif metodo == "aleman":
            capital = round(monto_cents / plazo_meses)
        else:
            raise ValueError("método debe ser 'frances' o 'aleman'")
        saldo -= capital
        cuotas.append(Cuota(n, _sumar_meses(inicio, n), capital, interes))
    return cuotas


def interes_mora(cuota_cents: int, dias_atraso: int, tasa_mora_anual: float) -> int:
    """Recargo por mora sobre la cuota vencida (base 360 días)."""
    return round(cuota_cents * tasa_mora_anual * max(dias_atraso, 0) / 360)

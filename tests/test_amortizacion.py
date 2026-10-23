from datetime import date
from itertools import pairwise

import pytest

from app.amortizacion import interes_mora, tabla


@pytest.mark.parametrize("metodo", ["frances", "aleman"])
def test_el_capital_suma_el_monto(metodo):
    cuotas = tabla(100_000, 0.15, 12, metodo, date(2026, 1, 31))
    assert sum(c.capital_cents for c in cuotas) == 100_000
    assert len(cuotas) == 12


def test_frances_cuota_casi_constante():
    totales = {c.total_cents for c in tabla(100_000, 0.15, 12, "frances", date(2026, 1, 1))[:-1]}
    assert max(totales) - min(totales) <= 1  # solo el redondeo


def test_aleman_capital_constante_e_interes_decreciente():
    cuotas = tabla(120_000, 0.12, 12, "aleman", date(2026, 1, 1))
    assert {c.capital_cents for c in cuotas[:-1]} == {10_000}
    assert all(a.interes_cents > b.interes_cents for a, b in pairwise(cuotas))


def test_cuota_francesa_conocida():
    # $1.000 al 15 % anual a 12 meses: cuota de $90,26
    assert tabla(100_000, 0.15, 12, "frances", date(2026, 1, 1))[0].total_cents == 9026


def test_vencimientos_fin_de_mes():
    cuotas = tabla(10_000, 0.1, 3, "frances", date(2026, 1, 31))
    assert [c.vence for c in cuotas] == [date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_tasa_cero():
    cuotas = tabla(1_000, 0, 3, "frances", date(2026, 1, 1))
    assert [c.interes_cents for c in cuotas] == [0, 0, 0] and sum(c.capital_cents for c in cuotas) == 1_000


def test_mora():
    assert interes_mora(9_000, 36, 0.10) == 90
    assert interes_mora(9_000, -5, 0.10) == 0


def test_datos_invalidos():
    with pytest.raises(ValueError):
        tabla(0, 0.1, 12, "frances", date(2026, 1, 1))

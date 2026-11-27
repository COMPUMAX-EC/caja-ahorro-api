from datetime import date, timedelta

from app import par

TODAY = date(2026, 11, 27)


def loan(lid, days_overdue, principal=100_000, paid_first=False):
    due = (TODAY - timedelta(days=days_overdue)).isoformat()
    cuotas = [{"vence": due, "capital_cents": principal, "pagada": paid_first}]
    cuotas.append({"vence": (TODAY + timedelta(days=30)).isoformat(), "capital_cents": principal, "pagada": False})
    return {"id": lid, "cuotas": cuotas}


def test_par_buckets_nest():
    r = par.par_report([loan(1, -5), loan(2, 15), loan(3, 70), loan(4, 120)], TODAY)
    p = r["par"]
    assert r["cartera_cents"] == 800_000
    assert p["PAR1"]["prestamos"] == 3 and p["PAR30"]["prestamos"] == 2 and p["PAR90"]["prestamos"] == 1
    assert p["PAR1"]["ratio"] >= p["PAR30"]["ratio"] >= p["PAR90"]["ratio"] > 0
    assert p["PAR90"]["capital_cents"] == 200_000  # both installments of the 120-day loan stay outstanding


def test_paid_installment_is_not_late():
    r = par.par_report([loan(1, 200, paid_first=True)], TODAY)
    assert r["par"]["PAR1"]["prestamos"] == 0


def test_empty_portfolio():
    assert par.par_report([], TODAY)["par"]["PAR30"]["ratio"] == 0.0

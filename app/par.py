"""Portfolio at risk (PAR): the standard delinquency indicator banks report.

PAR-N = outstanding principal of loans whose oldest unpaid installment is at least N days late,
divided by total outstanding principal. Pure functions, so they are easy to test.
"""

from datetime import date

BUCKETS = (1, 30, 90)


def days_late(due: str, today: date) -> int:
    return max((today - date.fromisoformat(due)).days, 0)


def par_report(loans: list[dict], today: date) -> dict:
    """loans: [{"id", "cuotas": [{"vence", "capital_cents", "pagada"}]}] for approved loans.

    Returns amounts in cents plus ratios; a loan counts in every bucket its oldest unpaid installment reaches.
    """
    total = 0
    at_risk = {n: 0 for n in BUCKETS}
    count = {n: 0 for n in BUCKETS}
    for loan in loans:
        unpaid = [c for c in loan["cuotas"] if not c["pagada"]]
        outstanding = sum(c["capital_cents"] for c in unpaid)
        total += outstanding
        worst = max((days_late(c["vence"], today) for c in unpaid), default=0)
        for n in BUCKETS:
            if worst >= n:
                at_risk[n] += outstanding
                count[n] += 1
    return {
        "cartera_cents": total,
        "par": {
            f"PAR{n}": {
                "capital_cents": at_risk[n],
                "prestamos": count[n],
                "ratio": round(at_risk[n] / total, 4) if total else 0.0,
            }
            for n in BUCKETS
        },
    }

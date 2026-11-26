# Community Savings Fund API

🇬🇧 **English** · 🇪🇨 [Español](README.es.md)

A demo REST API for an Ecuadorian **community savings and credit fund** (*caja de ahorro*, part of the popular and
solidarity financial sector registered with the SEPS). It covers what many of these funds still keep in notebooks or
spreadsheets:

- **Members and contributions**: member registry, contribution certificates and account statements.
- **Savings**: counter deposits and withdrawals, with balance control.
- **Loans**: simulation and **amortization schedule** with the **French** (fixed installment) or **German** (fixed
  principal) method, approval subject to a **savings-backed limit** (up to 3 times what the member has saved and
  contributed) and disbursement to the member's savings.
- **Arrears**: days overdue and a surcharge per overdue installment, installment collection and the portfolio
  **delinquency ratio**.
- **Alerts**: transactions for the **UAFE** RESU threshold report (from USD 10,000, or several by the same member that
  add up to that amount within 30 days, cash or not), possible cash structuring within 7 days, and large withdrawals.
- **Audit**: every transaction that moves money is logged with who made it.

> This is a demo with test data, built as a portfolio project. It is not in production at any institution.

## Process documentation as code

Savings, loan disbursement and installment collection are documented with Mermaid flows, procedures and controls in
[`docs/procesos/`](docs/procesos/README.md); CI validates sections, links and endpoints (`scripts/check_docs.py`).

## What it shows

| Skill | Where |
|---|---|
| Financial domain (savings and credit) | `app/amortizacion.py`, savings-backed limit, arrears and UAFE rules in `app/main.py` and `app/alertas.py` |
| REST APIs | FastAPI with OpenAPI docs at `/docs` |
| Security | 15-minute JWTs, roles (treasurer/member), PBKDF2 password hashing (600,000 iterations), login rate limiting, security headers, amounts in integer cents, parameterized queries, bandit and pip-audit in CI |
| CI/CD | GitHub Actions: ruff, pytest, bandit, pip-audit, Docker image build and test, automatic deployment |
| Public cloud | Google Cloud Run (scales to zero), Secret Manager and Workload Identity Federation (no keys in the repo) |
| Observability | Prometheus metrics at `/metrics` and a ready-made Grafana dashboard (requests, errors, p95 latency, transactions, alerts, delinquency) |

## Try it

```bash
python -m venv .venv && .venv/Scripts/activate   # on Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt pytest httpx
pytest -q
```

With Docker (API, Prometheus and Grafana):

```bash
docker compose up --build
```

- API and docs: <http://localhost:8080/docs> (user `tesorero`, password `clave-local-tesorero`)
- Grafana: <http://localhost:3000>, dashboard *Caja de ahorro — operación*

Example flow in `/docs`: `POST /auth/token` → `POST /socios` → `POST /movimientos` (deposit and contribution) →
`POST /prestamos/simular` → `POST /prestamos` → `POST /prestamos/{id}/aprobar` → `GET /prestamos/{id}` →
`GET /reportes/cartera`.

The API routes and field names are in Spanish, as used by Ecuadorian funds.

## Deploy

See [docs/deployment.md](docs/deployment.md): Cloud Run on the free tier with a budget alert.

## Configurable rules

Each fund's general assembly sets them; here they are environment variables (`app/config.py`): monthly contribution,
how many times savings can be lent, arrears rate and the large-withdrawal threshold.

License: MIT.

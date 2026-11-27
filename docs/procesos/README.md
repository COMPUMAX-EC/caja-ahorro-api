# Process documentation as code

Each process of the savings fund is documented next to the code that runs it: purpose, roles, a Mermaid flow, the
step-by-step procedure, the controls and the audit trail. CI checks the documents (`scripts/check_docs.py`), so a
procedure cannot silently drift from the API.

| Process | Document | Endpoints |
|---|---|---|
| Savings deposit / withdrawal | [deposito-retiro.md](deposito-retiro.md) | `POST /movimientos` |
| Loan origination and disbursement | [desembolso-prestamo.md](desembolso-prestamo.md) | `POST /prestamos`, `POST /prestamos/{pid}/aprobar` |
| Installment collection | [cobro-cuota.md](cobro-cuota.md) | `POST /prestamos/{pid}/pagar` |

Synthetic data only. The limits shown (3x savings, 10% late surcharge, USD 10,000 UAFE threshold) are example values from
`app/config.py`, not any institution's policy.

Every document has the same sections: Purpose, Roles, Flow, Procedure, Controls, Audit evidence.

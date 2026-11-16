# Project plan

| | |
|---|---|
| **Target sector** | Banking and fintech (banks, cooperatives, digital payments) |
| **Segment** | A (the plan's only segment) |
| **Allocated effort** | 14% of project time (within the 50% for banking and fintech) |
| **Horizon** | 9 Nov 2026 → 31 Jan 2027 |

## Who it is designed for

Savings funds and cooperatives in SEPS segments 3 to 5, and IT teams at large cooperatives (JEP, segment-1 cooperatives) and banks that need credit, arrears and UAFE-alert control.

## Goals

**By 30 Nov 2026**
- [ ] Public demo on Cloud Run with test data and a link in the README
- [ ] Portfolio report by maturity and provisions in an endpoint with tests

**By 31 Dec 2026**
- [ ] Integration with fineract-lab: the same amortization schedule compared against Fineract in CI
- [ ] Grafana dashboard with delinquency by segment and UAFE alerts

**By 31 Jan 2027**
- [ ] End-to-end documented use case (member → loan → arrears → alert) with screenshots
- [ ] Security review against OWASP ASVS level 1 with results in docs/

## Out of scope

Connecting to real member data or to the SEPS system.

---
Reviewed every Sunday: progress on goals and hours spent. Overall sector plan in COMPUMAX-EC/red-contactos-ti (private).

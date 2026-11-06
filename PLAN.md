# Plan del proyecto

| | |
|---|---|
| **Sector objetivo** | Banca y fintech (bancos, cooperativas, pagos digitales) |
| **Segmento** | A (único segmento del plan) |
| **Esfuerzo asignado** | 14 % del tiempo de proyectos (dentro del 50 % de banca y fintech) |
| **Horizonte** | 9-nov-2026 → 31-ene-2027 |

## Para quién se diseña

Cajas de ahorro y cooperativas de los segmentos 3 a 5 de la SEPS, y equipos de TI de cooperativas grandes (JEP, cooperativas del segmento 1) y bancos que necesitan control de crédito, mora y alertas UAFE.

## Metas

**Hasta 30-nov-2026**
- [ ] Demo pública en Cloud Run con datos de prueba y enlace en el README
- [ ] Reporte de cartera por vencimiento y provisiones en un endpoint con pruebas

**Hasta 31-dic-2026**
- [ ] Integración con fineract-lab: la misma tabla de amortización comparada contra Fineract en CI
- [ ] Tablero Grafana con morosidad por segmento y alertas UAFE

**Hasta 31-ene-2027**
- [ ] Caso de uso documentado de punta a punta (socio → préstamo → mora → alerta) con capturas
- [ ] Revisión de seguridad con OWASP ASVS nivel 1 y resultados en docs/

## Fuera de alcance

Conexión con datos reales de socios o con el sistema de la SEPS.

---
Revisión cada domingo: avance de metas y horas dedicadas. Plan general de sectores en COMPUMAX-EC/red-contactos-ti (privado).

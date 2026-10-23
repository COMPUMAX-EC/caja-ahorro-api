"""Métricas para Prometheus (las grafica el tablero de Grafana en grafana/)."""

from prometheus_client import Counter, Gauge, Histogram

PETICIONES = Counter("caja_http_requests_total", "Peticiones HTTP", ["ruta", "metodo", "estado"])
LATENCIA = Histogram("caja_http_request_seconds", "Duración de las peticiones", ["ruta"])
OPERACIONES = Counter("caja_operaciones_total", "Movimientos registrados", ["tipo"])
ALERTAS = Counter("caja_alertas_total", "Alertas de operaciones inusuales", ["regla"])
LOGIN_FALLIDO = Counter("caja_login_fallido_total", "Intentos de inicio de sesión fallidos")
CARTERA = Gauge("caja_cartera_cents", "Capital pendiente de los préstamos aprobados")
MOROSIDAD = Gauge("caja_morosidad_ratio", "Capital vencido sobre cartera total")

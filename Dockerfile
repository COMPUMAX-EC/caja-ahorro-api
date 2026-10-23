FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Sin privilegios de root; la base SQLite vive en /data (en Cloud Run es efímera: es una demo)
RUN useradd --create-home --uid 10001 caja && mkdir /data && chown caja /data
USER caja
ENV CAJA_DB_PATH=/data/caja.db

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/salud')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]

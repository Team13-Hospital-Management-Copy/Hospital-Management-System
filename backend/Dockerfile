FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# TLS is expected to be terminated by a reverse proxy in front of this container (the app's own
# HttpsOnlyMiddleware already trusts X-Forwarded-Proto for that - see app/tls.py). For a
# standalone HTTPS container instead, run `python -m app.serve` (see backend/README.md).
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

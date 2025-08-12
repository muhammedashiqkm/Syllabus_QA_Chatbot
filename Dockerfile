
FROM python:3.11-slim as builder

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .


RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*


RUN useradd --create-home --shell /bin/bash appuser


COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin


COPY . .


RUN chown -R appuser:appuser /app


USER appuser


EXPOSE 5000


ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=development


CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "run:app"]
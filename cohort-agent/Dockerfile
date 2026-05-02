FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py /app/
COPY memory_seeds/ /app/memory_seeds/
COPY skills/ /app/skills/

RUN useradd -m -s /bin/bash tars \
    && mkdir -p /data \
    && chown -R tars:tars /app /data
USER tars

ENV PYTHONUNBUFFERED=1 PORT=8080

EXPOSE 8080

CMD ["python", "-u", "telegram_bot.py"]

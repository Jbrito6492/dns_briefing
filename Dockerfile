FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY dns_briefing/ dns_briefing/
COPY config.toml .

RUN pip install --no-cache-dir .

CMD ["python", "-m", "dns_briefing"]

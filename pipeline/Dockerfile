FROM python:3.12-slim

WORKDIR /app

# Install system deps needed by psycopg2 and dbt-postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# No source copy — volumes mount producers, ingestion, dbt, science at runtime
# See docker-compose.yml pipeline service volumes

CMD ["bash"]
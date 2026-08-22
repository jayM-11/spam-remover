# Always-on Discord bot. Works on Railway, Fly.io, Render workers, a VPS, or a Pi.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
COPY spam_remover ./spam_remover
RUN pip install --no-cache-dir .

# Runtime config comes from environment variables (see .env.example).
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "spam_remover.bot"]

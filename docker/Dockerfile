FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN groupadd --system appuser \
    && useradd --system \
        --gid appuser \
        --create-home \
        --home-dir /home/appuser \
        appuser

WORKDIR /code

# Install Python dependencies
COPY requirements.txt /code/requirements.txt

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /code/requirements.txt

# Copy application
COPY . /code

# Remove Git metadata
RUN rm -rf /code/.git

# Create writable directories
RUN chown -R appuser:appuser /code

RUN mkdir -p /code/logs && chown -R appuser:appuser /code/logs

# Entrypoint must be executable
RUN chmod 755 /code/scripts/docker-entrypoint.sh

# Run application as non-root user
USER appuser



ENTRYPOINT ["/bin/bash", "/code/scripts/docker-entrypoint.sh"]
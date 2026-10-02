FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install only what we need, upgrade existing packages for security patches,
# then clean up apt lists so they don't bloat or leak into the image layer.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip tooling and install dependencies in a single layer, no cache.
RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir flask

# Copy application code after dependencies to maximize layer caching.
COPY app/ .

# Create and switch to a non-root user. Running as root inside the container
# is a common security risk; drop privileges for the running process.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# Basic container-level healthcheck against the app's /health endpoint.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health').status==200 else 1)"

CMD ["python", "app.py"]

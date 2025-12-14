FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system appuser && adduser --system --group appuser

# Install dependencies (use requirements from service)
COPY services/auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities to root to match relative path expectations
COPY shared /shared

# Copy application code
COPY services/auth-service/app /app/app

# Change ownership to non-root user
RUN chown -R appuser:appuser /app /shared

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8001

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

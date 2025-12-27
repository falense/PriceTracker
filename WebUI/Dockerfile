FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

# Install system dependencies (for playwright and general use)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install uv for ExtractorPatternAgent script execution
RUN pip install uv

# Install additional dependencies for ExtractorPatternAgent and PriceFetcher
# These are needed when celery worker calls these components
RUN pip install playwright>=1.40.0 click>=8.1.0 rich>=13.0.0 pyyaml>=6.0 structlog>=23.0.0

# Install playwright browsers (for ExtractorPatternAgent)
RUN playwright install chromium
RUN playwright install-deps chromium || true

# Copy application code
COPY . .

# Create directory for database
RUN mkdir -p /app/data

# Collect static files (optional, might fail if not configured)
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

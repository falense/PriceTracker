FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright/Chromium
RUN apt-get update && apt-get install -y \
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
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/

# Create logs directory
RUN mkdir -p logs

# Install Python dependencies
RUN uv pip install --system -e .

# Install Playwright browsers (Chromium only)
RUN python -m playwright install chromium --with-deps

# Set Python path
ENV PYTHONPATH=/app

# Default command: run fetch job
CMD ["uv", "run", "scripts/run_fetch.py", "--all"]

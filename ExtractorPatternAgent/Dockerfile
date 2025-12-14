FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for playwright
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
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy project configuration
COPY pyproject.toml .
COPY requirements.txt .

# Copy source code
COPY src/ src/
COPY config/ config/
COPY *.py ./

# Create necessary directories
RUN mkdir -p logs data

# Install Python dependencies using uv
RUN uv pip install --system -e .

# Install playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Set Python path
ENV PYTHONPATH=/app

# Set environment variables for headless browser
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Default command (can be overridden)
CMD ["python", "generate_pattern.py", "--help"]

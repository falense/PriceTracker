FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/

# Create logs directory
RUN mkdir -p logs

# Install dependencies
RUN uv pip install --system -e .

# Set Python path
ENV PYTHONPATH=/app

# Default command: run fetch job
CMD ["uv", "run", "scripts/run_fetch.py", "--all"]

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY examples/ examples/

# Install Python dependencies and package
RUN pip install --no-cache-dir -e .

# Default command
CMD ["gridq", "--help"]

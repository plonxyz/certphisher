# Certphisher - Dockerfile
FROM python:3.11-slim

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies in layers for better caching and debugging
# Layer 1: Build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Layer 2: Common utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Layer 3: Python package build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libpng-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Layer 4: OpenCV runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Layer 5: Chromium (optional - for screenshot capture)
# Use fallback if chromium package names differ
RUN apt-get update && \
    (apt-get install -y --no-install-recommends chromium chromium-driver || \
     apt-get install -y --no-install-recommends chromium-browser chromium-chromedriver || \
     echo "Warning: Chromium not installed - screenshot capture will not work") && \
    rm -rf /var/lib/apt/lists/*

# Set Chromium environment variables (try multiple possible locations)
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p /app/app/uploads && \
    chmod -R 755 /app

# Expose Flask port
EXPOSE 5000

# Default command (can be overridden in docker-compose)
CMD ["python3", "main.py"]

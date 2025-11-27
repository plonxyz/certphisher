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

# Layer 5: Chromium for Selenium (optional - for screenshot capture)
# Install from Debian repos with proper driver setup
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libwayland-client0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        xdg-utils \
    && rm -rf /var/lib/apt/lists/* \
    || echo "Warning: Chromium packages not available - screenshot feature will be disabled"

# Set Chromium environment variables for Selenium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Create symlinks for different chromium names
RUN if [ -f /usr/bin/chromium ]; then \
        ln -sf /usr/bin/chromium /usr/bin/chromium-browser || true; \
        ln -sf /usr/bin/chromium /usr/bin/google-chrome || true; \
    elif [ -f /usr/bin/chromium-browser ]; then \
        ln -sf /usr/bin/chromium-browser /usr/bin/chromium || true; \
        export CHROME_BIN=/usr/bin/chromium-browser; \
    fi

# Verify chromium installation (optional, for debugging)
RUN (chromium --version || chromium-browser --version || echo "Chromium not installed") && \
    (chromedriver --version || echo "ChromeDriver not installed")

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

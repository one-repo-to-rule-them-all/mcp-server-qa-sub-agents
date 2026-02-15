# Use Python slim image with Node.js for Playwright
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set Python unbuffered mode
ENV PYTHONUNBUFFERED=1

# Install system dependencies for Playwright and git
RUN apt-get update && apt-get install -y \
    git \
    wget \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (needed for Playwright)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy the server code
COPY qa_council_server.py .

# Create non-root user
RUN useradd -m -u 1000 mcpuser && \
    mkdir -p /app/repos /app/test_results /app/coverage && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Run the server
CMD ["python", "qa_council_server.py"]
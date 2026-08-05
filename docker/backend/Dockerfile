# Base Image
FROM python:3.11-slim

# Python Settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_PATH=/usr/bin/tesseract

# Working Directory
WORKDIR /app

# Install Linux packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file first (better Docker cache)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application
COPY backend ./backend
COPY ml_pipeline ./ml_pipeline
COPY database ./database

COPY run.py .
COPY wsgi.py .

# Expose application port
EXPOSE 5000

# Start application
CMD ["gunicorn","--bind","0.0.0.0:5000","--timeout","180","wsgi:app"]
    
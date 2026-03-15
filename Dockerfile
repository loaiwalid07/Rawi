## ---- Stage 1: Build React Frontend ----
FROM node:20-slim AS frontend-build

WORKDIR /frontend

# Install dependencies first (cache layer)
COPY frontend-react/package.json frontend-react/package-lock.json* ./
RUN npm install

# Copy frontend source and build
COPY frontend-react/ ./
RUN npm run build


## ---- Stage 2: Python Backend ----
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (FFmpeg for video merging)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY main.py .
COPY app/ ./app/

# Copy built frontend from Stage 1 into the expected directory
COPY --from=frontend-build /frontend/dist ./frontend-react/dist

# Create temp dir for media processing
RUN mkdir -p /tmp/story-assets

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

# Run the application
CMD ["python", "main.py"]

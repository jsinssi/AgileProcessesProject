FROM python:3.11-slim

WORKDIR /app

# Install OS dependencies for pandas & NiceGUI
RUN apt-get update && apt-get install -y \
    build-essential \
    libatlas-base-dev \
    && rm -rf /var/lib/apt/lists/*

# Install required Python packages directly 
RUN pip install --no-cache-dir pandas nicegui

# Copy application files
COPY . .

EXPOSE 8080

CMD ["python", "BookRecomendationApp.py"]
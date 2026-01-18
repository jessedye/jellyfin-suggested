FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY jellyfin_suggested.py .

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

CMD ["python", "jellyfin_suggested.py"]

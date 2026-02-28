# Use Python 3.11 slim image for a lightweight container
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies - curl needed for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create the data directory for the database
RUN mkdir -p /app/data

# Environment variable for FastAPI to run in production mode
ENV PYTHONUNBUFFERED=1

# Expose port 8000
EXPOSE 8000

# Health check for container monitoring
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/ping || exit 1

# Command to run the application
# We use --host 0.0.0.0 to make it accessible outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Use Python 3.11 slim image for a lightweight container
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies if any are needed
# (none currently required for our app's pip packages)

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

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

# Command to run the application
# We use --host 0.0.0.0 to make it accessible outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

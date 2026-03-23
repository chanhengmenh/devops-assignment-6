# Use official Python slim image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy and install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application source code
COPY app.py .

# Expose the port uvicorn runs on
EXPOSE 5000

# Run the application with uvicorn (FastAPI ASGI server)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]

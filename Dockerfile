FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy API source code and resources
COPY src/ ./src/
COPY resources/ ./resources/

# Render sets PORT env var; default to 8000
ENV PORT=8000

EXPOSE ${PORT}

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --app-dir src

  FROM python:3.12-slim
  WORKDIR /app
  ENV PYTHONUNBUFFERED=1
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY ping_api.py .
  ENV PORT=8000
  EXPOSE 8000
  CMD uvicorn ping_api:app --host 0.0.0.0 --port ${PORT}

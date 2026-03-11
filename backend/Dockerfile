FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY proto/ proto/

EXPOSE 50051 9090
CMD ["python", "-m", "taskqueue.api.server"]

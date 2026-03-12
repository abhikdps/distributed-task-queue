FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/

EXPOSE 9091
CMD ["python", "-m", "worker.run"]

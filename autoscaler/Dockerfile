FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir docker requests

CMD ["python", "autoscaler.py"]

FROM python:3.11-slim

WORKDIR /app

# --- install system deps for building Python packages safely ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

# --- install Python deps ---
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# --- copy main script ---
COPY modbus_mqtt_bridge.py /app/modbus_mqtt_bridge.py

# optional: mount for MQTT certs
VOLUME ["/etc/mqtt/certs"]

ENV PYTHONUNBUFFERED=1

# Expose Prometheus (8000) and API/Webhook (5000) ports
EXPOSE 8000 5000

CMD ["python", "/app/modbus_mqtt_bridge.py"]

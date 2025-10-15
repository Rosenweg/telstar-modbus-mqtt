FROM python:3.11-slim

WORKDIR /app

# system deps for pymodbus if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY modbus_mqtt_bridge.py /app/modbus_mqtt_bridge.py

# create directory for certificates (optional)
VOLUME ["/etc/mqtt/certs"]

ENV PYTHONUNBUFFERED=1

CMD ["python", "/app/modbus_mqtt_bridge.py"]

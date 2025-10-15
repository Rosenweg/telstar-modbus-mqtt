# Telstar 80A Modbus -> MQTT Bridge (Telstar / Smart-Me)

Dieses Projekt liest Modbus-TCP-Register des Telstar/Smart-Me Zählers und sendet die Messwerte per MQTT.
Außerdem stellt es einen Prometheus /metrics Endpunkt zur Verfügung.

## Features
- Liest alle Register laut Register-Mapping (0x2000 .. 0x205E)
- Skaliert Leistung in W (mW -> W) und Energie in kWh (mWh/Wh -> kWh)
- Publisht JSON pro Register und ein Snapshot-JSON
- Optional: MQTT over TLS (Zertifikate können in `/etc/mqtt/certs` gemountet werden)
- Prometheus-Metriken auf `/metrics`
- GHCR Workflow (push to GitHub -> build & push image to GHCR)

## Environment Variables
- MODBUS_HOST (required)
- MODBUS_PORT (default 502)
- MODBUS_UNIT_ID (default 1)
- MODBUS_ADDRESS_OFFSET (default 0)   # set to -40001 if device uses 40001 addressing
- MQTT_HOST (required)
- MQTT_PORT (default 1883)
- MQTT_USER / MQTT_PASS (optional)
- MQTT_QOS (0/1/2) default 0
- MQTT_RETAIN (true/false) default false
- MQTT_TLS (true/false) default false
- MQTT_TLS_CA, MQTT_TLS_CERT, MQTT_TLS_KEY -- paths inside container (optional)
- MQTT_TLS_INSECURE (true/false) allow invalid cert
- MQTT_TOPIC_PREFIX (default meter/telstar80a)
- INTERVAL (s) default 10
- LOG_LEVEL default INFO
- PROMETHEUS_PORT default 8000
- PROMETHEUS_PREFIX default telstar

## Quickstart (docker-compose)
1. Create a `.env` file with at least:
   ```
   MODBUS_HOST=192.168.1.100
   MQTT_HOST=192.168.1.10
   MQTT_TOPIC_PREFIX=home/meter/telstar80a
   INTERVAL=10
   ```
2. Optional: create `./certs` and place `ca.crt`, `client.crt`, `client.key` if you use TLS.
   Then set:
   ```
   MQTT_TLS=true
   MQTT_TLS_CA=/etc/mqtt/certs/ca.crt
   MQTT_TLS_CERT=/etc/mqtt/certs/client.crt
   MQTT_TLS_KEY=/etc/mqtt/certs/client.key
   MQTT_TLS_INSECURE=false
   ```
3. Build & start:
   ```
   docker-compose up -d --build
   ```
4. Verify:
   - Prometheus metrics: http://<host>:8000/metrics
   - MQTT: subscribe to `<MQTT_TOPIC_PREFIX>/#`

## GitHub Container Registry
The GitHub Actions workflow is configured to push the image to:
`ghcr.io/rosenweg/telstar-modbus-mqtt:latest`
Make sure your repository is `Rosenweg/telstar-modbus-mqtt`.

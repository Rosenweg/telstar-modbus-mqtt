# Telstar 80A Modbus -> MQTT Bridge (Telstar / Smart-Me)

Environment variables:
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

Run with docker-compose:
  docker-compose up -d --build

Prometheus:
  Scrape target: http://<host>:<PROMETHEUS_PORT>/metrics

MQTT Topics:
- <prefix>/<register_name> (JSON payload)
- <prefix>/snapshot (combined JSON, retained if MQTT_RETAIN=true)

Notes:
- If the Modbus addressing in your device is different from the PDF, use MODBUS_ADDRESS_OFFSET to shift.
- Place TLS certs under ./certs and set MQTT_TLS=true and the env paths to the files in the container (/etc/mqtt/certs/...)

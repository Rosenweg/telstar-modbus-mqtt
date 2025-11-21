#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""modbus_mqtt_bridge.py
Reads Modbus TCP registers (from provided register map) and publishes scaled JSON to MQTT.
Also exposes Prometheus metrics on /metrics.
"""

import os
import time
import json
import logging
import threading
from datetime import datetime
from pymodbus.client.sync import ModbusTcpClient
import paho.mqtt.client as mqtt
from prometheus_client import start_http_server, Gauge
from flask import Flask, jsonify

# ----------------------------
# Config from env
# ----------------------------
MODBUS_HOST = os.getenv("MODBUS_HOST", "127.0.0.1")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))
MODBUS_UNIT_ID = int(os.getenv("MODBUS_UNIT_ID", "1"))
# If your device expects an offset (e.g. address base 40001), set MODBUS_ADDRESS_OFFSET to -40001 or similar.
# Default 0 assumes addresses from PDF (hex like 0x2000) are usable directly.
MODBUS_ADDRESS_OFFSET = int(os.getenv("MODBUS_ADDRESS_OFFSET", "0"))

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
MQTT_QOS = int(os.getenv("MQTT_QOS", "0"))
MQTT_RETAIN = os.getenv("MQTT_RETAIN", "false").lower() in ("1", "true", "yes")
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "meter/telstar80a")

# TLS options (optional)
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() in ("1", "true", "yes")
MQTT_TLS_CA = os.getenv("MQTT_TLS_CA")       # path inside container to CA file (optional)
MQTT_TLS_CERT = os.getenv("MQTT_TLS_CERT")   # client cert (optional)
MQTT_TLS_KEY = os.getenv("MQTT_TLS_KEY")     # client key (optional)
MQTT_TLS_INSECURE = os.getenv("MQTT_TLS_INSECURE", "false").lower() in ("1","true","yes")

INTERVAL = int(os.getenv("INTERVAL", "10"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Prometheus
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "8000"))
PROMETHEUS_PREFIX = os.getenv("PROMETHEUS_PREFIX", "telstar")

# API/Webhook port
API_PORT = int(os.getenv("API_PORT", "5000"))

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("modbus-mqtt")

# ----------------------------
# Register mapping (from PDF)
# Format: (address_hex, name, unit, size_bytes, signed)
# ----------------------------
REGISTERS = [
    (0x2000, "serial_number", "", 4, False),
    (0x2002, "date_time_utc", "unix", 4, False),
    (0x2004, "active_power_total_mW", "mW", 4, True),
    (0x2006, "active_power_l1_mW", "mW", 4, True),
    (0x2008, "active_power_l2_mW", "mW", 4, True),
    (0x200A, "active_power_l3_mW", "mW", 4, True),
    (0x200C, "reactive_power_total_mVar", "mVar", 4, False),
    (0x200E, "reactive_power_l1_mVar", "mVar", 4, False),
    (0x2010, "reactive_power_l2_mVar", "mVar", 4, False),
    (0x2012, "reactive_power_l3_mVar", "mVar", 4, False),
    (0x2014, "voltage_l1_mV", "mV", 4, False),
    (0x2016, "voltage_l2_mV", "mV", 4, False),
    (0x2018, "voltage_l3_mV", "mV", 4, False),
    (0x201A, "current_l1_mA", "mA", 4, True),
    (0x201C, "current_l2_mA", "mA", 4, True),
    (0x201E, "current_l3_mA", "mA", 4, True),
    (0x2020, "power_factor_l1_raw", "1/1000", 2, False),
    (0x2021, "power_factor_l2_raw", "1/1000", 2, False),
    (0x2022, "power_factor_l3_raw", "1/1000", 2, False),
    (0x2023, "active_tariff", "", 2, False),
    (0x2024, "active_energy_import_total_mWh", "mWh", 8, False),
    (0x2028, "active_energy_export_total_mWh", "mWh", 8, False),
    (0x202C, "active_energy_import_t1_mWh", "mWh", 8, False),
    (0x2030, "active_energy_import_t2_mWh", "mWh", 8, False),
    (0x2034, "active_energy_export_t1_mWh", "mWh", 8, False),
    (0x2038, "active_energy_export_t2_mWh", "mWh", 8, False),
    (0x203C, "reactive_energy_q1_mVarh", "mVarh", 8, False),
    (0x2040, "reactive_energy_q2_mVarh", "mVarh", 8, False),
    (0x2044, "reactive_energy_q3_mVarh", "mVarh", 8, False),
    (0x2048, "reactive_energy_q4_mVarh", "mVarh", 8, False),
    (0x204C, "active_energy_import_total_Wh", "Wh", 4, False),
    (0x204E, "active_energy_export_total_Wh", "Wh", 4, False),
    (0x2050, "active_energy_import_t1_Wh", "Wh", 4, False),
    (0x2052, "active_energy_import_t2_Wh", "Wh", 4, False),
    (0x2054, "active_energy_export_t1_Wh", "Wh", 4, False),
    (0x2056, "active_energy_export_t2_Wh", "Wh", 4, False),
    (0x2058, "reactive_energy_q1_Varh", "Varh", 4, False),
    (0x205A, "reactive_energy_q2_Varh", "Varh", 4, False),
    (0x205C, "reactive_energy_q3_Varh", "Varh", 4, False),
    (0x205E, "reactive_energy_q4_Varh", "Varh", 4, False),
]

# ----------------------------
# Scaling rules: convert raw to human units
# Each entry name -> (scale_fn, final_unit)
# If not present, raw integer is returned as-is.
# We use: power in W (mW -> W), energy in kWh:
#  - mWh (milli-watt-hour) -> kWh  : divide by 1_000_000
#  - Wh -> kWh : divide by 1000
# ----------------------------
def identity(v): return v

SCALE_MAP = {
    "_mW":      (lambda v: v / 1000.0, "W"),
    "_mV":      (lambda v: v / 1000.0, "V"),
    "_mA":      (lambda v: v / 1000.0, "A"),
    # mWh -> kWh
    "_mWh":     (lambda v: v / 1_000_000.0, "kWh"),
    # mVar -> Var
    "_mVar":    (lambda v: v / 1000.0, "Var"),
    "_mVarh":   (lambda v: v / 1000.0, "Varh"),
    "_1/1000":  (lambda v: v / 1000.0, ""),
    "_rawpf":   (lambda v: v / 1000.0, ""),
    "Wh":       (lambda v: v / 1000.0, "kWh"),  # Wh -> kWh
    "Varh":     (lambda v: v, "Varh"),
}

def scale_value_by_name(name, raw_value, unit_label):
    # try suffix heuristics
    for suffix, (fn, unit) in SCALE_MAP.items():
        if name.endswith(suffix) or unit_label == suffix.replace("_",""):
            return fn(raw_value), unit or unit_label
    # special by unit_label
    if unit_label in ("mW", "mV", "mA", "mWh", "mVar", "mVarh", "1/1000", "Wh"):
        key = "_" + unit_label
        if key in SCALE_MAP:
            fn, unit = SCALE_MAP[key]
            return fn(raw_value), unit
    # default unchanged
    return raw_value, unit_label

# ----------------------------
# Prometheus metrics: one Gauge per register name
# ----------------------------
PROM_GAUGES = {}
for _, name, _, _, _ in REGISTERS:
    metric_name = f"{PROMETHEUS_PREFIX}_{name}".replace(".", "_").replace("-", "_")
    PROM_GAUGES[name] = Gauge(metric_name, f"Telstar register {name}")

SNAPSHOT_GAUGE = Gauge(f"{PROMETHEUS_PREFIX}_snapshot_timestamp", "Snapshot timestamp")

# ----------------------------
# Global state for API/Webhooks
# ----------------------------
latest_data = {
    "timestamp": None,
    "connection_status": "Not connected",
    "registers": {}
}

# ----------------------------
# Flask API for Webhooks
# ----------------------------
app = Flask(__name__)

@app.route('/api/data')
def api_data():
    """Get all register values"""
    return jsonify(latest_data)

@app.route('/api/topics')
def api_topics():
    """List all available topics/register names"""
    topics = list(latest_data.get("registers", {}).keys())
    return jsonify({"topics": topics, "count": len(topics)})

@app.route('/api/topic/<topic_name>')
def api_topic(topic_name):
    """Get a specific topic/register value with scaled unit"""
    registers = latest_data.get("registers", {})
    if topic_name in registers:
        return jsonify({
            "topic": topic_name,
            "data": registers[topic_name],
            "timestamp": latest_data.get("timestamp")
        })
    else:
        return jsonify({
            "error": "Topic not found",
            "topic": topic_name,
            "available_topics": list(registers.keys())
        }), 404

@app.route('/api/topic/<topic_name>/value')
def api_topic_value(topic_name):
    """Get only the scaled value of a specific topic"""
    registers = latest_data.get("registers", {})
    if topic_name in registers:
        return str(registers[topic_name]["value"]), 200, {'Content-Type': 'text/plain'}
    else:
        return f"Topic '{topic_name}' not found", 404

@app.route('/api/topic/<topic_name>/unit')
def api_topic_unit(topic_name):
    """Get only the unit of a specific topic"""
    registers = latest_data.get("registers", {})
    if topic_name in registers:
        return str(registers[topic_name]["unit"]), 200, {'Content-Type': 'text/plain'}
    else:
        return f"Topic '{topic_name}' not found", 404

@app.route('/api/topic/<topic_name>/raw')
def api_topic_raw(topic_name):
    """Get only the raw value of a specific topic"""
    registers = latest_data.get("registers", {})
    if topic_name in registers:
        return str(registers[topic_name]["raw_value"]), 200, {'Content-Type': 'text/plain'}
    else:
        return f"Topic '{topic_name}' not found", 404

# ----------------------------
# Helpers: combine registers (Big Endian)
# ----------------------------
def combine_registers_be(regs, signed=False):
    val = 0
    for r in regs:
        val = (val << 16) | (r & 0xFFFF)
    bits = 16 * len(regs)
    if signed:
        sign_bit = 1 << (bits - 1)
        if val & sign_bit:
            val = val - (1 << bits)
    return val

# ----------------------------
# MQTT client setup
# ----------------------------
mqtt_client = mqtt.Client()
if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

if MQTT_TLS:
    try:
        mqtt_client.tls_insecure_set(MQTT_TLS_INSECURE)
        if MQTT_TLS_CA:
            if MQTT_TLS_CERT and MQTT_TLS_KEY:
                mqtt_client.tls_set(MQTT_TLS_CA, certfile=MQTT_TLS_CERT, keyfile=MQTT_TLS_KEY)
            else:
                mqtt_client.tls_set(MQTT_TLS_CA)
        else:
            if MQTT_TLS_CERT and MQTT_TLS_KEY:
                mqtt_client.tls_set(None, certfile=MQTT_TLS_CERT, keyfile=MQTT_TLS_KEY)
            else:
                mqtt_client.tls_set()  # default
        log.info("MQTT TLS configured (insecure=%s)", MQTT_TLS_INSECURE)
    except Exception as e:
        log.exception("Failed to configure MQTT TLS: %s", e)

def mqtt_connect():
    while True:
        try:
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            mqtt_client.loop_start()
            log.info("Connected to MQTT broker %s:%s", MQTT_HOST, MQTT_PORT)
            return
        except Exception as e:
            log.warning("MQTT connect failed: %s — retry in 5s", e)
            time.sleep(5)

# ----------------------------
# Read a register entry
# ----------------------------
def read_register_entry(client, entry):
    addr_hex, name, unit, size_bytes, signed = entry
    # convert hex to int (pdf uses hex addresses)
    base_address = int(addr_hex)
    address = base_address + MODBUS_ADDRESS_OFFSET
    # count of 16-bit words
    count = size_bytes // 2
    try:
        rr = client.read_holding_registers(address, count, unit=MODBUS_UNIT_ID)
        if rr is None:
            raise Exception("No response (None)")
        if hasattr(rr, "isError") and rr.isError():
            raise Exception(f"Modbus error reading {hex(base_address)}: {rr}")
        regs = rr.registers
        value_raw = combine_registers_be(regs, signed=signed)
        return {
            "name": name,
            "address": hex(base_address),
            "value_raw": value_raw,
            "unit_raw": unit,
            "raw_registers": regs,
            "timestamp": int(time.time())
        }
    except Exception as e:
        log.debug("Exception reading %s (%s): %s", name, hex(base_address), e)
        return None

# ----------------------------
# Main loop
# ----------------------------
def modbus_loop():
    global latest_data
    mqtt_connect()
    client = None
    while True:
        try:
            if client is None:
                client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, timeout=5)
                if not client.connect():
                    log.warning("Cannot connect to Modbus %s:%s — retry in 5s", MODBUS_HOST, MODBUS_PORT)
                    latest_data["connection_status"] = f"Connection failed to {MODBUS_HOST}:{MODBUS_PORT}"
                    client.close()
                    client = None
                    time.sleep(5)
                    continue
                log.info("Connected to Modbus %s:%s", MODBUS_HOST, MODBUS_PORT)
                latest_data["connection_status"] = "Connected"

            results = {}
            for entry in REGISTERS:
                res = read_register_entry(client, entry)
                if res is None:
                    continue
                # scale value
                scaled, scaled_unit = scale_value_by_name(res["name"], res["value_raw"], res["unit_raw"])
                # publish per-register JSON
                topic = f"{MQTT_TOPIC_PREFIX}/{res['name']}"
                payload = {
                    "value": scaled,
                    "unit": scaled_unit,
                    "raw_value": res["value_raw"],
                    "raw_registers": res["raw_registers"],
                    "address": res["address"],
                    "timestamp": res["timestamp"]
                }
                try:
                    mqtt_client.publish(topic, json.dumps(payload), qos=MQTT_QOS, retain=MQTT_RETAIN)
                    log.debug("Published %s -> %s", topic, payload)
                except Exception as e:
                    log.warning("MQTT publish failed for %s: %s", topic, e)

                # Prometheus metric
                try:
                    PROM_GAUGES[res["name"]].set(float(scaled))
                except Exception:
                    # if metric not present or conversion fails, skip
                    pass

                # Store for API/Webhooks (with unit information)
                results[res["name"]] = {
                    "value": scaled,
                    "unit": scaled_unit,
                    "raw_value": res["value_raw"],
                    "raw_registers": res["raw_registers"],
                    "address": res["address"]
                }

            # snapshot (combined)
            snapshot_topic = f"{MQTT_TOPIC_PREFIX}/snapshot"
            snapshot_payload = {"timestamp": int(time.time()), "data": results}
            try:
                mqtt_client.publish(snapshot_topic, json.dumps(snapshot_payload), qos=MQTT_QOS, retain=MQTT_RETAIN)
            except Exception as e:
                log.warning("MQTT publish failed for snapshot: %s", e)

            SNAPSHOT_GAUGE.set(int(time.time()))

            # Update global state for API/Webhooks
            latest_data["registers"] = results
            latest_data["timestamp"] = int(time.time())

            time.sleep(INTERVAL)
        except KeyboardInterrupt:
            log.info("Stopping due to KeyboardInterrupt")
            break
        except Exception as e:
            log.exception("Main loop exception: %s — reconnecting in 5s", e)
            latest_data["connection_status"] = f"Error: {str(e)}"
            if client:
                client.close()
                client = None
            time.sleep(5)

def main():
    # Start Prometheus server
    start_http_server(PROMETHEUS_PORT)
    log.info("Prometheus metrics available on :%s/metrics", PROMETHEUS_PORT)

    # Start Modbus loop in background thread
    modbus_thread = threading.Thread(target=modbus_loop, daemon=True)
    modbus_thread.start()
    log.info("Modbus loop started")

    # Start Flask API server
    log.info("Starting API/Webhook server on port %s", API_PORT)
    app.run(host='0.0.0.0', port=API_PORT, debug=False)

if __name__ == "__main__":
    main()

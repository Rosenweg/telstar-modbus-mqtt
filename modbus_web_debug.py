#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""modbus_web_debug.py
Debug version: Reads Modbus TCP registers and displays them on a web interface.
No MQTT required - perfect for debugging!
"""

import os
import time
import json
import logging
import threading
from datetime import datetime
from pymodbus.client import ModbusTcpClient
from flask import Flask, render_template_string, jsonify

# ----------------------------
# Config from env
# ----------------------------
MODBUS_HOST = os.getenv("MODBUS_HOST", "127.0.0.1")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))
MODBUS_UNIT_ID = int(os.getenv("MODBUS_UNIT_ID", "1"))
MODBUS_ADDRESS_OFFSET = int(os.getenv("MODBUS_ADDRESS_OFFSET", "0"))

INTERVAL = int(os.getenv("INTERVAL", "10"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Web interface port
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("modbus-web-viewer")

# ----------------------------
# Register mapping (from PDF)
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
# Scaling rules
# ----------------------------
SCALE_MAP = {
    "_mW":      (lambda v: v / 1000.0, "W"),
    "_mV":      (lambda v: v / 1000.0, "V"),
    "_mA":      (lambda v: v / 1000.0, "A"),
    "_mWh":     (lambda v: v / 1_000_000.0, "kWh"),
    "_mVar":    (lambda v: v / 1000.0, "Var"),
    "_mVarh":   (lambda v: v / 1000.0, "Varh"),
    "_1/1000":  (lambda v: v / 1000.0, ""),
    "_rawpf":   (lambda v: v / 1000.0, ""),
    "Wh":       (lambda v: v / 1000.0, "kWh"),
    "Varh":     (lambda v: v, "Varh"),
}

def scale_value_by_name(name, raw_value, unit_label):
    for suffix, (fn, unit) in SCALE_MAP.items():
        if name.endswith(suffix) or unit_label == suffix.replace("_",""):
            return fn(raw_value), unit or unit_label
    if unit_label in ("mW", "mV", "mA", "mWh", "mVar", "mVarh", "1/1000", "Wh"):
        key = "_" + unit_label
        if key in SCALE_MAP:
            fn, unit = SCALE_MAP[key]
            return fn(raw_value), unit
    return raw_value, unit_label

# ----------------------------
# Helpers
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

def read_register_entry(client, entry):
    addr_hex, name, unit, size_bytes, signed = entry
    base_address = int(addr_hex)
    address = base_address + MODBUS_ADDRESS_OFFSET
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
# Global state for web interface
# ----------------------------
latest_data = {
    "timestamp": None,
    "connection_status": "Not connected",
    "registers": {}
}

# ----------------------------
# Flask web interface
# ----------------------------
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Telstar Modbus Debug</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        primary: '#667eea',
                        secondary: '#764ba2',
                    }
                }
            }
        }
    </script>
</head>
<body class="bg-gradient-to-br from-primary to-secondary min-h-screen p-4 md:p-8">
    <div class="max-w-7xl mx-auto">
        <div class="bg-white rounded-xl shadow-2xl p-6 md:p-8">
            <h1 class="text-3xl md:text-4xl font-bold text-gray-800 mb-6 pb-4 border-b-4 border-primary flex items-center gap-3">
                <span class="text-4xl">🔌</span>
                Telstar Modbus Debug Interface
            </h1>

            <div id="status" class="mb-6 p-4 rounded-lg font-semibold bg-red-100 text-red-800 border border-red-300">
                Status: Not connected
            </div>

            <div class="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6 rounded-r-lg">
                <div class="flex items-start">
                    <span class="text-2xl mr-3">📊</span>
                    <div class="text-sm text-gray-700">
                        <div class="font-bold mb-1">Configuration:</div>
                        <div>Modbus Host: <span class="font-mono bg-white px-2 py-1 rounded">{{ modbus_host }}:{{ modbus_port }}</span> (Unit ID: {{ modbus_unit_id }})</div>
                        <div class="mt-1">Update Interval: {{ interval }}s | Web Port: {{ web_port }}</div>
                    </div>
                </div>
            </div>

            <div id="content" class="text-center py-12 text-gray-600 text-lg">
                <svg class="animate-spin h-12 w-12 mx-auto mb-4 text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Loading data...
            </div>

            <div class="text-right text-sm text-gray-600 mt-6" id="timestamp"></div>
        </div>
    </div>

    <script>
        function getCategoryColors(name) {
            if (name.includes('power') && !name.includes('reactive'))
                return { border: 'border-red-500', bg: 'bg-red-50', text: 'text-red-700' };
            if (name.includes('voltage'))
                return { border: 'border-yellow-500', bg: 'bg-yellow-50', text: 'text-yellow-700' };
            if (name.includes('current'))
                return { border: 'border-blue-500', bg: 'bg-blue-50', text: 'text-blue-700' };
            if (name.includes('energy'))
                return { border: 'border-green-500', bg: 'bg-green-50', text: 'text-green-700' };
            if (name.includes('reactive'))
                return { border: 'border-purple-500', bg: 'bg-purple-50', text: 'text-purple-700' };
            return { border: 'border-gray-500', bg: 'bg-gray-50', text: 'text-gray-700' };
        }

        function formatValue(value) {
            if (typeof value === 'number') {
                return value.toFixed(3);
            }
            return value;
        }

        function updateData() {
            fetch('/api/data')
                .then(response => response.json())
                .then(data => {
                    // Update status
                    const statusEl = document.getElementById('status');
                    if (data.connection_status === 'Connected') {
                        statusEl.className = 'mb-6 p-4 rounded-lg font-semibold bg-green-100 text-green-800 border border-green-300';
                        statusEl.textContent = '✓ Status: Connected to Modbus';
                    } else {
                        statusEl.className = 'mb-6 p-4 rounded-lg font-semibold bg-red-100 text-red-800 border border-red-300';
                        statusEl.textContent = '✗ Status: ' + data.connection_status;
                    }

                    // Update timestamp
                    if (data.timestamp) {
                        const date = new Date(data.timestamp * 1000);
                        document.getElementById('timestamp').textContent =
                            'Last update: ' + date.toLocaleString();
                    }

                    // Update content
                    const content = document.getElementById('content');
                    if (Object.keys(data.registers).length === 0) {
                        content.innerHTML = '<div class="text-center py-12 text-gray-600 text-lg">No data available yet...</div>';
                        return;
                    }

                    let html = '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">';
                    for (const [name, info] of Object.entries(data.registers)) {
                        const colors = getCategoryColors(name);
                        html += `
                            <div class="group ${colors.bg} hover:shadow-lg transition-all duration-200 p-4 rounded-lg border-l-4 ${colors.border}">
                                <div class="font-bold ${colors.text} text-xs uppercase tracking-wide mb-2">
                                    ${name.replace(/_/g, ' ')}
                                </div>
                                <div class="text-3xl font-bold text-gray-800 my-2">
                                    ${formatValue(info.value)}
                                    <span class="text-lg text-gray-600 ml-1">${info.unit}</span>
                                </div>
                                <div class="text-xs text-gray-600 mt-3 pt-3 border-t border-gray-200 space-y-1">
                                    <div class="flex justify-between">
                                        <span class="font-medium">Address:</span>
                                        <span class="font-mono">${info.address}</span>
                                    </div>
                                    <div class="flex justify-between">
                                        <span class="font-medium">Raw value:</span>
                                        <span class="font-mono">${info.raw_value}</span>
                                    </div>
                                    <div class="flex justify-between">
                                        <span class="font-medium">Registers:</span>
                                        <span class="font-mono text-xs">[${info.raw_registers.join(', ')}]</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                    html += '</div>';
                    content.innerHTML = html;
                })
                .catch(error => {
                    console.error('Error fetching data:', error);
                    const statusEl = document.getElementById('status');
                    statusEl.className = 'mb-6 p-4 rounded-lg font-semibold bg-red-100 text-red-800 border border-red-300';
                    statusEl.textContent = '✗ Status: Error fetching data';
                });
        }

        // Initial load
        updateData();

        // Auto-refresh every 2 seconds
        setInterval(updateData, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE,
                                 modbus_host=MODBUS_HOST,
                                 modbus_port=MODBUS_PORT,
                                 modbus_unit_id=MODBUS_UNIT_ID,
                                 interval=INTERVAL,
                                 web_port=WEB_PORT)

@app.route('/api/data')
def api_data():
    return jsonify(latest_data)

@app.route('/api/topics')
def api_topics():
    """List all available topics/register names"""
    topics = list(latest_data.get("registers", {}).keys())
    return jsonify({"topics": topics, "count": len(topics)})

@app.route('/api/topic/<topic_name>')
def api_topic(topic_name):
    """Get a specific topic/register value"""
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
# Modbus reading loop
# ----------------------------
def modbus_loop():
    global latest_data
    client = None

    while True:
        try:
            if client is None:
                log.info("Connecting to Modbus %s:%s", MODBUS_HOST, MODBUS_PORT)
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

                # Scale value
                scaled, scaled_unit = scale_value_by_name(res["name"], res["value_raw"], res["unit_raw"])

                results[res["name"]] = {
                    "value": scaled,
                    "unit": scaled_unit,
                    "raw_value": res["value_raw"],
                    "raw_registers": res["raw_registers"],
                    "address": res["address"]
                }

            latest_data["registers"] = results
            latest_data["timestamp"] = int(time.time())

            log.debug("Read %d registers successfully", len(results))
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

# ----------------------------
# Main entry point
# ----------------------------
def main():
    # Start Modbus reading thread
    modbus_thread = threading.Thread(target=modbus_loop, daemon=True)
    modbus_thread.start()
    log.info("Modbus reading thread started")

    # Start Flask web server
    log.info("Starting web interface on port %s", WEB_PORT)
    log.info("Open http://localhost:%s in your browser", WEB_PORT)
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)

if __name__ == "__main__":
    main()

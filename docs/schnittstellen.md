# Telstar-Bridge – Schnittstellen

MQTT-Topics, Prometheus-Metriken und REST-API (aus dem README hierher verschoben).

## MQTT Topics

Die Bridge publiziert auf folgende Topics (mit konfiguriertem Präfix):

- `<prefix>/register/<register_name>` - Einzelne Registerwerte
- `<prefix>/snapshot` - Kompletter Snapshot aller Werte
- `<prefix>/status` - Status-Informationen der Bridge

Beispiel Payload:
```json
{
  "register": "0x2000",
  "name": "ActivePower_L1",
  "value": 1234.5,
  "unit": "W",
  "timestamp": "2025-11-21T10:30:00Z"
}
```

## Prometheus Metriken

Verfügbare Metriken unter `/metrics`:
- `{prefix}_active_power_l1` - Wirkleistung Phase L1 (W)
- `{prefix}_active_power_l2` - Wirkleistung Phase L2 (W)
- `{prefix}_active_power_l3` - Wirkleistung Phase L3 (W)
- `{prefix}_total_active_energy` - Gesamtenergie (kWh)
- Weitere Metriken für Spannung, Strom, Frequenz, etc.

## REST-API / Webhook-Integration

Die Bridge stellt eine REST-API zur Verfügung, über die externe Systeme die aktuellen Messwerte abrufen können. Dies ermöglicht die Integration mit Home Automation Systemen, Monitoring-Tools oder benutzerdefinierten Dashboards.

### Konfiguration

Die API läuft auf Port `5000` (Standard) und kann über die Umgebungsvariable `API_PORT` konfiguriert werden:

```env
API_PORT=5000
```

Der API-Server ist unter `http://<host>:<API_PORT>` erreichbar.

### Verfügbare Endpunkte

#### 1. Alle Daten abrufen
```
GET /api/data
```

Gibt alle Register-Werte sowie Verbindungsstatus und Timestamp zurück.

**Beispiel:**
```bash
curl http://localhost:5000/api/data
```

**Antwort:**
```json
{
  "timestamp": 1700567890,
  "connection_status": "Connected",
  "registers": {
    "active_power_l1_mW": {
      "value": 1234.5,
      "unit": "W",
      "raw_value": 1234500,
      "raw_registers": [18, 53184],
      "address": "0x2006"
    },
    "voltage_l1_mV": {
      "value": 230.5,
      "unit": "V",
      "raw_value": 230500,
      "raw_registers": [3, 34516],
      "address": "0x2014"
    }
    // ... weitere Register
  }
}
```

#### 2. Verfügbare Topics auflisten
```
GET /api/topics
```

Gibt eine Liste aller verfügbaren Register-Namen zurück.

**Beispiel:**
```bash
curl http://localhost:5000/api/topics
```

**Antwort:**
```json
{
  "topics": [
    "serial_number",
    "active_power_l1_mW",
    "active_power_l2_mW",
    "voltage_l1_mV",
    "current_l1_mA"
  ],
  "count": 38
}
```

#### 3. Spezifisches Register abrufen
```
GET /api/topic/<topic_name>
```

Gibt detaillierte Informationen zu einem bestimmten Register zurück (JSON-Format).

**Beispiel:**
```bash
curl http://localhost:5000/api/topic/active_power_l1_mW
```

**Antwort:**
```json
{
  "topic": "active_power_l1_mW",
  "timestamp": 1700567890,
  "data": {
    "value": 1234.5,
    "unit": "W",
    "raw_value": 1234500,
    "raw_registers": [18, 53184],
    "address": "0x2006"
  }
}
```

**Fehlerfall (404):**
```json
{
  "error": "Topic not found",
  "topic": "unknown_topic",
  "available_topics": ["serial_number", "active_power_l1_mW", ...]
}
```

#### 4. Nur Wert abrufen (Plain Text)
```
GET /api/topic/<topic_name>/value
```

Gibt nur den skalierten Wert als Plain Text zurück - ideal für einfache Integrationen.

**Beispiel:**
```bash
curl http://localhost:5000/api/topic/active_power_l1_mW/value
```

**Antwort:**
```
1234.5
```

#### 5. Nur Einheit abrufen (Plain Text)
```
GET /api/topic/<topic_name>/unit
```

Gibt nur die Einheit als Plain Text zurück.

**Beispiel:**
```bash
curl http://localhost:5000/api/topic/active_power_l1_mW/unit
```

**Antwort:**
```
W
```

#### 6. Nur Roh-Wert abrufen (Plain Text)
```
GET /api/topic/<topic_name>/raw
```

Gibt den unskalierte Roh-Wert als Plain Text zurück.

**Beispiel:**
```bash
curl http://localhost:5000/api/topic/active_power_l1_mW/raw
```

**Antwort:**
```
1234500
```

### Wichtige Register-Namen

Die folgenden Register sind besonders relevant für die meisten Anwendungsfälle:

| Register-Name | Beschreibung | Einheit (skaliert) |
|--------------|--------------|-------------------|
| `active_power_total_mW` | Gesamtleistung | W |
| `active_power_l1_mW` | Leistung Phase L1 | W |
| `active_power_l2_mW` | Leistung Phase L2 | W |
| `active_power_l3_mW` | Leistung Phase L3 | W |
| `voltage_l1_mV` | Spannung Phase L1 | V |
| `voltage_l2_mV` | Spannung Phase L2 | V |
| `voltage_l3_mV` | Spannung Phase L3 | V |
| `current_l1_mA` | Strom Phase L1 | A |
| `current_l2_mA` | Strom Phase L2 | A |
| `current_l3_mA` | Strom Phase L3 | A |
| `active_energy_import_total_mWh` | Gesamtenergie Import | kWh |
| `active_energy_export_total_mWh` | Gesamtenergie Export | kWh |

Alle verfügbaren Register können über `/api/topics` abgerufen werden.

### Integration mit Home Assistant

Die API kann einfach in Home Assistant mit dem RESTful Sensor integriert werden:

```yaml
sensor:
  - platform: rest
    name: "Stromverbrauch Total"
    resource: http://<bridge-ip>:5000/api/topic/active_power_total_mW/value
    unit_of_measurement: "W"
    value_template: "{{ value | float }}"
    scan_interval: 10

  - platform: rest
    name: "Energie Import"
    resource: http://<bridge-ip>:5000/api/topic/active_energy_import_total_mWh/value
    unit_of_measurement: "kWh"
    value_template: "{{ value | float }}"
    scan_interval: 60
```

### Integration mit Node-RED

Beispiel für einen HTTP-Request Node in Node-RED:

```json
{
  "method": "GET",
  "url": "http://<bridge-ip>:5000/api/topic/active_power_l1_mW",
  "headers": {
    "Content-Type": "application/json"
  }
}
```

### Polling vs. MQTT

**REST-API (Polling):**
- ✅ Einfache Integration ohne MQTT-Setup
- ✅ Ideal für gelegentliche Abfragen
- ✅ Kein MQTT-Broker erforderlich
- ❌ Höhere Latenz bei vielen Clients
- ❌ Mehr Netzwerkverkehr bei häufigen Abfragen

**MQTT (Push):**
- ✅ Echtzeit-Updates bei Änderungen
- ✅ Effizient bei vielen Subscribern
- ✅ Geringere Netzwerklast
- ❌ Erfordert MQTT-Broker
- ❌ Komplexere Einrichtung

**Empfehlung:** Nutze MQTT für Echtzeit-Monitoring und die REST-API für gelegentliche Abfragen oder wenn kein MQTT-Broker verfügbar ist.

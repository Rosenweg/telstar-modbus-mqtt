# Telstar 80A Modbus -> MQTT Bridge (Telstar / Smart-Me)

Dieses Projekt liest Modbus-TCP-Register des Telstar/Smart-Me Zählers und sendet die Messwerte per MQTT.
Außerdem stellt es einen Prometheus /metrics Endpunkt sowie eine REST-API für externe Systeme zur Verfügung.

## Features
- **Modbus-TCP Integration**: Liest alle Register laut Register-Mapping (0x2000 .. 0x205E)
- **Automatische Skalierung**: Konvertiert Leistung in W (mW → W) und Energie in kWh (mWh/Wh → kWh)
- **MQTT Publishing**: Publisht JSON pro Register und einen kompletten Snapshot
- **TLS-Unterstützung**: Optional MQTT over TLS (Zertifikate können in `/etc/mqtt/certs` gemountet werden)
- **Prometheus-Integration**: Metriken auf `/metrics` Endpunkt für Monitoring
- **REST-API**: Umfassende HTTP-API für externe Systeme und Home Automation
- **Debug-Modus**: Separater Web-Viewer Container für Entwicklung und Debugging

## Konfiguration

### Umgebungsvariablen

#### Modbus-Konfiguration
| Variable | Erforderlich | Standard | Beschreibung |
|----------|--------------|----------|--------------|
| `MODBUS_HOST` | Ja | - | IP-Adresse oder Hostname des Modbus-Geräts |
| `MODBUS_PORT` | Nein | 502 | Modbus-TCP Port |
| `MODBUS_UNIT_ID` | Nein | 1 | Modbus Unit ID |
| `MODBUS_ADDRESS_OFFSET` | Nein | 0 | Offset für Registeradressen (z.B. -40001 bei 40001-Adressierung) |

#### MQTT-Konfiguration
| Variable | Erforderlich | Standard | Beschreibung |
|----------|--------------|----------|--------------|
| `MQTT_HOST` | Ja | - | MQTT Broker Hostname/IP |
| `MQTT_PORT` | Nein | 1883 | MQTT Broker Port |
| `MQTT_USER` | Nein | - | MQTT Benutzername |
| `MQTT_PASS` | Nein | - | MQTT Passwort |
| `MQTT_QOS` | Nein | 0 | Quality of Service (0, 1, oder 2) |
| `MQTT_RETAIN` | Nein | false | Nachrichten als Retained markieren |
| `MQTT_TLS` | Nein | false | TLS-Verschlüsselung aktivieren |
| `MQTT_TLS_CA` | Nein | - | Pfad zum CA-Zertifikat (im Container) |
| `MQTT_TLS_CERT` | Nein | - | Pfad zum Client-Zertifikat (im Container) |
| `MQTT_TLS_KEY` | Nein | - | Pfad zum Client-Key (im Container) |
| `MQTT_TLS_INSECURE` | Nein | false | Ungültige Zertifikate akzeptieren |
| `MQTT_TOPIC_PREFIX` | Nein | meter/telstar80a | Präfix für MQTT Topics |

#### Allgemeine Einstellungen
| Variable | Erforderlich | Standard | Beschreibung |
|----------|--------------|----------|--------------|
| `INTERVAL` | Nein | 10 | Abfrageintervall in Sekunden |
| `LOG_LEVEL` | Nein | INFO | Log-Level (DEBUG, INFO, WARNING, ERROR) |
| `PROMETHEUS_PORT` | Nein | 8000 | Port für Prometheus Metrics |
| `PROMETHEUS_PREFIX` | Nein | telstar | Präfix für Prometheus Metriken |
| `API_PORT` | Nein | 5000 | Port für die REST-API (Webhooks) |

## Installation und Nutzung

### Mit Docker Compose (Empfohlen)

1. **Erstelle eine `.env` Datei** mit den Mindestanforderungen:
   ```env
   MODBUS_HOST=192.168.1.100
   MQTT_HOST=192.168.1.10
   MQTT_TOPIC_PREFIX=home/meter/telstar80a
   INTERVAL=10
   ```

2. **Optional: TLS-Zertifikate einrichten**

   Erstelle ein `./certs` Verzeichnis und platziere die Zertifikate:
   - `ca.crt` - CA-Zertifikat
   - `client.crt` - Client-Zertifikat
   - `client.key` - Client-Key

   Erweitere die `.env` Datei:
   ```env
   MQTT_TLS=true
   MQTT_TLS_CA=/etc/mqtt/certs/ca.crt
   MQTT_TLS_CERT=/etc/mqtt/certs/client.crt
   MQTT_TLS_KEY=/etc/mqtt/certs/client.key
   MQTT_TLS_INSECURE=false
   ```

3. **Container starten**
   ```bash
   docker-compose up -d
   ```

   Der Service heißt `mqtt` und verwendet das vorgefertigte Image von ghcr.io.
   Für lokale Entwicklung kann auch mit `--build` das Image lokal gebaut werden.

4. **Funktionalität überprüfen**
   - REST-API: `http://<host>:5000/api/data`
   - Prometheus Metriken: `http://<host>:8000/metrics`
   - MQTT: Subscribe zu `<MQTT_TOPIC_PREFIX>/#`
   - Logs: `docker-compose logs -f`

### Mit Docker (Standalone)

```bash
docker pull ghcr.io/rosenweg/telstar-modbus-mqtt:latest
docker run -d \
  --name telstar-mqtt-bridge \
  -e MODBUS_HOST=192.168.1.100 \
  -e MQTT_HOST=192.168.1.10 \
  -p 8000:8000 \
  -p 5000:5000 \
  ghcr.io/rosenweg/telstar-modbus-mqtt:latest
```

### Debug-Modus

Für Entwicklung und Debugging steht ein separater Container mit Web-Interface zur Verfügung:

```bash
docker-compose -f docker-compose-debug.yml up -d
```

Der Debug-Container (Service `web`) bietet:
- Web-Interface auf Port 5000 (Standard)
- Echtzeit-Anzeige aller Modbus-Register
- REST-API für direkten Datenabruf
- Detaillierte Logging-Informationen
- Verwendet das vorgefertigte Image von ghcr.io

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

## Fehlerbehebung

### Container startet nicht
```bash
docker-compose logs
```

### Keine Verbindung zum Modbus-Gerät
- Prüfe die IP-Adresse und Port
- Stelle sicher, dass das Gerät erreichbar ist: `ping <MODBUS_HOST>`
- Überprüfe Firewall-Einstellungen

### MQTT-Verbindungsprobleme
- Verifiziere MQTT Broker Erreichbarkeit
- Prüfe Benutzername und Passwort
- Bei TLS: Verifiziere Zertifikatspfade und -inhalte

### Debug-Logging aktivieren
```env
LOG_LEVEL=DEBUG
```

## Lizenz

Dieses Projekt ist Open Source und kann frei verwendet werden.

## Support

Bei Fragen oder Problemen erstelle bitte ein Issue im Repository.

# Telstar 80A Modbus -> MQTT Bridge (Telstar / Smart-Me)

Dieses Projekt liest Modbus-TCP-Register des Telstar/Smart-Me Zählers und sendet die Messwerte per MQTT.
Außerdem stellt es einen Prometheus /metrics Endpunkt zur Verfügung und bietet Webhook-Unterstützung für Echtzeit-Benachrichtigungen.

## Features
- **Modbus-TCP Integration**: Liest alle Register laut Register-Mapping (0x2000 .. 0x205E)
- **Automatische Skalierung**: Konvertiert Leistung in W (mW → W) und Energie in kWh (mWh/Wh → kWh)
- **MQTT Publishing**: Publisht JSON pro Register und einen kompletten Snapshot
- **TLS-Unterstützung**: Optional MQTT over TLS (Zertifikate können in `/etc/mqtt/certs` gemountet werden)
- **Prometheus-Integration**: Metriken auf `/metrics` Endpunkt für Monitoring
- **Webhooks**: Automatische Benachrichtigungen bei Wertänderungen
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
   docker-compose up -d --build
   ```

4. **Funktionalität überprüfen**
   - Prometheus Metriken: `http://<host>:8000/metrics`
   - MQTT: Subscribe zu `<MQTT_TOPIC_PREFIX>/#`
   - Logs: `docker-compose logs -f`

### Mit Docker (Standalone)

```bash
docker build -t telstar-modbus-mqtt .
docker run -d \
  --name telstar-bridge \
  -e MODBUS_HOST=192.168.1.100 \
  -e MQTT_HOST=192.168.1.10 \
  -p 8000:8000 \
  telstar-modbus-mqtt
```

### Debug-Modus

Für Entwicklung und Debugging steht ein separater Container mit Web-Interface zur Verfügung:

```bash
docker-compose -f docker-compose-debug.yml up -d
```

Der Debug-Container bietet:
- Web-Interface auf Port 5001
- Echtzeit-Anzeige aller Modbus-Register
- Webhook-Test-Interface
- Detaillierte Logging-Informationen

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

## Webhook-Integration

Webhooks können konfiguriert werden, um bei Wertänderungen Benachrichtigungen zu erhalten.
Die Webhook-URLs können über Umgebungsvariablen oder die Web-Schnittstelle konfiguriert werden.

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

# Telstar-Bridge – Einrichten und Betrieb

Technische Details, aus dem README hierher verschoben. Die Schnittstellen (MQTT, Prometheus, REST-API) stehen in [schnittstellen.md](schnittstellen.md).

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

Das Projekt bietet zwei Docker-Compose-Konfigurationen:
- **docker-compose.mqtt.yml**: MQTT-Bridge (Produktiv-Setup mit MQTT, Prometheus und REST-API)
- **docker-compose.web.yml**: Web-Viewer (Debug-Setup ohne MQTT, nur Web-Interface und REST-API)

### Hinweis zu Docker-Images

Beide Compose-Dateien ziehen fertige Images aus der GitHub Container Registry
(`ghcr.io/rosenweg/telstar-modbus-mqtt:latest` bzw.
`ghcr.io/rosenweg/telstar-modbus-web-viewer:latest`), gebaut von den Workflows
`build.yml` und `build-debug.yml`. Sind die Packages privat, vorher anmelden:

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

Wer lieber lokal baut, ersetzt in der Compose-Datei `image:` durch
`build: .` (MQTT-Bridge, `Dockerfile`) bzw. `build: { context: ., dockerfile: Dockerfile.debug }`
(Web-Viewer) oder nimmt den Weg unter „Mit Docker (Standalone)“.

### Mit Docker Compose (Empfohlen)

1. **Konfiguration anlegen.** Vorlagen mit allen Variablen liegen bei: `.env.mqtt`
   (MQTT-Bridge) und `.env.web` (Web-Viewer); Start dann mit `--env-file .env.mqtt`
   bzw. `--env-file .env.web`. Oder eine `.env` Datei mit den Mindestanforderungen:
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
   docker-compose -f docker-compose.mqtt.yml up -d
   ```

   Der Service heißt `mqtt` und nutzt das Image von ghcr.io (siehe oben).

4. **Funktionalität überprüfen**
   - REST-API: `http://<host>:5000/api/data`
   - Prometheus Metriken: `http://<host>:8000/metrics`
   - MQTT: Subscribe zu `<MQTT_TOPIC_PREFIX>/#`
   - Logs: `docker-compose -f docker-compose.mqtt.yml logs -f mqtt`

### Mit Docker (Standalone)

```bash
# Image lokal bauen
docker build -t telstar-modbus-mqtt:local -f Dockerfile .

# Container starten
docker run -d \
  --name telstar-mqtt-bridge \
  -e MODBUS_HOST=192.168.1.100 \
  -e MQTT_HOST=192.168.1.10 \
  -p 8000:8000 \
  -p 5000:5000 \
  telstar-modbus-mqtt:local
```

### Debug-Modus (Web-Viewer)

Für Entwicklung und Debugging steht ein separater Container mit Web-Interface zur Verfügung:

```bash
docker-compose -f docker-compose.web.yml up -d
```

Der Debug-Container (Service `web`) bietet:
- Web-Interface auf Port 5000 (Standard)
- Echtzeit-Anzeige aller Modbus-Register
- REST-API für direkten Datenabruf
- Detaillierte Logging-Informationen
- Baut automatisch lokal aus dem Dockerfile.debug

## Fehlerbehebung

### Container startet nicht
```bash
# MQTT-Bridge Logs
docker-compose -f docker-compose.mqtt.yml logs -f mqtt

# Web-Viewer Logs
docker-compose -f docker-compose.web.yml logs -f web
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

## Support

Bei Fragen oder Problemen erstelle bitte ein Issue im Repository.

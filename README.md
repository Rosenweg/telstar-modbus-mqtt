<p align="center"><img src="docs/logo.png" width="96" alt="Logo"></p>
<h1 align="center">Rosenweg Telstar-Bridge</h1>
<p align="center">Liest den Stromzähler Telstar 80A (Smart-Me) per Modbus aus und stellt die Werte für Haussteuerung und Überwachung bereit.</p>
<p align="center"><a href="docs/schnittstellen.md">Schnittstellen</a> · <a href="docs/entwickeln.md">Anleitung</a></p>

## Inhalt

- [Überblick](#überblick)
- [Läuft auf](#läuft-auf)
- [Schnittstellen](#schnittstellen)
- [Wichtige Messwerte](#wichtige-messwerte)
- [Aufbau](#aufbau)
- [Bauen und CI](#bauen-und-ci)
- [Ausrollen und Betrieb](#ausrollen-und-betrieb)
- [Konfiguration](#konfiguration)
- [Fehlerbehebung](#fehlerbehebung)
- [Lizenz](#lizenz)

## Überblick

Die Bridge fragt die Modbus-TCP-Register des Zählers (0x2000 bis 0x205E) im Takt ab, rechnet sie in übliche Einheiten um (mW → W, mWh/Wh → kWh) und gibt sie weiter:

- **MQTT:** ein JSON je Register und ein kompletter Schnappschuss, auf Wunsch über TLS.
- **Prometheus:** Metriken unter `/metrics` fürs Monitoring.
- **REST-API:** einfache HTTP-Abfragen, z.B. für Home Assistant oder Node-RED.
- **Web-Viewer:** eigener Container zum Nachschauen aller Register und zur Fehlersuche.

## Läuft auf

| Plattform | Stand |
|---|---|
| Docker / Docker Compose | ja, fertige Images auf ghcr.io |
| Python 3 direkt | ja (`requirements.txt`) |

## Schnittstellen

| Schnittstelle | Adresse | Inhalt |
|---|---|---|
| MQTT | `<prefix>/register/<name>` | einzelner Registerwert (JSON mit Wert, Einheit, Zeit) |
| MQTT | `<prefix>/snapshot` | alle Werte auf einmal |
| MQTT | `<prefix>/status` | Zustand der Bridge |
| Prometheus | `http://<host>:8000/metrics` | z.B. `<prefix>_active_power_l1`, `<prefix>_total_active_energy` |
| REST | `GET /api/data` | alle Register mit Verbindungsstatus |
| REST | `GET /api/topics` | Liste der Register-Namen |
| REST | `GET /api/topic/<name>` | ein Register als JSON |
| REST | `GET /api/topic/<name>/value`, `/unit`, `/raw` | nur Wert, Einheit oder Rohwert als Text |

Die REST-API läuft auf Port 5000. **Wann was:** MQTT für laufende Überwachung mit vielen Abnehmern, REST für gelegentliche Abfragen oder wenn kein Broker da ist.

Beispiel Home Assistant:

```yaml
sensor:
  - platform: rest
    name: "Stromverbrauch Total"
    resource: http://<bridge-ip>:5000/api/topic/active_power_total_mW/value
    unit_of_measurement: "W"
    value_template: "{{ value | float }}"
    scan_interval: 10
```

Mehr (alle Antworten, Node-RED, Fehlerfälle): [docs/schnittstellen.md](docs/schnittstellen.md).

## Wichtige Messwerte

| Register-Name | Bedeutung | Einheit |
|---|---|---|
| `active_power_total_mW` | Gesamtleistung | W |
| `active_power_l1_mW` … `_l3_mW` | Leistung je Phase | W |
| `voltage_l1_mV` … `_l3_mV` | Spannung je Phase | V |
| `current_l1_mA` … `_l3_mA` | Strom je Phase | A |
| `active_energy_import_total_mWh` | Energie Bezug | kWh |
| `active_energy_export_total_mWh` | Energie Einspeisung | kWh |

Alle Namen liefert `/api/topics`.

## Aufbau

| Teil | Inhalt |
|---|---|
| `modbus_mqtt_bridge.py` | Bridge: Modbus → MQTT, Prometheus, REST-API |
| `modbus_web_debug.py` | Web-Viewer: Echtzeit-Anzeige und REST-API, ohne MQTT |
| `Dockerfile`, `Dockerfile.debug` | Images für Bridge und Web-Viewer |
| `docker-compose.mqtt.yml`, `docker-compose.web.yml` | Betrieb (Bridge) bzw. Fehlersuche (Web-Viewer) |
| `.env.mqtt`, `.env.web` | Vorlagen mit allen Variablen |

## Bauen und CI

| Workflow | Ergebnis |
|---|---|
| `build.yml` | Image `ghcr.io/rosenweg/telstar-modbus-mqtt:latest` |
| `build-debug.yml` | Image `ghcr.io/rosenweg/telstar-modbus-web-viewer:latest` |

Lokal bauen: `docker build -t telstar-modbus-mqtt:local -f Dockerfile .` – oder in der Compose-Datei `image:` durch `build: .` ersetzen.

## Ausrollen und Betrieb

```bash
docker-compose -f docker-compose.mqtt.yml --env-file .env.mqtt up -d   # Bridge
docker-compose -f docker-compose.web.yml --env-file .env.web up -d     # Web-Viewer
```

| Aufgabe | So geht's |
|---|---|
| Logs Bridge | `docker-compose -f docker-compose.mqtt.yml logs -f mqtt` |
| Logs Web-Viewer | `docker-compose -f docker-compose.web.yml logs -f web` |
| Prüfen | `/api/data`, `/metrics`, MQTT `<prefix>/#` abonnieren |
| TLS | Zertifikate nach `./certs` (`ca.crt`, `client.crt`, `client.key`), im Container unter `/etc/mqtt/certs` |
| Private Images | vorher `docker login ghcr.io` |

## Konfiguration

Umgebungsvariablen, nur die Namen (Vorgaben und Erklärungen in [docs/entwickeln.md](docs/entwickeln.md)):

| Bereich | Variablen |
|---|---|
| Modbus | `MODBUS_HOST` (Pflicht), `MODBUS_PORT`, `MODBUS_UNIT_ID`, `MODBUS_ADDRESS_OFFSET` |
| MQTT | `MQTT_HOST` (Pflicht), `MQTT_PORT`, `MQTT_USER`, `MQTT_PASS`, `MQTT_QOS`, `MQTT_RETAIN`, `MQTT_TOPIC_PREFIX` |
| MQTT-TLS | `MQTT_TLS`, `MQTT_TLS_CA`, `MQTT_TLS_CERT`, `MQTT_TLS_KEY`, `MQTT_TLS_INSECURE` |
| Allgemein | `INTERVAL`, `LOG_LEVEL`, `PROMETHEUS_PORT`, `PROMETHEUS_PREFIX`, `API_PORT` (Web-Viewer: `WEB_PORT`) |

## Fehlerbehebung

| Problem | Prüfen |
|---|---|
| Container startet nicht | Logs (siehe oben) |
| Keine Verbindung zum Zähler | IP und Port, `ping <MODBUS_HOST>`, Firewall |
| MQTT verbindet nicht | Broker erreichbar? Benutzer/Passwort? Bei TLS Zertifikatspfade |
| Mehr Details | `LOG_LEVEL=DEBUG` |

Fragen und Probleme als Issue im Repo melden.

## Lizenz

Laut bisherigem README Open Source und frei verwendbar; eine LICENSE-Datei fehlt noch.

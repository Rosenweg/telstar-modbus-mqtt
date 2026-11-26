<p align="center"><img src="docs/logo.png" width="96" alt="Logo"></p>
<h1 align="center">Rosenweg Telstar-Bridge</h1>
<p align="center">Liest den Stromzähler Telstar 80A (Smart-Me) per Modbus aus und stellt die Werte für Haussteuerung und Überwachung bereit.</p>
<p align="center"><a href="docs/schnittstellen.md">Schnittstellen</a> · <a href="docs/entwickeln.md">Für Entwickler</a></p>

## Was drin ist

- Liest Leistung, Spannung, Strom und Energie des Zählers alle paar Sekunden.
- Schickt die Werte per MQTT (auf Wunsch verschlüsselt) an den Broker.
- Liefert Prometheus-Metriken fürs Monitoring.
- Eine einfache REST-API, z.B. für Home Assistant oder Node-RED.
- Ein Web-Viewer zum Nachschauen und Fehlersuchen.

## Läuft auf

Docker (fertige Images auf ghcr.io).

## Entwickeln

Python (`modbus_mqtt_bridge.py`, Web-Viewer `modbus_web_debug.py`), Einstellungen über
Umgebungsvariablen. Konfiguration, Docker-Compose, Images und Fehlerbehebung stehen in
[docs/entwickeln.md](docs/entwickeln.md).

## Lizenz

Laut bisherigem README Open Source und frei verwendbar; eine LICENSE-Datei fehlt noch.

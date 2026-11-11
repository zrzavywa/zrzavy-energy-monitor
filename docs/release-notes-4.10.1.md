# Release 4.10.1

Veröffentlicht am 2026-11-11.

## Geändert

- Der Migrationspfad prüft die Quelldatenbank nur noch einmal statt drei Mal.
  Auf der Referenzinstallation (6,1 GB, USB) kostet ein vollständiger
  `PRAGMA integrity_check` rund eine Stunde; das Wartungsfenster schrumpft
  damit von mehreren Stunden auf gut eine.
- Nach einer rein additiven Migration genügt `PRAGMA quick_check`. Die
  Prüfung vor der Migration bleibt ein vollständiger Integritätslauf.

## Inhalt von 4.10.0 (unverändert enthalten)

- Erreichbarkeits-Zeitreihe je Gerät auf der Seite „Datenerfassung"
  (24 Stunden, 7 Tage, 30 Tage), Schema 3 mit `device_availability_hours`.
- `GET /api/devices/availability`, Backfill-Skript, Aufbewahrungskategorie
  `availability_days`.

## Installation

```bash
tar -xzf zrzavy-energy-monitor-4.10.1.tar.gz
sudo systemctl stop zrzavy-energy-monitor.service
sudo rsync -a --delete zrzavy-energy-monitor-4.10.1/ /opt/zrzavy-energy-monitor/releases/4.10.1/
sudo cp -a /opt/zrzavy-energy-monitor/releases/4.9.0/.venv /opt/zrzavy-energy-monitor/releases/4.10.1/.venv
sudo ln -sfn /opt/zrzavy-energy-monitor/releases/4.10.1 /opt/zrzavy-energy-monitor/current
sudo systemctl start zrzavy-energy-monitor.service
curl -s http://127.0.0.1:8787/api/health
```

Das Release-Archiv enthält kein `.venv`; die virtuelle Umgebung wird aus dem
vorherigen Release übernommen. Schema-Migration 2 → 3, `config_schema` bleibt 5.

**Full Changelog**: https://github.com/zrzavywa/zrzavy-energy-monitor/compare/v4.10.0...v4.10.1

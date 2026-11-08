# Release 4.8.1

Veröffentlicht am 2026-11-08.

## Behoben

- Die Update-Seite meldete einen alten Vorgang als Ergebnis der laufenden
  Installation. Auf der Referenzinstallation stand „Zrzavy Energy Monitor 4.5.5
  wurde erfolgreich installiert“, während oben korrekt 4.8.0 als installiert
  angezeigt wurde. Ursache war ein Statusdatensatz vom 29.07.2026: die
  Statusdatei wird nur vom privilegierten Updater geschrieben, manuelle
  Deployments lassen sie unverändert stehen.
- Ein solcher Datensatz erscheint jetzt als älterer Vorgang: Status mit Zusatz
  „älterer Vorgang“, Fortschritt und verifizierte Version als Gedankenstrich,
  dazu Datum, damals eingespielte Version und der Hinweis, dass die laufende
  Version nicht aus diesem Vorgang stammt. Die Erfolgsmeldung erscheint nur
  noch, wenn der Vorgang zur laufenden Version gehört.

## Geändert

- `/api/update/status` liefert zusätzlich `status_is_historic`. Die Ergänzung
  ist additiv; `installed_version` bleibt die laufende Version,
  `status_installed_version` die in der Datei gespeicherte.

## Installation

```bash
tar -xzf zrzavy-energy-monitor-4.8.1.tar.gz
sudo systemctl stop zrzavy-energy-monitor.service
sudo rsync -a --delete zrzavy-energy-monitor-4.8.1/ /opt/zrzavy-energy-monitor/releases/4.8.1/
sudo cp -a /opt/zrzavy-energy-monitor/releases/4.8.0/.venv /opt/zrzavy-energy-monitor/releases/4.8.1/.venv
sudo ln -sfn /opt/zrzavy-energy-monitor/releases/4.8.1 /opt/zrzavy-energy-monitor/current
sudo systemctl start zrzavy-energy-monitor.service
curl -s http://127.0.0.1:8787/api/health
```

Das Release-Archiv enthält kein `.venv`; die virtuelle Umgebung wird aus dem
vorherigen Release übernommen. Kein Schemawechsel, keine Migration,
`config_schema` bleibt 5.

**Full Changelog**: https://github.com/zrzavywa/zrzavy-energy-monitor/compare/v4.8.0...v4.8.1

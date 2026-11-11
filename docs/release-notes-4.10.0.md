# Release 4.10.0

Veröffentlicht am 2026-11-11.

## Neu

- Die Seite „Datenerfassung" zeigt je konfiguriertem Gerät eine
  Erreichbarkeits-Zeitreihe für 24 Stunden, 7 Tage und 30 Tage. Ein Balken
  entspricht einer Stunde; graue Abschnitte bedeuten, dass der Sammler in
  dieser Stunde nichts geschrieben hat.
- Der Collector schreibt je Zyklus und gelesenem Gerät einen Zähler in die
  neue Tabelle `device_availability_hours`. Sie wächst mit Stunden, nicht mit
  Messzyklen, und überlebt die Aufbewahrungsfrist der Rohdaten.
- Neuer Endpunkt `GET /api/devices/availability`.
- `scripts/backfill-availability.py` leitet die Historie einmalig aus
  vorhandenen Messzeilen ab und überschreibt keine erfassten Stunden.

## Geändert

- `degraded` gilt als erreichbar; der Anteil erscheint getrennt als
  „mit Einschränkung". Ein dauerhaft diagnostizierendes Gerät wird damit
  nicht als Dauerausfall dargestellt.

## Betriebshinweis: Schema-Migration

Dieses Release migriert das Datenbankschema von 2 auf 3. Vor der Migration
erstellt die Anwendung automatisch ein verifiziertes Vollbackup unter
`/var/lib/zrzavy-energy-monitor/backups`. Daraus folgen drei Punkte:

1. Auf dem Daten-Datenträger muss freier Platz in Größe der Datenbank
   vorhanden sein, sonst startet die Anwendung nicht.
2. Der erste Start dauert länger (Backup, Integritätsprüfung, Migration).
3. Ein Zurückschalten auf 4.9.0 genügt nicht: Der ältere Stand verweigert
   eine Datenbank mit Schema 3. Ein Rollback erfordert zusätzlich das
   Zurückkopieren des Backups.

## Optional: Historie nachladen

Die Zeitreihe beginnt mit dem Update. Vorhandene Messzeilen lassen sich
einmalig nachladen; der Befehl zählt ohne `--apply` nur und schreibt nichts:

```bash
sudo /opt/zrzavy-energy-monitor/current/.venv/bin/python \
  /opt/zrzavy-energy-monitor/current/scripts/backfill-availability.py --days 30
sudo /opt/zrzavy-energy-monitor/current/.venv/bin/python \
  /opt/zrzavy-energy-monitor/current/scripts/backfill-availability.py --days 30 --apply
```

Abgeleitete Stunden tragen `origin=derived`; der Endpunkt weist sie als
`coverage: "derived"` aus. Der Nachladebefehl ist idempotent.

## Installation

```bash
tar -xzf zrzavy-energy-monitor-4.10.0.tar.gz
sudo systemctl stop zrzavy-energy-monitor.service
sudo rsync -a --delete zrzavy-energy-monitor-4.10.0/ /opt/zrzavy-energy-monitor/releases/4.10.0/
sudo cp -a /opt/zrzavy-energy-monitor/releases/4.9.0/.venv /opt/zrzavy-energy-monitor/releases/4.10.0/.venv
sudo ln -sfn /opt/zrzavy-energy-monitor/releases/4.10.0 /opt/zrzavy-energy-monitor/current
sudo systemctl start zrzavy-energy-monitor.service
curl -s http://127.0.0.1:8787/api/health
```

Das Release-Archiv enthält kein `.venv`; die virtuelle Umgebung wird aus dem
vorherigen Release übernommen. `config_schema` bleibt 5.

**Full Changelog**: https://github.com/zrzavywa/zrzavy-energy-monitor/compare/v4.9.0...v4.10.0

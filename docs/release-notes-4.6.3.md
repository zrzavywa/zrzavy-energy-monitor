# Release 4.6.3

Veröffentlicht am 2026-11-07. Fehlerbehebungen auf 4.6.1.

## Behoben

- Die Aufbewahrungsbefehle `--retention-dry-run` und `--apply-retention`
  laufen nicht mehr durch die allgemeine Schema- und Integritätsprüfung.
  Auf der Referenzdatenbank mit 6 GB hätte der Dry Run zuvor eine
  vollständige `integrity_check` ausgelöst und minutenlang nichts
  ausgegeben. Er braucht jetzt nur die Zählabfragen.

- Zählung und Löschung abhängiger Zeilen laufen über einen Join statt über
  eine IN-Unterabfrage: 0,9 s statt 13,3 s pro Tabelle bei 181 226
  abgelaufenen Zeilen (gemessen auf der Referenzdatenbank).

## Inhalt von 4.6.1

- Phasenverlauf in der Jahresansicht (Monatsmittel, 9,7 s statt 39,1 s).
- Aufbewahrung für Rohdaten mit Dry Run.
- Tag, Woche und Monat aktualisieren sich alle 15 s ohne Abblendung.
- Die Update-Anzeige meldet die laufende Version.

## Installation

```bash
tar -xzf zrzavy-energy-monitor-4.6.3.tar.gz
sudo systemctl stop zrzavy-energy-monitor.service
sudo rsync -a --delete zrzavy-energy-monitor-4.6.3/ /opt/zrzavy-energy-monitor/releases/4.6.3/
sudo cp -a /opt/zrzavy-energy-monitor/releases/4.6.2/.venv /opt/zrzavy-energy-monitor/releases/4.6.3/.venv
sudo ln -sfn /opt/zrzavy-energy-monitor/releases/4.6.3 /opt/zrzavy-energy-monitor/current
sudo systemctl start zrzavy-energy-monitor.service
curl -s http://127.0.0.1:8787/api/health
```

Das Release-Archiv enthält kein `.venv`; die virtuelle Umgebung wird aus dem
vorherigen Release übernommen. Kein Schemawechsel: `config_schema` bleibt 5,
die Datenbankschema-Version bleibt 2.
# Release 4.6.1

Veröffentlicht am 2026-11-07. Enthält die Verbesserungen, die nach der
Veröffentlichung von 4.6.0 entstanden sind, sowie zwei neue Befehle für den
Betrieb.

## Neu

- **Phasenverlauf in der Jahresansicht.** Die API aggregiert für `period=year`
  je lokalem Kalendermonat. Zwölf Monatsmittel der Momentanleistung statt bis
  zu 8 760 Stundenzeilen: auf der Referenzinstallation 9,7 s statt 39,1 s.
  Die Werte sind Monatsmittel der Momentanleistung, keine Monatsenergie.
- **Aufbewahrung für Rohdaten.** `--retention-dry-run` zählt, wie viele Zeilen
  eine Frist löschen würde, `--apply-retention` löscht sie in einer
  Transaktion samt abhängiger Tabellen. Standard sind 730 Tage.

## Verbessert

- Tag, Woche und Monat aktualisieren sich alle 15 s selbst, ohne die Panels
  abzublenden. Neben dem Periodentitel steht der Zeitpunkt der letzten
  Aktualisierung.
- Die Jahresansicht lädt den Phasenverlauf mit.

## Behoben

- Die Update-Anzeige zeigt die laufende Version. Zuvor blieb
  `installed_version` in `update-status.json` auf dem Stand des letzten
  Updater-Laufs, auch wenn das Release anders installiert wurde.

## Installation

```bash
tar -xzf zrzavy-energy-monitor-4.6.1.tar.gz
sudo systemctl stop zrzavy-energy-monitor.service
sudo rsync -a --delete zrzavy-energy-monitor-4.6.1/ /opt/zrzavy-energy-monitor/releases/4.6.1/
sudo ln -sfn /opt/zrzavy-energy-monitor/releases/4.6.1 /opt/zrzavy-energy-monitor/current
sudo systemctl start zrzavy-energy-monitor.service
curl -s http://127.0.0.1:8787/api/health
```

Kein Schemawechsel: `config_schema` bleibt 5, die Datenbankschema-Version
bleibt 2.

## Prüfsumme

Die SHA-256-Prüfsumme steht in `zrzavy-energy-monitor-4.6.1.tar.gz.sha256`.
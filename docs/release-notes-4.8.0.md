# Release 4.8.0

Veröffentlicht am 2026-11-08.

Diese Version fasst alles seit 4.6.4 zusammen. Die Zwischenstände 4.7.0 und
4.7.1 wurden auf der Referenzinstallation betrieben, aber nicht als
GitHub-Release veröffentlicht.

## Hinzugefügt

- Wertetabelle: Eigenverbrauchsquote und Autarkiegrad stehen jetzt für jede
  Zeile des gewählten Zeitraums, nicht nur als Kennzahl über den gesamten
  Zeitraum. Beide Werte erscheinen auch im Ausdruck, in der Tabelle je Zeile
  und in der Kennzahlenzeile.
- Ist der Nenner einer Quote `0` oder liegt für die Zeile keine einzige Messung
  vor, zeigt die Zelle einen Gedankenstrich statt `0 %`. Die kWh-Spalten
  behalten ihre Nullsummen.
- Schaltfläche **Drucken** (4.7.0): Die gewählte Periode wird als druckfertige
  Seite ausgegeben — mit Periodentitel, Energie-Diagramm als vorab gerendertem
  Bild, vollständiger Wertetabelle und Kennzahlenzeile. Live-, Bilanz-,
  Validierungs-, Zähler-, Phasen- und Solakon-Panels bleiben dem Bildschirm
  vorbehalten.
- Datenstand („Stand“) und Erzeugungszeitpunkt („Ausdruck“) sind im Ausdruck
  getrennt, damit ein später gedruckter Bericht kein frischeres Datum
  vortäuscht.

## Geändert

- Die Summenzeile der Wertetabelle zeigt den Quotienten der Summen, nicht die
  Summe der Zeilenquoten. Sie stimmt damit mit den Kennzahlen überein.
- `/api/dashboard` liefert zusätzlich die Serien `self_consumption_pct`,
  `autarky_pct` und `sample_count` je Bucket. Die Ergänzung ist additiv, ohne
  zusätzliche Datenbankabfrage und ohne Schemaänderung; die Antwortzeiten
  bleiben unverändert.
- Der Ausdruck verteilt acht Spalten über feste Breiten und trennt lange
  Spaltenköpfe an Silbengrenzen. Die neuen Spalten können dadurch nicht über
  den Papierrand laufen.

## Behoben

- Der Ausdruck zeigte kein Diagramm (4.7.1). Das Druckbild wird jetzt zusammen
  mit den Daten vorbereitet; fehlt es, druckt die Seite ersatzweise das Canvas.
- Die Wertetabelle lief rechts über die Seite und wurde am Papierrand
  abgeschnitten (4.7.1), sobald die Systemschrift breitere Zeichen lieferte.

## Installation

```bash
tar -xzf zrzavy-energy-monitor-4.8.0.tar.gz
sudo systemctl stop zrzavy-energy-monitor.service
sudo rsync -a --delete zrzavy-energy-monitor-4.8.0/ /opt/zrzavy-energy-monitor/releases/4.8.0/
sudo cp -a /opt/zrzavy-energy-monitor/releases/<vorherige Version>/.venv /opt/zrzavy-energy-monitor/releases/4.8.0/.venv
sudo ln -sfn /opt/zrzavy-energy-monitor/releases/4.8.0 /opt/zrzavy-energy-monitor/current
sudo systemctl start zrzavy-energy-monitor.service
curl -s http://127.0.0.1:8787/api/health
```

Das Release-Archiv enthält kein `.venv`; die virtuelle Umgebung wird aus dem
vorherigen Release übernommen. Kein Schemawechsel, keine Migration,
`config_schema` bleibt 5.

**Referenzinstallation:** am 2026-11-08 auf 4.8.0 umgestellt, Healthcheck
`status=ok`, `version=4.8.0`, `database=ok`; Antwortzeiten warm Tag 0,07 s,
Woche 0,31 s, Monat 0,36 s, Jahr 7,0 s.

**Full Changelog**: https://github.com/zrzavywa/zrzavy-energy-monitor/compare/v4.6.4...v4.8.0

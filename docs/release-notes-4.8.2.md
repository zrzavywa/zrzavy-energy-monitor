# Release 4.8.2

Veröffentlicht am 2026-11-08.

## Geändert

- Die Release-Notes auf der Update-Seite werden als Formatierung dargestellt
  statt als Rohtext: Überschriften, Aufzählungen, Inline-Code und Codeblöcke.
  Die Notes stammen aus einem GitHub-Release und gelten als nicht
  vertrauenswürdig. Die Seite baut deshalb ausschließlich DOM-Knoten mit
  `textContent`, ohne `innerHTML`, und macht nur `https`-Adressen zu Links.
- Hart umbrochene Notes bleiben in einem Aufzählungspunkt, Codeblöcke behalten
  ihre Zeilen. Der Container der Notes ist ein `div` statt `pre`, weil ein
  `pre` keine Überschriften und Listen halten kann.

## Behoben

- Ohne Statusdatei meldete `/api/update/status` `status_is_historic: true`,
  weil die fehlende gespeicherte Version als abweichende Version galt. Es gibt
  dann keinen Vorgang; das Feld ist jetzt `false`.

## Betriebshinweis

Die Statusdatei wird nur vom privilegierten Updater geschrieben. Nach einem
manuell eingespielten Release beschreibt sie einen früheren Vorgang. Für eine
leere Statusanzeige den Altstand archivieren statt löschen:

```bash
sudo mv /var/lib/zrzavy-energy-monitor/update-status.json \
        /var/lib/zrzavy-energy-monitor/update-status.json.stale-<datum>
```

## Installation

```bash
tar -xzf zrzavy-energy-monitor-4.8.2.tar.gz
sudo systemctl stop zrzavy-energy-monitor.service
sudo rsync -a --delete zrzavy-energy-monitor-4.8.2/ /opt/zrzavy-energy-monitor/releases/4.8.2/
sudo cp -a /opt/zrzavy-energy-monitor/releases/4.8.1/.venv /opt/zrzavy-energy-monitor/releases/4.8.2/.venv
sudo ln -sfn /opt/zrzavy-energy-monitor/releases/4.8.2 /opt/zrzavy-energy-monitor/current
sudo systemctl start zrzavy-energy-monitor.service
curl -s http://127.0.0.1:8787/api/health
```

Das Release-Archiv enthält kein `.venv`; die virtuelle Umgebung wird aus dem
vorherigen Release übernommen. Kein Schemawechsel, keine Migration,
`config_schema` bleibt 5.

**Full Changelog**: https://github.com/zrzavywa/zrzavy-energy-monitor/compare/v4.8.1...v4.8.2

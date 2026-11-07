# Release 4.6.4

Veröffentlicht am 2026-11-07.

## Geändert

- Tag, Woche und Monat aktualisieren sich im 60-Sekunden-Takt statt alle
  15 Sekunden. Der Sammler schreibt eine Messung pro Minute; häufigeres
  Neuladen zeigte viermal denselben Wert.

## Installation

```bash
tar -xzf zrzavy-energy-monitor-4.6.4.tar.gz
sudo systemctl stop zrzavy-energy-monitor.service
sudo rsync -a --delete zrzavy-energy-monitor-4.6.4/ /opt/zrzavy-energy-monitor/releases/4.6.4/
sudo cp -a /opt/zrzavy-energy-monitor/releases/4.6.3/.venv /opt/zrzavy-energy-monitor/releases/4.6.4/.venv
sudo ln -sfn /opt/zrzavy-energy-monitor/releases/4.6.4 /opt/zrzavy-energy-monitor/current
sudo systemctl start zrzavy-energy-monitor.service
curl -s http://127.0.0.1:8787/api/health
```

Das Release-Archiv enthält kein `.venv`; die virtuelle Umgebung wird aus dem
vorherigen Release übernommen. Kein Schemawechsel.
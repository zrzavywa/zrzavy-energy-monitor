# Release 4.9.0

Veröffentlicht am 2026-11-11.

## Geändert

- Die Gerätekarten unter „Konfigurierte Geräte" auf der Seite „Datenerfassung"
  werden aus der Konfiguration erzeugt statt im Template fest verdrahtet.
  Damit erscheint der offizielle Netzstromzähler als eigene Karte — mit
  Adapter, Protokoll, Port und Host aus seiner Konfiguration. Bisher fehlte er
  in der Oberfläche, obwohl er als Netzreferenz Vorrang hat.
- Jede Karte zeigt ihren Zustand dreistufig: „aktiv", „Host fehlt" und
  „inaktiv". Eine aktivierte Quelle ohne Adresse ist damit von einer bewusst
  abgeschalteten unterscheidbar.
- Ist die Anlagenmessung (Shelly Plug M) aktiv, ersetzt ihre Karte die
  Shelly-AC-Erzeugungskarte — also die Quelle, die der Collector tatsächlich
  abfragt.

## Behoben

- Die Beschriftungen der Auswahl `general.grid_power_source` nannten den
  offiziellen Netzstromzähler nicht, obwohl er bei gültigen Werten immer
  Vorrang hat. Sie benennen ihn jetzt und kennzeichnen Hausmessung und
  Solakon-Meter ausdrücklich als Fallback.

## Betriebshinweis

Der Netzstromzähler wird nur angezeigt, wenn `grid_meter.enabled` gesetzt und
ein Host eingetragen ist. Die Karte liest die Konfiguration, sie fragt das
Gerät nicht ab.

## Installation

```bash
tar -xzf zrzavy-energy-monitor-4.9.0.tar.gz
sudo systemctl stop zrzavy-energy-monitor.service
sudo rsync -a --delete zrzavy-energy-monitor-4.9.0/ /opt/zrzavy-energy-monitor/releases/4.9.0/
sudo cp -a /opt/zrzavy-energy-monitor/releases/4.8.2/.venv /opt/zrzavy-energy-monitor/releases/4.9.0/.venv
sudo ln -sfn /opt/zrzavy-energy-monitor/releases/4.9.0 /opt/zrzavy-energy-monitor/current
sudo systemctl start zrzavy-energy-monitor.service
curl -s http://127.0.0.1:8787/api/health
```

Das Release-Archiv enthält kein `.venv`; die virtuelle Umgebung wird aus dem
vorherigen Release übernommen. Kein Schemawechsel, keine Migration,
`config_schema` bleibt 5.

**Full Changelog**: https://github.com/zrzavywa/zrzavy-energy-monitor/compare/v4.8.2...v4.9.0

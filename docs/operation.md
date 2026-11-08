# Betriebshandbuch

## Service verwalten

Status:

```bash
sudo systemctl status zrzavy-energy-monitor.service
```

Start:

```bash
sudo systemctl start zrzavy-energy-monitor.service
```

Stopp:

```bash
sudo systemctl stop zrzavy-energy-monitor.service
```

Neustart:

```bash
sudo systemctl restart zrzavy-energy-monitor.service
```

Autostart prüfen:

```bash
systemctl is-enabled zrzavy-energy-monitor.service
```

## Logs anzeigen

Letzte Meldungen:

```bash
journalctl -u zrzavy-energy-monitor.service -n 100 --no-pager
```

Live-Ansicht:

```bash
journalctl -u zrzavy-energy-monitor.service -f
```

Seit dem letzten Systemstart:

```bash
journalctl -u zrzavy-energy-monitor.service -b
```

Updater:

```bash
journalctl -u zrzavy-energy-monitor-updater.service -n 200 --no-pager
```

Vor der Veröffentlichung von Logs Zugangsdaten, interne Adressen und Seriennummern entfernen.

## Healthcheck

```bash
curl --fail --silent --show-error \
  http://127.0.0.1:8787/api/health
```

Der Kern-Healthcheck soll den Zustand der Anwendung, nicht die permanente Erreichbarkeit aller externen Messgeräte bewerten. Ein ausgeschalteter Shelly darf daher als Warnung erscheinen, ohne automatisch ein Release-Rollback auszulösen.

## Installierte Version

```bash
cat /opt/zrzavy-energy-monitor/current/VERSION
readlink -f /opt/zrzavy-energy-monitor/current
```

Alternativ über die API:

```bash
curl --silent http://127.0.0.1:8787/api/system/version
```

## Wichtige Pfade

| Inhalt | Referenzpfad |
|---|---|
| aktives Release | `/opt/zrzavy-energy-monitor/current` |
| versionierte Releases | `/opt/zrzavy-energy-monitor/releases/` |
| Konfiguration | `/etc/zrzavy-energy-monitor/config.json` |
| SQLite-Datenbank | `/var/lib/zrzavy-energy-monitor/data/zrzavy-energy-monitor.db` |
| Update-Status | `/var/lib/zrzavy-energy-monitor/update-status.json` |
| Update-Anforderung | `/var/lib/zrzavy-energy-monitor/update-request.json` |
| Backups | `/var/lib/zrzavy-energy-monitor/backups/` |
| Update-Downloads | `/var/cache/zrzavy-energy-monitor/updates/` |
| Updater-Logs | `/var/log/zrzavy-energy-monitor/` |

Bei älteren Installationen können Konfiguration und Daten noch direkt im Anwendungsordner liegen.

## Manuelles Backup

Anwendung für eine konsistente Sicherung stoppen:

```bash
sudo systemctl stop zrzavy-energy-monitor.service
```

Backup erstellen:

```bash
BACKUP="$HOME/zrzavy-energy-monitor-$(date +%Y%m%d-%H%M%S).tar.gz"

sudo tar -czf "$BACKUP" \
  /etc/zrzavy-energy-monitor \
  /var/lib/zrzavy-energy-monitor/data \
  /var/lib/zrzavy-energy-monitor/update-status.json 2>/dev/null || true

sudo chown "$USER":"$USER" "$BACKUP"
```

Danach:

```bash
sudo systemctl start zrzavy-energy-monitor.service
```

Backup prüfen:

```bash
tar -tzf "$BACKUP"
```

Ein Backup ist erst dann vertrauenswürdig, wenn seine Wiederherstellung mindestens einmal getestet wurde.

## SQLite-Datenbank prüfen

Integrität:

```bash
sqlite3 /var/lib/zrzavy-energy-monitor/data/zrzavy-energy-monitor.db \
  "PRAGMA integrity_check;"
```

Erwartete Ausgabe:

```text
ok
```

Dateigröße:

```bash
du -h /var/lib/zrzavy-energy-monitor/data/zrzavy-energy-monitor.db
```

Vor direkten SQL-Änderungen immer ein Backup erstellen. Die Datenbank sollte normalerweise ausschließlich durch Zrzavy Energy Monitor verwaltet werden.

## Dateirechte prüfen

```bash
sudo stat /etc/zrzavy-energy-monitor/config.json
sudo stat /var/lib/zrzavy-energy-monitor/data/zrzavy-energy-monitor.db
sudo namei -l /opt/zrzavy-energy-monitor/current/app/config.json
sudo namei -l /opt/zrzavy-energy-monitor/current/app/data
```

Der Zrzavy-Energy-Monitor-Service-Benutzer benötigt:

- Leserechte auf Programmdateien,
- Leserechte auf die Konfiguration,
- Schreibrechte auf Datenbank und Laufzeitdaten,
- keine allgemeinen Root-Rechte.

## Speicherplatz kontrollieren

```bash
df -h /
du -sh /opt/zrzavy-energy-monitor
du -sh /var/lib/zrzavy-energy-monitor
du -sh /var/cache/zrzavy-energy-monitor
```

Alte Release-Downloads im Cache können nach erfolgreicher Sicherung und Prüfung entfernt werden. Das aktive Release, das unmittelbar vorherige Release und mindestens ein funktionierendes Backup sollten erhalten bleiben.

## Wartungsfenster für die Datenbank

Ein `VACUUM` schreibt die Datenbank vollständig neu und braucht während der
Laufzeit exklusiven Zugriff: Der Dienst muss stehen. Auf der Referenzinstallation
liegt die Datenbank mit rund 6 GB auf einem USB-Datenträger mit etwa 4–10 MB/s
Schreibrate. Dort dauerte allein das Kopieren der Datei rund zehn Minuten, und
eine vollständige `PRAGMA quick_check`-Prüfung der Sicherung war nach 25 Minuten
noch nicht abgeschlossen. Ein zweiter Versuch am 2026-11-07 brauchte für
dieselbe Prüfung über 48 Minuten; der Prozess verbrauchte in dieser Zeit nur
1:10 min CPU-Zeit, also praktisch nur I/O-Wartezeit. Rechne für eine
6-GB-Datenbank mit 60 bis 90 Minuten pro vollständigem Prüflauf.

Daraus folgt für Wartungsarbeiten:

- Fenster von mindestens 60 bis 120 Minuten einplanen, nicht von Minuten.
- Lange Schritte abgekoppelt starten (`setsid nohup … > /var/log/… 2>&1 &`) und
  über eine Logdatei verfolgen. Eine abreißende SSH-Verbindung darf die Wartung
  weder beenden noch den Dienst gestoppt zurücklassen.
- Die Sicherung zunächst ohne Dienstunterbrechung prüfen: Die Kopie ist
  unabhängig von der laufenden Instanz lesbar, ein `quick_check` darauf braucht
  also kein Wartungsfenster.
- Nach jedem Schritt prüfen, ob Dienst und Healthcheck wieder antworten; bei
  Überschreitung des Fensters abbrechen und den Dienst zuerst starten.
- Ein Abbruch vor dem `VACUUM` verändert die Datenbank nicht. Ein
  Aufbewahrungs- oder Aufräumschritt ist erst wirksam, wenn das `VACUUM`
  anschließend läuft.

## Aufbewahrung und Aufräumen der Rohdaten

Die Rohdatenbank wächst mit jedem Messintervall. Seit 4.6.1 gibt es dafür
einen Befehl, der ausschließlich Datenbankarbeit leistet und weder Webserver
noch Collector startet:

```bash
# Nur zählen, nichts löschen
python app/database_cli.py --retention-dry-run --keep-raw-days 730

# Löschen; läuft in einer Transaktion mit aktiven Fremdschlüsseln
python app/database_cli.py --apply-retention --keep-raw-days 730
```

- `--keep-raw-days` legt fest, wie viele Tage Rohdaten erhalten bleiben
  (Standard 730, also 24 Monate).
- Gelöscht werden Samples vor der Grenze und alle abhängigen Zeilen in
  `phase_samples`, `grid_meter_samples`, `validation_events`,
  `energy_balance_samples`, `measurements` und `source_selection_events`.
  Fehlt eine abhängige Tabelle im Schema, bricht die Transaktion ab, statt
  Waisen zurückzulassen.
- Der Dateiplatz wird erst durch ein anschließendes `VACUUM` frei; vorher
  bleibt die Datei gleich groß.
- Vorher eine geprüfte Sicherung erstellen (`--backup-database`) und das
  Ergebnis des Dry Run notieren.
- **Bewusst kein Automatiklauf.** Am 2026-11-07 wurde entschieden, die
  Aufbewahrung nur von Hand im Wartungsfenster auszuführen; es gibt keinen
  Zeitplan und keinen Hintergrunddienst dafür. Wer das ändern will, braucht
  eine eigene Freigabe.

Restobjekte aus einer Reparatur (`lost_and_found`) gehören nicht zum
Anwendungsbestand. Sie lassen sich im Wartungsfenster mit `DROP TABLE
lost_and_found` entfernen; wirksam wird der gewonnene Platz ebenfalls erst
nach dem `VACUUM`.

## Abgebrochener Wartungsversuch am 2026-11-07

Fenster 16:13–17:01 UTC: Dienst gestoppt, `quick_check` der 6,3-GB-Sicherung
gestartet. Nach 48 Minuten war die Prüfung noch nicht fertig; währenddessen
startete der Host neu. Der Dienst kam beim Booten automatisch wieder hoch.

- Ursache des Neustarts: unbekannt. Kein OOM, kein Undervoltage-Flag nach dem
  Boot, keine Abschaltmeldung im Journal des vorherigen Boots. Auffällig ist
  nur die Korrelation mit dauerhafter, schwerer Datenträgerlast.
- Ergebnis: Datenbank unverändert. `lost_and_found` (120 565 Zeilen) ist
  weiterhin vorhanden, es wurde keine Zeile gelöscht und kein `VACUUM`
  gestartet.
- Messlücke: 17:13:19 bis 18:01:38 lokal, also 48,3 Minuten.
- Konsequenz: Aufräumen ohne Platzdruck ist den Ausfall nicht wert; 42 GB sind
  frei. Ein `VACUUM` würde ein Mehrfaches der Prüfzeit brauchen. Wenn der Platz
  gebraucht wird, zuerst Netzteil und Datenträger stabilisieren und ein
  Fenster von mehreren Stunden einplanen.

## Release einspielen

1. Archiv prüfen: `sha256sum -c zrzavy-energy-monitor-<version>.tar.gz.sha256`.
2. Dienst stoppen.
3. Archiv nach `/opt/zrzavy-energy-monitor/releases/<version>/` entpacken.
4. **`.venv` aus dem laufenden Release übernehmen:**
   `cp -a /opt/zrzavy-energy-monitor/releases/<alt>/.venv releases/<version>/.venv`.
   Das Archiv enthält keine virtuelle Umgebung; ohne diesen Schritt startet
   der Dienst nicht (`status=203/EXEC`). Am 2026-11-07 ist genau das passiert.
5. `current`-Symlink umschalten, Dienst starten
6. Healthcheck prüfen: `status`, `version` und `database` müssen stimmen und die
   Version muss der neuen entsprechen.

Bei Fehlschlag genügt es, den Symlink auf das vorherige Release zurückzusetzen
und den Dienst neu zu starten; die Datenbank bleibt unberührt.

## Regelmäßige Betriebsprüfung

Empfohlen mindestens monatlich:

- Service läuft und ist aktiviert.
- Healthcheck antwortet.
- Gerätewerte sind aktuell.
- Systemzeit stimmt.
- Datenbankintegrität ist `ok`.
- Freier Speicherplatz ist ausreichend.
- Backup ist vorhanden.
- Update-Status enthält keinen dauerhaften Fehler.
- Raspberry Pi und Abhängigkeiten erhalten Sicherheitsupdates.

## Ausdruck der Periodenübersicht

Das Dashboard hat neben der Periodenauswahl die Schaltfläche **Drucken**. Sie
gibt die aktuell gewählte Periode (Tag, Woche, Monat, Jahr) so aus, wie sie
gerade angezeigt wird — mit den geladenen Zahlen, ohne neue Abfrage.

Gedruckt werden:

- Kopf mit Periodentitel, Datenstand und Erzeugungszeitpunkt,
- das Energie-Diagramm (Erzeugung, Hausverbrauch, Netzbezug, Einspeisung),
- die vollständige Wertetabelle des Zeitraums mit Summenzeile,
- die Kennzahlenzeile (Ertrag, Hausverbrauch, Netzbezug, Einspeisung,
  Eigenverbrauchsquote, Autarkiegrad).

Nicht gedruckt werden Live-Karten, Momentan-Energiebilanz,
Plausibilitätsprüfung, Netzstromzähler, Phasen- und Solakon-Panel sowie
Navigation und Seitenfuß.

**Zeitangaben:** „Stand“ ist der Zeitpunkt, an dem die angezeigten Zahlen
geladen wurden. „Ausdruck“ ist der Zeitpunkt des Druckbefehls. Bei einer
laufenden Periode liegen beide höchstens eine Minute auseinander; bei einer
abgeschlossenen Periode bleibt „Stand“ der ältere, ehrlichere Wert.

**Einstellungen im Browser (Chrome):**

1. „Hintergrundgrafiken“ aktivieren, sonst drucken Legende, Balken und die
   hervorgehobenen Kennzahlen ohne Farbe.
2. „Kopf- und Fußzeilen“ deaktivieren, sonst erscheinen URL und Datum des
   Browsers am Seitenrand.
3. Für ein PDF „Als PDF speichern“ als Ziel wählen; der Text bleibt auswählbar.

Der Ausdruck umfasst je nach Periode etwa eine Seite (Tag, Woche, Jahr) oder
zwei Seiten (Monat: 31 Tabellenzeilen). Seitenzahlen druckt nur der Browser
selbst, nicht die Anwendung.

## Dokument-Change-Log

- 2026-11-08 — Abschnitt „Ausdruck der Periodenübersicht“ mit Druckumfang, Zeitangaben und Chrome-Einstellungen ergänzt; Anlass/Quelle: Betreiberanforderung Druck der Periodenübersicht (4.7.0); Prüfstatus: Umsetzung und Tests abgeglichen, Sichtprüfung im Browser steht aus.
- 2026-11-07 — Abschnitte „Aufbewahrung und Aufräumen der Rohdaten“, „Abgebrochener Wartungsversuch am 2026-11-07“ und „Release einspielen“ ergänzt; Anlass/Quelle: Retention-Befehl ab 4.6.1, abgebrochenes Aufräumfenster und fehlende `.venv` beim Deployment von 4.6.1; Prüfstatus: Befehle auf der Referenzinstallation ausgeführt (Dry Run), Deployment-Schritte am 2026-11-07 zweimal durchlaufen.
- 2026-11-07 — Abschnitt „Wartungsfenster für die Datenbank" mit gemessenen Wartezeiten und Abbruchregeln ergänzt; Anlass/Quelle: Wartungsversuch auf der Referenzinstallation (6 GB, USB, `quick_check` > 25 min); Prüfstatus: Messwerte aus dem Betriebsprotokoll, Vorgehen angewandt und dokumentiert.

# Changelog

Alle wesentlichen Änderungen an Zrzavy Energy Monitor werden in dieser Datei dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/). Die Versionsnummern folgen nach Möglichkeit [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

Keine Änderungen.

## [4.8.2] — 2026-11-08

### Geändert

- Die Release-Notes auf der Update-Seite werden als Formatierung dargestellt
  statt als Rohtext: Überschriften, Aufzählungen, Inline-Code und Codeblöcke.
  Die Notes stammen aus einem GitHub-Release und gelten als nicht vertrauenswürdig;
  die Seite baut deshalb ausschließlich DOM-Knoten mit `textContent`, ohne
  `innerHTML`, und macht nur `https`-Adressen zu Links.
- Hart umbrochene Notes bleiben in einem Aufzählungspunkt, Codeblöcke behalten
  ihre Zeilen. Das Containerelement der Notes ist jetzt ein `div` statt `pre`,
  weil ein `pre` keine Überschriften und Listen halten kann.

### Behoben

- Ohne Statusdatei meldete `/api/update/status` `status_is_historic: true`,
  weil die fehlende gespeicherte Version als abweichende Version galt. Es gibt
  dann keinen Vorgang; das Feld ist jetzt `false`.

## [4.8.1] — 2026-11-08

### Behoben

- Die Update-Seite meldete einen alten Vorgang als Ergebnis der laufenden
  Installation: „Zrzavy Energy Monitor 4.5.5 wurde erfolgreich installiert“,
  während oben 4.8.0 als installiert stand. Ursache war ein Statusdatensatz vom
  29.07.2026, den manuelle Deployments nie fortschreiben. Die Seite zeigt einen
  solchen Datensatz jetzt als älteren Vorgang: Status mit Zusatz, Fortschritt
  und verifizierte Version als Gedankenstrich, dazu Datum, damals eingespielte
  Version und der Hinweis, dass die laufende Version nicht aus diesem Vorgang
  stammt. Die Erfolgsmeldung erscheint nur noch für die laufende Version.

### Geändert

- `/api/update/status` liefert zusätzlich `status_is_historic`. Die Ergänzung
  ist additiv; `installed_version` bleibt weiterhin die laufende Version.

## [4.8.0] — 2026-11-08

### Hinzugefügt

- Dashboard: Die Wertetabelle zeigt für jede Zeile des gewählten Zeitraums die
  Eigenverbrauchsquote und den Autarkiegrad in Prozent. Beide Werte stehen auch
  im Ausdruck, in der Tabelle je Zeile und in der Kennzahlenzeile.
- Ist der Nenner einer Quote `0` oder liegt für die Zeile keine einzige Messung
  vor, zeigt die Zelle einen Gedankenstrich statt `0 %`. Die kWh-Spalten
  behalten ihre Nullsummen.

### Geändert

- Die Summenzeile zeigt den Quotienten der Summen, nicht die Summe der
  Zeilenquoten. Der Tabellenuntertitel benennt diesen Unterschied.
- `/api/dashboard` liefert zusätzlich die Serien `self_consumption_pct`,
  `autarky_pct` und `sample_count` je Bucket. Die Ergänzung ist additiv und
  benötigt keine zusätzliche Datenbankabfrage und keine Schemaänderung.
- Der Ausdruck verteilt die acht Spalten über feste Breiten; die beiden neuen
  Spalten laufen dadurch nicht über den Papierrand.

## [4.7.1] — 2026-11-08

### Behoben

- Der Ausdruck zeigte kein Diagramm. Das Druckbild wird jetzt zusammen mit den
  Daten vorbereitet und nicht erst im `beforeprint`; ein Bild aus einer
  Daten-URL wird asynchron dekodiert und war in der Druckvorschau deshalb oft
  noch leer. Fehlt das Bild, druckt die Seite ersatzweise das Canvas.
- Die Wertetabelle lief rechts über die Seite und wurde am Papierrand
  abgeschnitten, sobald die Systemschrift breitere Zeichen lieferte. Die
  Tabelle hat jetzt feste Spaltenbreiten (`table-layout: fixed`), lange
  Spaltenköpfe umbrechen statt zu verbreitern. Die Kennzahlenzeile nutzt
  `minmax(0, 1fr)`, damit lange Beschriftungen das Raster nicht aufziehen.

## [4.7.0] — 2026-11-08

### Hinzugefügt

- Dashboard: Die Schaltfläche „Drucken“ gibt die gewählte Periode als
  druckfertige Seite aus. Gedruckt werden Periodentitel mit Datenstand, das
  Energie-Diagramm als vorab gerendertes Bild, die vollständige Wertetabelle
  mit Summenzeile und die Kennzahlenzeile. Live-, Bilanz-, Validierungs-,
  Zähler-, Phasen- und Solakon-Panels bleiben dem Bildschirm vorbehalten.
- Im Ausdruck stehen Datenstand („Stand“) und Erzeugungszeitpunkt
  („Ausdruck“) getrennt, damit ein später gedruckter Bericht kein frischeres
  Datum vortäuscht.

### Geändert

- Keine Änderung an der API: der Ausdruck nutzt die bereits gelieferten
  Felder von `/api/dashboard`.

## [4.6.4] — 2026-11-07

### Betrieb

- Referenzinstallation am 2026-11-07 auf 4.6.4 gehoben (`releases/4.6.4`,
  `.venv` aus 4.6.3 übernommen). Healthcheck `status=ok`, `version=4.6.4`,
  `database=ok`; Tag 0,06 s, Woche 0,32 s, Monat 0,36 s.
- Beim ersten Versuch mit 4.6.1 fehlte die `.venv` im Release-Verzeichnis, der
  Dienst startete nicht (`203/EXEC`); Rollback auf 4.6.0 per Symlink, danach
  `.venv` übernommen. Der Schritt steht jetzt in `docs/operation.md` unter
  „Release einspielen“.

### Geändert

- Tag, Woche und Monat aktualisieren sich im 60-Sekunden-Takt statt alle 15 s.
  Der Sammler schreibt eine Messung pro Minute; häufigeres Neuladen zeigte
  viermal denselben Wert.

## [4.6.3] — 2026-11-07

### Behoben

- Zählung und Löschung der abhängigen Zeilen laufen über einen Join auf
  `samples` statt über eine `IN`-Unterabfrage. Gemessen auf der
  Referenzdatenbank: 0,9 s statt 13,3 s pro Tabelle bei 181 226 abgelaufenen
  Zeilen, weil der Join den vorhandenen Index auf `sample_id` als
  Deckungsindex nutzt.

## [4.6.2] — 2026-11-07

### Behoben

- `--retention-dry-run` und `--apply-retention` laufen nicht mehr durch die
  allgemeine Schema- und Integritätsprüfung. Auf einer 6-GB-Datenbank hätte
  der Dry Run sonst eine vollständige `integrity_check` ausgelöst und
  minutenlang nichts ausgegeben; er braucht jetzt nur die Zählabfragen.

## [4.6.1] — 2026-11-07

### Hinzugefügt

- Aufbewahrung für Rohdaten: `python app/database_cli.py
  --retention-dry-run --keep-raw-days 730` zählt, `--apply-retention` löscht
  alte Samples und alle abhängigen Zeilen in einer Transaktion. Der Dry Run
  ist der Standardweg; der Dateiplatz wird erst durch ein anschließendes
  `VACUUM` frei.

- Phasenverlauf für die Jahresansicht: Die API aggregiert für `year` in SQL je
  lokalem Kalendermonat und liefert zwölf Monatsmittel der Momentanleistung
  statt bis zu 8 760 Stundenzeilen. Auf der Referenzinstallation brauchte die
  Abfrage vorher 39,1 s, jetzt 9,7 s (warm, drei Messungen). Ein schmaler
  Deckungsindex auf den Phasenspalten bringt weitere Verbesserung auf 5,9 s
  (gemessen an der Sicherungskopie, Indexaufbau 6,8 s), wurde aber nicht
  eingebaut: der Gewinn von rund 3,8 s rechtfertigt die zusätzliche
  Indexpflege auf dem Referenzgerät derzeit nicht.
- Tag, Woche und Monat aktualisieren sich alle 15 s selbst; ein Request
  kostet gemessen 0,36 s (Woche) bzw. 0,43 s (Monat) über das Netz. Die
  Jahresansicht lädt nicht automatisch, eine Ansicht in der Vergangenheit
  ebenso wenig. Automatische Aktualisierungen laufen ohne Ladeabblendung, die
  Panels bleiben also lesbar; neben dem Periodentitel steht der Zeitpunkt der
  letzten Aktualisierung.

### Behoben

- Die Update-Anzeige meldet die laufende Version statt der zuletzt vom
  Updater geschriebenen. Wird ein Release auf anderem Weg installiert, blieb
  `installed_version` in `update-status.json` veraltet (auf der
  Referenzinstallation monatelang `4.5.3`). Der laufende Stand gewinnt jetzt,
  der gespeicherte Wert bleibt als `status_installed_version` sichtbar.

### Betrieb

- Aufräumfenster am 2026-11-07 abgebrochen: Die `quick_check`-Prüfung der
  6,3-GB-Sicherung war nach 48 Minuten nicht fertig, währenddessen startete
  der Host neu. Datenbank unverändert, `lost_and_found` weiterhin vorhanden,
  kein `VACUUM` gelaufen, Messlücke 48,3 Minuten. Ursache des Neustarts
  unbekannt, dokumentiert in `docs/operation.md`.
- Der Release-Build (`scripts/build-release.sh`) nutzt `rsync`, wenn es
  vorhanden ist, und fällt sonst auf `tar` mit derselben Ausschlussliste
  zurück. Auf dem Build-Host fehlte `rsync`.
- Referenzinstallation am 2026-11-07 auf 4.6.0 gehoben: Release-Verzeichnis
  `releases/4.6.0` aus dem veröffentlichten Archiv, `current` umgeschaltet,
  Healthcheck meldet `version=4.6.0`. Gemessen danach Live 0,06 s, Tag 0,06 s,
  Woche 0,30 s, Monat 0,33 s, Jahr 7,09 s.
- Der Versuch, die Datenbank zu bereinigen, wurde im Wartungsfenster
  abgebrochen: Das Kopieren der 6 GB dauerte rund zehn Minuten, die
  anschließende `quick_check`-Prüfung der Sicherung war nach 25 Minuten nicht
  abgeschlossen. Der Dienst wurde wieder gestartet, die Datenbank ist
  unverändert (die Tabelle `lost_and_found` mit 120 565 Zeilen besteht
  weiterhin). Während des Fensters entstand eine Aufzeichnungslücke von rund
  55 Minuten. Ein neues Fenster braucht 60 bis 120 Minuten; das Vorgehen steht
  in `docs/operation.md`.
- Der Update-Status der Installation nennt weiterhin `installed_version: 4.5.3`,
  obwohl 4.6.0 läuft. Ursache ist der bekannte Updater-Statusfehler; die
  Anzeige ist damit unzuverlässig, die installierte Version nicht.

## [4.6.0] - 2026-11-07

### Behoben

- Die Live-Ansicht antwortete auf der Referenzinstallation rund 6 Sekunden.
  Ursache war die Abfrage des letzten Netzanschluss-Datensatzes: Sie sortierte
  alle 224 000 Detailzeilen über `samples.ts_epoch` (`SCAN` +
  `USE TEMP B-TREE FOR ORDER BY`, 5,7 s). Die Suche nach dem jeweils neuesten
  Detaildatensatz betrachtet jetzt nur die jüngsten 200 Messungen über
  `idx_samples_ts_epoch` und bleibt damit bei der Semantik „neuester
  Zeitstempel"; gemessen 0,001 s statt 5,66 s. Dieselbe Abfrageform gilt für
  Phasen- und Energiebilanz-Detailsätze.

### Hinzugefügt

- Dashboard: Zeitraumauswahl `Monat` mit einem Bucket je Kalendertag sowie
  eine Wertetabelle unter dem Diagramm, die Erzeugung, Hausverbrauch,
  Netzbezug, Einspeisung und Eigenverbrauch je Bucket und als Summe in kWh
  ausgibt. Damit sind die Zahlen ohne Ablesen des Diagramms verfügbar.

### Geändert

- Der reguläre Start einer bereits aktuellen Datenbank führt kein vollständiges
  PRAGMA integrity_check und keine Zeilenzählungen aus. Schema- und
  Versionsprüfung bleiben aktiv; Migrations- und explizite Wartungspfade
  behalten ihre vollständigen Integritäts- und Bestandsprüfungen.
- Dashboard-Aggregation läuft in SQLite: Die Historie wird je Stunde
  zusammengefasst und erst danach auf Tages-, Wochen-, Monats- oder
  Jahresbuckets verteilt, statt alle Rohzeilen zu laden. Auf dem
  Referenz-Raspberry-Pi sinkt die Jahresansicht dadurch von rund 148 auf
  wenige Sekunden; die Phasenauswertung nutzt denselben Pfad.
- Die Web-Oberfläche lädt Energie- und Phasenansicht parallel, aktualisiert
  den gewählten Zeitraum nicht mehr minütlich in der Jahresansicht und fragt
  den Phasenverlauf für die Jahresansicht nicht mehr ab.
- `app.css`, `dashboard.js` und `update.js` werden mit einem aus ihrem Inhalt
  berechneten Token ausgeliefert. Nach einem Update laden Browser die neuen
  Dateien selbstständig; ein manuelles Hartladen entfällt.

### Betrieb

- Referenzinstallation (Raspberry Pi OS), Stand 2026-11-07: Tag 0,06 s,
  Woche 0,27 s, Monat 0,34 s, Jahr 6,88 s, Live 0,06 s. Vor der
  Aggregationsumstellung lag die Jahresansicht bei 148 s und die Live-Ansicht
  bei 5,9 s. Sicherungen der Deployments liegen unter
  `/var/backups/zem-deploy-20261107-*`.

## [4.5.5] - 2026-07-29

### Behoben

- Phase 10C: Python 3.11+, portable SHA-256-Prüfung und importfreier Preflight.
- Release- und Migrationspfade verwenden die deklarierte Zielversion 4.5.5.
- Healthchecks akzeptieren ausschließlich `status=ok` und die exakte Release-Version.

## [4.5.4] - 2026-07-29

### Geändert

- SHRDZM-Adapter verarbeitet bestätigte UTC-Messzeiten, HTTP-200-Fehlerobjekte
  und fehlende Werte ohne erfundene Nullwerte.
- `1.8.0` und `2.8.0` werden nach Hardwarebestätigung bei
  `energy_total_unit=auto` als Wh normalisiert; Betreiberanzeigen in kWh
  ändern die interne Einheit nicht.

## [4.5.3] - 2026-07-29

### Hinzugefügt

- Shelly Plug M Gen3 als optionale, lokale und read-only Anlagen-AC-Quelle
  über `Switch.GetStatus` ergänzt.
- `apower = 0` bleibt ein gültiger Messwert; fehlende oder ungültige Werte
  fallen auf Solakon ONE zurück. Das Relais wird niemals geschaltet.
- Konfiguration, anonymisierte Fixture und Phase-10A-Nachweise ergänzt.

Die reale Hardwarecharakterisierung von Vorzeichen, Rückspeisung und
`ret_aenergy` ist vor der Releasefreigabe noch durchzuführen.

## [4.5.2] - 2026-07-27

### Behoben

- Update-Downloads behandeln Schreib-, API-, Antwort- und Prüffehler als
  konsistente JSON-Fehler und geben keine internen Pfade oder Stacktraces aus.
- Statusdateien werden auch beim ersten Schreibvorgang atomar geschrieben und
  temporäre Dateien nach Fehlern bereinigt.
- Bootstrap und systemd erlauben dem Dienstkonto den Zugriff auf State- und
  Update-Cachepfade, ohne bestehende Nutzdaten rekursiv umzubesitzen.
- Das Frontend prüft HTTP-Status und Content-Type vor dem JSON-Parsing und setzt
  fehlgeschlagene Downloads in einen terminalen Fehlerzustand.

Das direkte Upgrade von 4.5.0 bzw. 4.5.1 ist vorgesehen; bestehende Daten und
Konfigurationen bleiben erhalten. Tag und GitHub-Release werden separat erstellt.

## [4.5.1] - 2026-07-27

### Documentation

- Architekturübersicht für den implementierten 4.5-Stand um Adapterfactory,
  normalisierte Modelle, Validierung, Quellenauswahl, Energiebilanz,
  Zeitreihenpersistenz, Update-/Rollbackgrenzen und direkte Migration ergänzt.
- Lokale standardbibliotheksbasierte Dokumentationsqualitätsverträge für Links,
  Indizes, Versionen, Konfigurationsschlüssel, Architekturpfade und Mermaid-
  Struktur ergänzt.
- Betriebs-, Update-, Persistenz-, Collector-, Web- und Geräte-Schnittstellen
  im priorisierten WP-03-Scope mit englischen PEP-257-/Google-Docstrings
  ergänzt und durch einen AST-Vertragstest abgesichert.
- Die unversionierten HTTP-Schnittstellen von Version 4.5 vollständig nach
  Zielgruppe, Wirkung, Parametern, Antworten, Einheiten und Sicherheitsgrenzen
  dokumentiert und ihre Abdeckung an die registrierten Flask-Routen gebunden.
- Aktive Entwicklungsstandards auf den kanonischen Produktnamen und
  Core-Namespace ausgerichtet sowie Migration und historische
  4.5-Entwicklungsnachweise über zentrale Indizes erschlossen.

### Tests

- Dokumentations-, Docstring-, Versions- und Releasevertragstests für den
  Patch-Release konsistent und versionsdynamisch abgesichert.
- Der vollständige Docstring-Qualitätsvertrag weist 84/84 Module und 425/425
  öffentliche Symbole nach.

4.5.1 enthält keine beabsichtigte Änderung der Laufzeit-, Mess-, Validierungs-,
Persistenz-, Quellenauswahl-, Energiebilanz- oder Datenbankschema-Semantik.
Hardwarevalidierung ist nicht Bestandteil dieses Releasevorbereitungslaufs.

## [4.5.0] - 2026-07-27

### Changed

- Das Projekt wird ab Version 4.5.0 unter dem Namen **Zrzavy Energy Monitor**
  geführt. SolarInspector bleibt ausschließlich als dokumentierter früherer
  Projektname und in zeitlich begrenzter Upgrade-Kompatibilität erhalten.
- Das direkte Upgrade von SolarInspector 4.1.3 auf Zrzavy Energy Monitor 4.5.0
  sichert Installation, Konfiguration, SQLite-Datenbank, Messhistorie und
  Service-Dateien vor der kontrollierten Umschaltung.

### Added

- Kanonische Metadaten für Zrzavy Energy Monitor sowie neue
  `ZRZAVY_ENERGY_MONITOR_*`-Umgebungsvariablen mit priorisierten,
  wertgeschützten Legacy-Fallbacks ergänzt.
- Kanonischen Einstiegspunkt `zrzavy_energy_monitor.py` und Core-Namespace
  `zrzavy_energy_monitor_core` mit schmalen Legacy-Wrappern eingeführt.
- Kanonische Laufzeitpfade und Datei-Basenamen mit expliziter neuer
  Variablenpriorität, Legacy-Erkennung und rücksetzbarer Pfadauswahl ergänzt.
- Direkte, wiederholsichere 4.1.3-zu-4.5.0-Datenmigration mit schreibgeschütztem
  Dry Run, vollständigem Installationsbackup, atomarer SQLite-Kopie,
  Integritätsvergleich und geprüftem Rollback ergänzt.
- Release-Artefakte, Updater, Bootstrap-Installation und konfliktgesicherte
  systemd-Units auf Zrzavy Energy Monitor umgestellt; die Linux-Migration
  prüft den Healthcheck und rollt bei Fehlern auf den alten Dienst zurück.
- Weboberfläche, Laufzeitmeldungen und Exportdateinamen auf den vollständigen
  Produktnamen umgestellt sowie Health- und Versions-API um kanonische
  Produktmetadaten ergänzt.
- Versionierte Phase-10-Schema-Migrationen, normalisierte Messwert- und
  Quellenentscheidungs-Zeitreihen sowie begrenzte, indexgestützte
  Zeitbereichsabfragen ergänzt.
- Standardmäßig deaktivierte, konfigurierbare und transaktional begrenzte
  Zeitreihenaufbewahrung mit sicherem Rollback ergänzt.
- Additive, begrenzte CSV-Exporte für normalisierte Messwerte, Phasen,
  Grid-Meter, Energiebilanz und sichere Diagnoseereignisse ergänzt.
- Eigenständige Datenbank-CLI für read-only Diagnose, private SQLite-Backups,
  unveränderliche Dry Runs und backup-gesicherte Migrationen ergänzt.
- Datenbankschema-Prüfung und Pflicht-Backup-Migration vor Konstruktion von
  Collector und Webanwendung in den Startablauf integriert.
- Offizieller Netzstromzähler als priorisierte Messquelle mit gekennzeichnetem Fallback ergänzt.
- Read-only SHRDZM-REST-Adapter für `/getLastData` mit Query-, Basic- und optionaler Authentifizierung ergänzt.
- Adapterabhängige OBIS-Mappings, Einheitenkonvertierung und End-to-End-Tests ergänzt.
- Erklärbare Quellenauswahlmodelle und additive, rückwärtskompatible Konfiguration für die Phase-09-Energiebilanz ergänzt.
- Deterministische qualitäts-, rollen- und messpositionsbasierte Quellenauswahl mit transparenten Fallbackgründen ergänzt.
- Begrenzte Altersprüfung, zeitnächste Auswahl, optionale Kurzzeitmittelung und Source-Skew-Bewertung ergänzt.
- Validierte aktuelle Leistungsbilanz mit Hausleistung, getrennten Netzrichtungen, Toleranzbehandlung und diagnostischem Residualwert ergänzt.
- Eigenverbrauch, Eigenverbrauchsquote, Autarkiegrad sowie getrennte Batterieflüsse und SOC mit Widerspruchsfindings ergänzt.
- Source Selector und Energiebilanz additiv in jeden Collector-Zyklus integriert; Bilanzfehler stoppen die Messwerterfassung nicht.
- Additive atomare SQLite-Persistenz für Bilanzwerte, Qualität, Findings und optionale Quellenentscheidungen ergänzt.
- Herstellerunabhängige Live-API und Dashboard-Bereiche für aktuelle Energieflüsse, Kennzahlen, Quellen, Datenalter und Bilanzqualität ergänzt.
- Deterministische Replay-Szenarien für Phase-09-Normal-, Ausfall-, Zeit-, Ablehnungs- und Nullwertfälle ergänzt.

### Documentation

- Zentrale GitHub-Dokumentation mit Installations-, Konfigurations-, Betriebs-, Update-, Sicherheits-, Architektur- und API-Referenz ergänzt.
- Aktuellen Betrieb der 4.1-Reihe klar von der geplanten 5.0-Zielarchitektur getrennt.
- Zentrale Markenhinweise und Herstellerabgrenzung für Solakon, Shelly und Raspberry Pi ergänzt.
- Einrichtung, Sicherheit und Hardwarevalidierung des SHRDZM-Netzstromzählers dokumentiert.
- Vergleichsfenster, Mindestdauer und Mindestanzahl für Quellen mit
  zehnsekündigem Messintervall einschließlich robuster `60/30/4`-Empfehlung
  dokumentiert.

### Fixed

- Die gehärtete systemd-Unit erlaubt atomare Konfigurationsupdates im
  kanonischen Verzeichnis `/etc/zrzavy-energy-monitor`, während das übrige
  System durch `ProtectSystem=strict` schreibgeschützt bleibt.
- Der Debian-Rollback bewahrt fehlgeschlagene Zieldaten als Diagnosekopie,
  entfernt danach deren inaktive kanonische Pfade und ermöglicht eine erneute
  Migration mit einem frischen, unveränderlichen Backup.
- Die systemd-Orchestrierung stoppt vor dem Rollback beide Collector, führt
  Fehler-Rollbacks nur nach abgeschlossenem Daten-Apply aus und erzeugt bei
  privilegierten Läufen keine root-eigenen Bytecode-Caches im Repository.
- Quellenmessungen aus demselben Collector-Zyklus werden erst nach Abschluss
  der Geräteabfragen zeitlich bewertet und nicht mehr fälschlich als zukünftige
  Messwerte verworfen.

## [4.1.3] - 2026-07-20

### Fixed

- Download-Schaltfläche wird nach einer erfolgreichen Release-Prüfung zuverlässig aktiviert.
- Verarbeitung und Darstellung des OTA-Update-Status wurden korrigiert.
- Zustandslogik der Update-Oberfläche und Aktivierung der Installationsschaltfläche wurden gehärtet.
- Rekursive beziehungsweise zyklische Verknüpfungen virtueller Python-Umgebungen werden bei der Release-Vorbereitung verhindert.
- Persistente Pfade für Konfiguration und Datenbank bleiben bei Side-by-side-Updates erhalten.

### Changed

- Produktversion auf `4.1.3` angehoben.

## [4.1.2] - 2026-07-20

### Added

- Separater privilegierter Updater für Raspberry Pi und systemd.
- Side-by-side-Installation versionierter Releases.
- Persistenter Update-Status und Update-Anforderung.
- Backup von Konfiguration und SQLite-Datenbank vor der Aktivierung.
- Healthcheck mit automatischem Rollback.
- systemd-Path-Unit zum kontrollierten Start des Updaters.

### Security

- Webprozess und privilegierte Installation sind voneinander getrennt.
- Release-Artefakte werden vor der Aktivierung validiert.
- Allgemeine, vom Browser übergebene Shell-Befehle oder Downloadpfade werden nicht unterstützt.

## [4.1.1] - 2026-07-19

### Fixed

- Verbesserungen an Release-Erkennung, Download und Statusdarstellung.
- Robustere Behandlung fehlgeschlagener Update-Vorgänge.

## [4.1.0] - 2026-07-19

### Added

- GitHub-basierte Prüfung auf neue Releases.
- Anzeige von installierter und verfügbarer Version im Webinterface.
- Download und Prüfung veröffentlichter Release-Artefakte.
- API-Endpunkte für Version, Healthcheck und Update-Status.

### Changed

- Vorbereitung der Anwendung auf ein versioniertes Release- und Rollback-Modell.

## [4.0.1] - 2026-07-19

### Added

- Solakon-ONE-Anbindung über read-only Modbus TCP.
- Auswahl der Datenquelle für Solarleistung sowie Netzbezug und Einspeisung.
- Vergleich von Solakon-ONE-AC-Leistung und Shelly-AC-Messung.
- Automatische Erweiterung bestehender Konfigurationen und Datenbanken.
- Raspberry-Pi-Upgrade, Diagnose, Backup und manuelles Rollback.

### Security

- Solakon-Zugriff verwendet ausschließlich lesende Modbus-Aufrufe.
- Laufzeitdaten und lokale Konfiguration werden aus Release-Archiven ausgeschlossen.

## [3.0.0]

### Added

- Browserbasierte Bedienoberfläche mit Dashboard, Datenerfassung, Konfiguration und Datenverwaltung.
- Unterstützung für Shelly PM Mini Gen 3, Shelly 3EM Gen 1 und Shelly Pro 3EM.
- SQLite-Speicherung, CSV-Export und Demodaten.

## Dokument-Change-Log

- 2026-11-07 — Unreleased-Eintrag zum Datenbankstart-Inspektionspfad ergänzt; Anlass/Quelle: verifizierter Produktions-Codevergleich mit GitHub; Prüfstatus: Implementierung, Tests und Dokumentation abgeglichen.
- 2026-11-07 — Unreleased-Einträge zu Monatsansicht, Wertetabelle und SQL-Aggregation ergänzt; Anlass/Quelle: Betreiberanforderung Monatsauswahl und Analyse der Dashboard-Latenzen; Prüfstatus: Implementierung und Tests abgeglichen, `./scripts/verify.sh` PASS.
- 2026-11-07 — Abschnitt „Betrieb" mit Deployment-Stand, Messwerten, Rollback und Update-Hinweis ergänzt; Anlass/Quelle: freigegebenes Deployment auf der Referenzinstallation; Prüfstatus: Deployment und Messung verifiziert, Sicherung vorhanden.
- 2026-11-07 — Einträge zu Live-Latenz (Abfrageplan des letzten Detaildatensatzes) und Asset-Token ergänzt; Anlass/Quelle: Messung des Query-Plans auf der Referenzinstallation und Betreiberfreigabe; Prüfstatus: Tests und Messung auf dem Host, Deployment nach Freigabe.

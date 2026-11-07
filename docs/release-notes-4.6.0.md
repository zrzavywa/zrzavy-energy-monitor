# Zrzavy Energy Monitor 4.6.0

4.6.0 macht das Dashboard benutzbar, ohne auf die Antwortzeiten zu achten. Die
Historie wird in SQLite aggregiert, die Jahresansicht fällt von rund 148 auf
unter 7 Sekunden, die Live-Ansicht von 5,9 auf 0,06 Sekunden. Neu ist die
Monatsauswahl mit einer Wertetabelle unter dem Diagramm.

## Änderungen

- **SQL-Aggregation:** Die Historie wird je Stunde zusammengefasst und erst
  danach auf Tages-, Wochen-, Monats- oder Jahresbuckets verteilt, statt alle
  Rohzeilen zu laden und in Python zu summieren.
- **Monatsansicht:** Zeitraum `Monat` mit einem Bucket je Kalendertag sowie
  eine Wertetabelle mit Erzeugung, Hausverbrauch, Netzbezug, Einspeisung und
  Eigenverbrauch je Bucket und als Summe.
- **Schnellere Oberfläche:** Energie- und Phasenansicht laden parallel, die
  Jahresansicht fragt keinen Phasenverlauf mehr ab, und der automatische
  Aktualisierungslauf beschränkt sich auf die Tagesansicht.
- **Live-Ansicht:** Die Abfrage des letzten Netzanschluss-Datensatzes sortiert
  nicht mehr alle Detailzeilen über die Messzeit, sondern liest ein begrenztes
  Fenster der jüngsten Messungen über den Zeitstempelindex. Gemessen
  0,001 s statt 5,66 s.
- **Asset-Token:** `app.css`, `dashboard.js` und `update.js` werden mit einem
  aus dem Inhalt berechneten Token ausgeliefert; nach einem Update laden
  Browser die neuen Dateien selbstständig.

## Gemessen auf der Referenzinstallation

| Ansicht | vorher | 4.6.0 |
| --- | --- | --- |
| Dashboard Tag | 0,50 s | 0,06 s |
| Dashboard Woche | 5,21 s | 0,27 s |
| Dashboard Monat | – | 0,34 s |
| Dashboard Jahr | 147,9 s | 6,88 s |
| Live | 5,9 s | 0,06 s |

Die Werte stammen von einem Raspberry Pi mit rund 224 000 Messzeilen und wurden
über die lokalen HTTP-Endpunkte gemessen; sie sind keine Zusage für andere
Hardware.

## Upgrade

Das reguläre Update über die Update-Seite bzw. den Updater installiert das
Release in einem neuen Verzeichnis und schaltet `current` um. Datenbank und
Konfiguration bleiben unverändert; das Schema bleibt Version 2.

## Bekannte Grenzen

- Die Jahresansicht liest weiterhin alle Messzeilen des Jahres; eine
  materialisierte Rollup-Tabelle ist nicht enthalten.
- Der Phasenverlauf wird für die Jahresansicht bewusst nicht angeboten, weil
  Monatsmittelwerte von Momentanleistungen wenig aussagekräftig sind.

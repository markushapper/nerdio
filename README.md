# Nerdio PWA

**MUSIC · PLAY** — Song starten, analog mit den drei Nerdio-Karten spielen, Lösung aufdecken.

## Enthalten

- Mitgelieferter Halloween-Pack (51 Songs)
- Neue `gamepack.json`-Dateien lokal importieren
- Importierte Packs dauerhaft im Browser via IndexedDB speichern
- Pro Pack eine zufällige Reihenfolge erzeugen und lokal fortsetzen
- Pack-Fortschritt zurücksetzen / neu mischen
- Importierte Packs wieder löschen
- Offline-fähige PWA-Oberfläche; Amazon Music selbst benötigt Internet
- Keine Accounts, keine Cloud, kein Backend, keine Punkte- oder Spielerlogik

## Lokal starten

Eine PWA sollte über HTTP(S) laufen, nicht direkt per `file://`.

```bash
python3 -m http.server 8080
```

Danach `http://localhost:8080` öffnen.

Auf Mobilgeräten für eine echte PWA-Installation über einen beliebigen statischen HTTPS-Host bereitstellen (z. B. GitHub Pages, Netlify oder Cloudflare Pages). Es ist kein Server-Code erforderlich.

## Neues Pack importieren

Auf dem Startscreen **+ Pack importieren** wählen und eine JSON-Datei auswählen. Erwartet werden mindestens:

- `pack_id`
- `playlist_name`
- `songs[]`
- pro Song: `title`, `artist`, `scoring_year`, `amazon_play_url`

Wenn `status` vorhanden ist, muss es `READY` sein.

## Spielprinzip

1. Pack öffnen.
2. `Song starten` öffnet den gespeicherten Amazon-Music-Link.
3. Die Spieler notieren/bewerten außerhalb der App.
4. `Lösung aufdecken` zeigt Titel, Interpret und Wertungsjahr.
5. `Nächster Song` fährt in der gemischten Reihenfolge fort.

# wsc-public

Warteschlange für die Instagram-Posts von @thefke.

Das Repo ist öffentlich, weil Instagram die Bilder über eine öffentliche URL abholt. Hier liegt nichts, was nicht ohnehin gepostet wird.

## So läuft es

- `queue/`: geplante Beiträge, je ein Ordner mit `image.jpg` und `post.json`.
- `posted/`: veröffentlichte Beiträge, mit Media-ID und Zeitpunkt.
- `plan/`: vorbereitete Posts zum Hochladen von Hand, je Tag ein Ordner mit Bildern und `caption.txt`. Wird nie automatisch gepostet. Nach jeder Änderung an `plan/` oder `queue/` `python3 tools/plan_index.py` laufen lassen, das schreibt `plan/index.json` für die Seite `why-so-curious.com/studio/posts/`. Feld `slot`: `auto`, wenn ein `post.json` in `queue/` oder `posted/` per `plan` auf den Ordner zeigt (die Seite zeigt dann „Läuft automatisch“), sonst `hand`. Weicht die README eines Plan-Posts davon ab, warnt das Skript, es gilt `queue/`.
- Captions mit Büchern enden ab 17.11.2026 vor den Hashtags mit „Books from this post: link in bio.“ Der Bio-Link geht auf `why-so-curious.com/en/ig/`, dort stehen die Bücher jedes Posts. `plan_insert.py` setzt die Zeile selbst, Posts ohne Bücher bekommen `"bio": false`.
- Workflow `Publish`: läuft stündlich, postet den nächsten fälligen Beitrag und verschiebt ihn nach `posted/`. Höchstens ein Post pro Lauf.
- Sprachsperre (seit 27.11.2026): @thefke postet nur Englisch, deutsche Texte gehören auf @thomas.hefke. `tools/sprache.py` erkennt deutsche Captions ohne Pakete (Funktionswörter und Umlaute gegen englische, Hashtags und Text in Anführungszeichen zählen nicht, damit deutsche Buchtitel und Zitate eine englische Caption nicht kippen). `publish.py` bricht vor jeder Anfrage an Instagram ab, `queue_plan.py`, `enqueue.py`, `plan_insert.py` und `plan_add.py` nehmen eine deutsche Caption nicht an. Ganzen Bestand prüfen: `python3 tools/sprache.py`, Tests: `python3 tools/test_sprache.py`.
- Workflow `Refresh Token`: erneuert den Instagram-Token am 1. und 15. des Monats.

## Beitrag anlegen

```
pip install pillow
python3 tools/enqueue.py export.png --at 2026-10-05T07:30 --caption caption.txt --slug phone
```

Ohne Zeitzone gilt Berliner Zeit. Das Bild darf PNG oder JPEG sein, es landet als JPEG in `queue/`.

Einen geplanten Beitrag stoppen: Ordner aus `queue/` löschen und pushen.

## Einrichtung

Secrets unter Settings, Secrets and variables, Actions:

- `META_TOKEN`: Systemnutzer-Token aus dem Business Manager. `Publish` und `Live` nutzen es, `Publish` findet die Konto-ID von @thefke selbst über `me/accounts` (seit 19.11.2026).
- `IG_USER_ID`, `IG_ACCESS_TOKEN`, `GH_PAT`: nicht mehr gebraucht. Der Instagram-Login-Token war nie gültig, der Workflow `Refresh Token` ist am 23.11.2026 entfernt. Die Secrets löscht Thomas in den Einstellungen.

Test ohne Risiko: Actions, `Publish`, „Run workflow“ mit Modus `pruefen`. Das baut den nächsten Beitrag bei Instagram als Container, ohne ihn zu veröffentlichen.

## Live-Liste für die Bio-Link-Seite

`plan/live.json` sagt, welche Plan-Posts auf @thefke wirklich live sind, mit Zeitpunkt und Link (`tools/live.py`). Die Seite `/en/ig/` auf why-so-curious.com liest sie, damit dort steht, was auf Instagram zu sehen ist, auch wenn vom Plandatum abweichend gepostet wird.

- Stündlich schreibt sie der Workflow `Live`, sobald das Secret `META_TOKEN` gesetzt ist (Systemnutzer-Token, einmal von Thomas eintragen). Bis dahin hilft nur ein Lauf von Hand in einer Claude-Session (`python3 tools/live.py`, der Proxy setzt dort das Token ein).
- Fehlt ein Post in der Liste, zeigt die Seite ihn ab seinem Plandatum.

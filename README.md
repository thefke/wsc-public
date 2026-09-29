# wsc-public

Warteschlange für die Instagram-Posts von @thefke.

Das Repo ist öffentlich, weil Instagram die Bilder über eine öffentliche URL abholt. Hier liegt nichts, was nicht ohnehin gepostet wird.

## So läuft es

- `queue/`: geplante Beiträge, je ein Ordner mit `image.jpg` und `post.json`.
- `posted/`: veröffentlichte Beiträge, mit Media-ID und Zeitpunkt.
- Workflow `Publish`: läuft stündlich, postet den nächsten fälligen Beitrag und verschiebt ihn nach `posted/`. Höchstens ein Post pro Lauf.
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

- `IG_USER_ID`: Instagram-User-ID des Creator-Kontos
- `IG_ACCESS_TOKEN`: langlebiger Token aus der Meta-App
- `GH_PAT`: Fine-grained Token nur für dieses Repo, Berechtigung „Secrets: Read and write". Den braucht `Refresh Token`, um den neuen Token zu speichern.

Test ohne Risiko: Actions, `Publish`, „Run workflow" mit `dry_run`. Das zeigt nur an, was fällig ist.

"""Legt Plan-Posts in queue/, damit publish.py sie automatisch postet.

Aufruf aus dem Repo-Root:
    python3 tools/queue_plan.py 2026-11-23-after-zero-to-one 2026-11-24-after-never-split
    python3 tools/queue_plan.py --slot frueh            # alle Plan-Ordner mit „Früh-Slot“ ab heute
    python3 tools/queue_plan.py ... --apply             # ohne --apply nur Bericht

Je Plan-Ordner entsteht queue/<datum>-<HHMM>-<slug>/post.json mit Caption aus
caption.txt und "images" mit den Pfaden der Slides in plan/. Die Bilder werden
nicht kopiert, publish.py lädt sie über raw.githubusercontent.com.

Uhrzeit: feste Zeit je Wochentag im Fenster 07:30 bis 09:30 Berliner Zeit (ZEITEN,
Thomas, 23.11.2026). Je Wochentag startet eine geplante Aufgabe in Claude den Workflow
Publish eine Minute danach. Früh-Slot nach Option C vom 19.11.2026: früh automatisch
ohne Musik, mittags und abends von Hand mit Musik.

Prüft vor dem Anlegen: Slides vorhanden, höchstens 20, JPEG, Seitenverhältnis
zwischen 4:5 und 1,91:1, Caption höchstens 2.200 Zeichen und 30 Hashtags,
Ordner noch nicht in queue/ oder posted/, Caption englisch (tools/sprache.py,
deutsche Texte gehören auf @thomas.hefke).
"""
import json
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sprache  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PLAN, QUEUE, POSTED = REPO / 'plan', REPO / 'queue', REPO / 'posted'
BERLIN = ZoneInfo('Europe/Berlin')
CAPTION_MAX, TAGS_MAX, BILDER_MAX = 2200, 30, 20


# Feste Uhrzeit je Wochentag (Thomas, 23.11.2026): Mo bis So. Der Zeitplan von GitHub ist
# unzuverlässig (Läufe nur alle 6 bis 9 Stunden), deshalb startet je Wochentag eine geplante
# Aufgabe in Claude den Workflow Publish zur selben Uhrzeit plus eine Minute.
ZEITEN = {0: time(8, 10), 1: time(7, 45), 2: time(8, 25), 3: time(7, 35), 4: time(7, 55), 5: time(8, 40), 6: time(9, 5)}


def zeitpunkt(name: str) -> datetime:
    tag = date.fromisoformat(name[:10])
    return datetime.combine(tag, ZEITEN[tag.weekday()], BERLIN)


def pruefen(ordner: Path) -> tuple[list[str], str]:
    slides = sorted(p for p in ordner.glob('[0-9]*.jpg'))
    if not slides:
        raise ValueError(f'{ordner.name}: keine Slides')
    if len(slides) > BILDER_MAX:
        raise ValueError(f'{ordner.name}: {len(slides)} Slides, höchstens {BILDER_MAX}')
    for s in slides:
        with Image.open(s) as im:
            if im.format != 'JPEG':
                raise ValueError(f'{s}: kein JPEG')
            r = im.width / im.height
            if not 0.8 - 1e-3 <= r <= 1.91:
                raise ValueError(f'{s}: Seitenverhältnis {r:.2f} außerhalb 4:5 bis 1,91:1')
    cap = (ordner / 'caption.txt').read_text(encoding='utf-8').strip()
    if len(cap) > CAPTION_MAX:
        raise ValueError(f'{ordner.name}: Caption {len(cap)} Zeichen')
    if len(re.findall(r'(?<!\w)#\w+', cap)) > TAGS_MAX:
        raise ValueError(f'{ordner.name}: mehr als {TAGS_MAX} Hashtags')
    m = sprache.meldung(f'plan/{ordner.name}/caption.txt', cap)
    if m:
        raise ValueError(m)
    return [s.relative_to(REPO).as_posix() for s in slides], cap


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    apply = '--apply' in sys.argv
    if '--slot' in sys.argv:
        heute = date.today().isoformat()
        args = [d.name for d in sorted(PLAN.iterdir())
                if d.is_dir() and re.match(r'\d{4}-', d.name) and d.name[:10] >= heute
                and 'Früh-Slot' in (d / 'README.md').read_text(encoding='utf-8')]
        args = [a for a in args if a != 'frueh']
    vorhanden = {p.name[16:] for base in (QUEUE, POSTED) if base.exists() for p in base.iterdir() if p.is_dir()}
    fehler = 0
    for name in args:
        ordner = PLAN / name
        slug = name[11:]
        if slug in vorhanden:
            print(f'schon in queue/ oder posted/: {name}')
            continue
        try:
            bilder, cap = pruefen(ordner)
        except Exception as e:
            print(f'FEHLER {e}')
            fehler += 1
            continue
        at = zeitpunkt(name)
        ziel = QUEUE / f'{at:%Y-%m-%d-%H%M}-{slug}'
        print(f'{ziel.name}  {at:%a %d.%m. %H:%M}  {len(bilder)} Slides')
        if apply:
            ziel.mkdir(parents=True)
            (ziel / 'post.json').write_text(json.dumps(
                {'publish_at': at.isoformat(), 'caption': cap, 'images': bilder, 'plan': name},
                ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not apply:
        print('\nnur Bericht, mit --apply anlegen')
    return 1 if fehler else 0


if __name__ == '__main__':
    sys.exit(main())

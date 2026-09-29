"""Legt einen Beitrag in queue/ an: Bild als JPEG, Caption und Termin.

Aufruf:
    python3 tools/enqueue.py BILD --at 2026-10-05T07:30 --caption caption.txt --slug phone
    python3 tools/enqueue.py BILD --at 2026-10-05T07:30+02:00 --caption-text "..." --slug phone

BILD darf PNG oder JPEG sein, zum Beispiel der Export aus dem Studio. Es wird
auf höchstens 1080 px Breite gebracht und als JPEG gespeichert, weil die
Instagram API nur JPEG annimmt.

Ohne Zeitzone gilt Europe/Berlin.

Das Seitenverhältnis muss zwischen 4:5 (hochkant) und 1,91:1 (quer) liegen,
sonst lehnt Instagram das Bild ab. Das Skript prüft das vorher.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
QUEUE = REPO / 'queue'
MAX_W = 1080
CAPTION_MAX = 2200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image')
    ap.add_argument('--at', required=True, help='Termin, ISO 8601')
    ap.add_argument('--slug', required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--caption', help='Datei mit der Caption')
    g.add_argument('--caption-text')
    a = ap.parse_args()

    at = datetime.fromisoformat(a.at)
    if at.tzinfo is None:
        at = at.replace(tzinfo=ZoneInfo('Europe/Berlin'))
    caption = Path(a.caption).read_text(encoding='utf-8').strip() if a.caption else a.caption_text.strip()
    if len(caption) > CAPTION_MAX:
        sys.exit(f'Caption hat {len(caption)} Zeichen, Instagram erlaubt {CAPTION_MAX}')

    img = Image.open(a.image).convert('RGB')
    ratio = img.width / img.height
    if not 0.8 - 1e-3 <= ratio <= 1.91 + 1e-3:
        sys.exit(f'Seitenverhältnis {img.width}x{img.height} liegt außerhalb von 4:5 bis 1,91:1')
    if img.width > MAX_W:
        img = img.resize((MAX_W, round(MAX_W / ratio)), Image.LANCZOS)

    folder = QUEUE / f'{at.strftime("%Y-%m-%d-%H%M")}-{a.slug}'
    if folder.exists():
        sys.exit(f'{folder.name} gibt es schon')
    folder.mkdir(parents=True)
    img.save(folder / 'image.jpg', 'JPEG', quality=92, optimize=True)
    meta = {'publish_at': at.isoformat(), 'image': 'image.jpg', 'caption': caption}
    (folder / 'post.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'angelegt: {folder.relative_to(REPO)} ({img.width}x{img.height}, {len(caption)} Zeichen Caption)')


if __name__ == '__main__':
    main()

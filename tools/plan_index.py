"""Schreibt plan/index.json, das Inhaltsverzeichnis für /studio/posts/ auf why-so-curious.com.

Liest jeden Ordner plan/YYYY-MM-DD-slug/ mit README.md (erste Zeile ist der Titel),
caption.txt und den Medien (JPG-Slides oder reel.mp4). Nach jeder Änderung an plan/
oder queue/ laufen lassen und mitcommitten.

Feld slot: "auto", wenn ein post.json in queue/ oder posted/ mit "plan" auf den Ordner zeigt.
Den Post postet dann der Workflow Publish, die Seite markiert ihn als "läuft automatisch",
damit er nicht zusätzlich von Hand gepostet wird. auto_at ist der geplante Zeitpunkt,
auto_posted sagt, ob er schon draußen ist. Sonst "hand".

Aufruf aus dem Repo-Root:
    python3 tools/plan_index.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / 'plan'


def auto_slots():
    """Plan-Ordner, die der Workflow Publish postet: {ordner: (publish_at, schon gepostet)}."""
    slots = {}
    for sub in ('queue', 'posted'):
        for f in sorted((ROOT / sub).glob('*/post.json')):
            post = json.loads(f.read_text(encoding='utf-8'))
            if post.get('plan'):
                slots[post['plan']] = (post.get('publish_at', ''), sub == 'posted')
    return slots


def main():
    auto = auto_slots()
    posts = []
    for d in sorted(p for p in PLAN.iterdir() if p.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}-', p.name)):
        head = (d / 'README.md').read_text(encoding='utf-8').splitlines()[0]
        title = head.split('·', 1)[-1].strip()
        media = sorted(f.name for f in d.iterdir() if f.suffix in ('.jpg', '.mp4'))
        readme_frueh = 'Früh-Slot' in (d / 'README.md').read_text(encoding='utf-8')
        if readme_frueh != (d.name in auto):
            print(f'Achtung {d.name}: README sagt {"Früh-Slot" if readme_frueh else "von Hand"}, '
                  f'queue/posted sagt {"automatisch" if d.name in auto else "von Hand"}. Es gilt queue/posted.')
        slot = {'slot': 'hand'}
        if d.name in auto:
            slot = {'slot': 'auto', 'auto_at': auto[d.name][0], 'auto_posted': auto[d.name][1]}
        posts.append({
            'date': d.name[:10],
            'folder': d.name,
            'title': title,
            'format': 'reel' if 'reel.mp4' in media else 'carousel',
            'media': media,
            'caption': (d / 'caption.txt').read_text(encoding='utf-8').strip(),
            **slot,
        })
    (PLAN / 'index.json').write_text(json.dumps({'posts': posts}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'{len(posts)} Posts in plan/index.json, davon {sum(p["slot"] == "auto" for p in posts)} automatisch')


if __name__ == '__main__':
    main()

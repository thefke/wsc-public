"""Schreibt plan/index.json, das Inhaltsverzeichnis für /studio/posts/ auf why-so-curious.com.

Liest jeden Ordner plan/YYYY-MM-DD-slug/ mit README.md (erste Zeile ist der Titel),
caption.txt und den Medien (JPG-Slides oder reel.mp4). Nach jeder Änderung an plan/
laufen lassen und mitcommitten.

Aufruf aus dem Repo-Root:
    python3 tools/plan_index.py
"""
import json
import re
from pathlib import Path

PLAN = Path(__file__).resolve().parent.parent / 'plan'


def main():
    posts = []
    for d in sorted(p for p in PLAN.iterdir() if p.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}-', p.name)):
        head = (d / 'README.md').read_text(encoding='utf-8').splitlines()[0]
        title = head.split('·', 1)[-1].strip()
        media = sorted(f.name for f in d.iterdir() if f.suffix in ('.jpg', '.mp4'))
        posts.append({
            'date': d.name[:10],
            'folder': d.name,
            'title': title,
            'format': 'reel' if any(m.endswith('.mp4') for m in media) else 'carousel',
            'media': media,
            'caption': (d / 'caption.txt').read_text(encoding='utf-8').strip(),
        })
    (PLAN / 'index.json').write_text(json.dumps({'posts': posts}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'{len(posts)} Posts in plan/index.json')


if __name__ == '__main__':
    main()

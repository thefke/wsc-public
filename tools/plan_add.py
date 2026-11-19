"""Fügt Posts in freie Slots von plan/ ein, ohne andere Ordner zu verschieben.

Seit 16.11.2026 gibt es mehrere Posts am Tag, seit 23.11.2026 drei Slots
(Option C, Thomas 19.11.2026):
- frueh:  07:30 bis 09:30, automatisch ohne Musik (danach tools/queue_plan.py)
- mittag: bis 13 Uhr, Thomas postet von Hand mit Musik
- abend:  ab 18 Uhr, Winkel-Post, Thomas postet von Hand mit Musik
tools/plan_insert.py kennt nur einen Post pro Tag und schiebt alles nach.

Aufruf aus dem Repo-Root: python3 tools/plan_add.py . spec.json [--apply]
spec: [{"date":"2026-12-10","slug":"...","title":"...","src":"<out-ordner mit PNGs>","caption":"<cap.md>","slot":"frueh"|"mittag"|"abend","bio":true}]
"""
import json, re, sys
from pathlib import Path
from PIL import Image
import datetime as dt

ROOT = Path(sys.argv[1]); P = ROOT / 'plan'
spec = json.load(open(sys.argv[2])); APPLY = '--apply' in sys.argv
BIO = 'Books from this post: link in bio.'
TAGS = '#bookstagram #bookrecommendations #books'  # höchstens drei (Thomas, 18.11.2026)
DOW = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
lab = lambda d: f'{DOW[d.weekday()]} {d:%d.%m.}'

existing = {d.name for d in P.iterdir() if d.is_dir()}
per_day = {}
for n in existing:
    if re.match(r'\d{4}-\d\d-\d\d-', n): per_day.setdefault(n[:10], []).append(n)
fehler = []
for s in spec:
    name = f"{s['date']}-{s['slug']}"
    if name in existing: fehler.append(f'{name} existiert schon')
    if any(e.endswith('-' + s['slug']) for e in existing): fehler.append(f"Slug {s['slug']} gibt es schon im Plan")
    n = len(per_day.get(s['date'], [])) + sum(1 for t in spec if t['date'] == s['date'])
    if n > 3: fehler.append(f"{s['date']}: dann {n} Posts am Tag")
    if not Path(s['src']).is_dir(): fehler.append(f"{s['src']} fehlt")
    if not Path(s['caption']).is_file(): fehler.append(f"{s['caption']} fehlt")
if fehler:
    print('\n'.join(fehler)); sys.exit(1)

for s in spec:
    d = dt.date.fromisoformat(s['date']); tgt = P / f"{s['date']}-{s['slug']}"
    src = Path(s['src']); pngs = sorted(src.glob('*.png'))
    print('NEU', tgt.name, s.get('slot', 'mittag'), len(pngs), 'Slides')
    if not APPLY: continue
    tgt.mkdir()
    media = []
    for f in pngs:
        Image.open(f).convert('RGB').save(tgt / (f.stem + '.jpg'), quality=90); media.append(f.stem + '.jpg')
    cap = Path(s['caption']).read_text().strip() + ('\n\n' + BIO if s.get('bio', True) else '') + '\n\n' + TAGS + '\n'
    (tgt / 'caption.txt').write_text(cap)
    abend = {'abend': 'Abend-Slot. ', 'frueh': 'Früh-Slot, wird automatisch gepostet (ohne Musik). Nicht von Hand posten. '}.get(s.get('slot'), '')
    (tgt / 'README.md').write_text(
        f"# {lab(d)} · {s['title']}\n\n{abend}Karussell, {len(media)} Slides. Beim Hochladen 4:5 wählen.\n\n## Caption\n\n```\n{cap}```\n\n## Slides\n\n"
        + ''.join(f'![{m}]({m})\n' for m in media))

if APPLY:
    rd = (P / 'README.md').read_text()
    a = rd.index('| Tag |'); b = rd.index('\nHinweise:')
    alt = {}
    for line in rd[a:b].splitlines():
        m = re.match(r'\| .*? \| \[.*?\]\((.*?)/\) \| (.*) \|$', line)
        if m: alt[m.group(1)] = m.group(2)
    neu = {f"{s['date']}-{s['slug']}": {'abend': 'Karussell, abends', 'frueh': 'Karussell, früh, automatisch'}.get(s.get('slot'), 'Karussell') for s in spec}
    rows = []
    for d in sorted(x for x in P.iterdir() if x.is_dir() and re.match(r'\d{4}-', x.name)):
        h = (d / 'README.md').read_text().splitlines()[0][2:]; l, t = h.split(' · ', 1)
        rows.append(f'| {l} | [{t}]({d.name}/) | {neu.get(d.name) or alt.get(d.name, "Karussell")} |')
    rd = rd[:a] + '| Tag | Post | Format |\n|---|---|---|\n' + '\n'.join(rows) + '\n' + rd[b:]
    (P / 'README.md').write_text(rd)
    print('README.md:', len(rows), 'Zeilen')

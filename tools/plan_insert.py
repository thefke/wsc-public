"""Neue Posts in den Plan einfügen, alles Nicht-Fixierte rückt nach. Aufruf aus dem Repo-Root: python3 tools/plan_insert.py spec.json [--apply]. Ohne --apply nur Bericht. Braucht Pillow, bei kaputtem System-Pillow ein venv im Scratchpad nehmen. Danach tools/plan_index.py laufen lassen.
spec: [{"date":"2026-10-30","slug":"follow-the-line","title":"...","src":"/pfad/zum/out","caption":"/pfad/cap.md"}]"""
import json, re, sys, shutil, subprocess, datetime as dt
from pathlib import Path
from PIL import Image
P = Path(__file__).resolve().parent.parent / 'plan'; APPLY = '--apply' in sys.argv
TAGS = '#books #bookstagram #bookrecommendations #reading #thefke #booklover #whysocurious'
DOW = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
PIN = {'gift-guide': '2026-12-05', 'reading-plan-2027': '2026-12-30', 'end-of-year-reflection': '2026-12-31', 'first-week-of-january': '2027-01-01'}
spec = json.load(open(sys.argv[1]))
start = min(s['date'] for s in spec)
lab = lambda d: f'{DOW[d.weekday()]} {d:%d.%m.}'
dirs = sorted(d for d in P.iterdir() if d.is_dir() and re.match(r'\d{4}-', d.name) and d.name[:10] >= start)
slug = lambda n: n[11:]
movable = [d for d in dirs if slug(d.name) not in PIN]
pinned = {dt.date.fromisoformat(v): next(d for d in dirs if slug(d.name) == k) for k, v in PIN.items()}
new = {dt.date.fromisoformat(s['date']): s for s in spec}
day, q, plan = dt.date.fromisoformat(start), list(movable), []
while q or any(d >= day for d in list(pinned) + list(new)):
    if day in pinned: plan.append((day, 'old', pinned[day]))
    elif day in new: plan.append((day, 'new', new[day]))
    elif q: plan.append((day, 'old', q.pop(0)))
    day += dt.timedelta(1)
for d, k, x in plan:
    if k == 'old':
        tgt = P / f'{d.isoformat()}-{slug(x.name)}'
        if tgt != x:
            print(f'{x.name} -> {tgt.name}')
            if APPLY:
                subprocess.run(['git', '-C', str(P.parent), 'mv', str(x), str(tgt)], check=True)
                r = (tgt / 'README.md').read_text().split('\n', 1)
                (tgt / 'README.md').write_text(f'# {lab(d)} · ' + r[0].split('·', 1)[1].strip() + '\n' + r[1])
    else:
        tgt = P / f"{d.isoformat()}-{x['slug']}"; print('NEU', tgt.name)
        if APPLY:
            tgt.mkdir()
            src = Path(x['src']); media = []
            for f in sorted(src.iterdir()):
                if f.suffix == '.mp4': shutil.copy(f, tgt / f.name); media.append(f.name)
                elif f.suffix == '.png' and not (src / (f.stem + '.mp4')).exists():
                    Image.open(f).convert('RGB').save(tgt / (f.stem + '.jpg'), quality=90); media.append(f.stem + '.jpg')
            media.sort()
            cap = Path(x['caption']).read_text().strip() + '\n\n' + TAGS + '\n'
            (tgt / 'caption.txt').write_text(cap)
            kind = 'Karussell mit Video-Slides' if any(m.endswith('.mp4') for m in media) else 'Karussell'
            (tgt / 'README.md').write_text(f"# {lab(d)} · {x['title']}\n\n{kind}, {len(media)} Slides. Beim Hochladen 4:5 wählen.\n\n## Caption\n\n```\n{cap}```\n\n## Slides\n\n" + ''.join(f'![{m}]({m})\n' if m.endswith('.jpg') else f'[{m}]({m})\n' for m in media))
if APPLY:
    rows = []
    for d in sorted(x for x in P.iterdir() if x.is_dir() and re.match(r'\d{4}-', x.name)):
        h = (d / 'README.md').read_text().splitlines()[0][2:]; l, t = h.split(' · ', 1)
        js = list(d.glob('*.jpg')); mp = list(d.glob('*.mp4'))
        f = 'Reel' if (d / 'reel.mp4').exists() else ('Karussell, Video' if mp else ('Einzelbild' if len(js) == 1 else 'Karussell'))
        rows.append(f'| {l} | [{t}]({d.name}/) | {f} |')
    rd = (P / 'README.md').read_text(); a = rd.index('| Tag |'); b = rd.index('\nHinweise:')
    last = plan[-1][0]
    rd = rd[:a] + '| Tag | Post | Format |\n|---|---|---|\n' + '\n'.join(rows) + '\n' + rd[b:]
    rd = re.sub(r'^# Plan: .*$', f"# Plan: 4. Oktober bis {last.day}. {['Januar','Dezember'][last.month == 12]} {last.year}", rd, count=1, flags=re.M)
    (P / 'README.md').write_text(rd)
print('letzter Tag', plan[-1][0])

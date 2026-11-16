"""Schreibt plan/live.json: welche Posts aus dem Plan auf @thefke wirklich live sind, mit Zeitpunkt und Link.

Die Bio-Link-Seite /en/ig/ auf why-so-curious.com liest die Datei, damit dort genau das steht, was auf
Instagram zu sehen ist, egal wann gepostet wurde.

Quelle ist die Graph API über Facebook Login (Systemnutzer-Token mit instagram_basic):
- In einer Claude-Session spritzt der Proxy das Token für graph.facebook.com ein, kein eigenes Token nötig.
- Im Workflow `Live` kommt es aus dem Secret META_TOKEN und geht nur als Header raus, nie in die URL.

Zuordnung Medium zu Plan-Ordner über den Caption-Text (Ähnlichkeit ab 0,6 auf den ersten 300 Zeichen).
Schlüssel ist der Slug ohne Datum, damit ein Umdatieren im Plan nichts kaputt macht. Einträge aus
früheren Läufen bleiben stehen, auch wenn ein Post aus den letzten 100 Medien herausfällt.

Aufruf aus dem Repo-Root:
    python3 tools/live.py            schreibt plan/live.json
    python3 tools/live.py --check    zeigt nur, was zugeordnet wird
"""
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = 'https://graph.facebook.com/v27.0'
KONTO = os.environ.get('IG_USERNAME', 'thefke')
PLAN = Path(__file__).resolve().parent.parent / 'plan'
OUT = PLAN / 'live.json'
SCHWELLE = 0.6


def hole(pfad=None, url=None, **params):
    if url is None:
        url = f'{API}/{pfad}' + ('?' + urllib.parse.urlencode(params) if params else '')
    req = urllib.request.Request(url, headers={'User-Agent': 'wsc-public-live'})
    token = os.environ.get('META_TOKEN')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            fehler = json.load(e).get('error', {})
        except Exception:
            fehler = {}
        sys.exit(f'Graph API {e.code}: {fehler.get("code")} {fehler.get("message", e.reason)}')


def konto_id():
    for seite in hole('me/accounts', fields='instagram_business_account{id,username}', limit=50).get('data', []):
        ig = seite.get('instagram_business_account') or {}
        if ig.get('username') == KONTO:
            return ig['id']
    sys.exit(f'Das Token sieht @{KONTO} nicht.')


def norm(s):
    return re.sub(r'\W+', ' ', (s or '').lower()).strip()[:300]


def main():
    check = '--check' in sys.argv
    plan = json.loads((PLAN / 'index.json').read_text(encoding='utf-8'))['posts']
    kandidaten = [(p['folder'][11:], norm(p['caption'])) for p in plan]
    planstart = min(p['date'] for p in plan)  # ältere Posts ohne Plan interessieren die Seite nicht

    antwort = hole(f'{konto_id()}/media', fields='id,caption,timestamp,permalink,media_type', limit=100)
    medien = antwort.get('data', [])

    alt = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'posts': [], 'ohne_plan': []}
    posts = {p['slug']: p for p in alt.get('posts', [])}
    ohne = {m['media_id']: m for m in alt.get('ohne_plan', [])}

    for m in medien:
        c = norm(m.get('caption'))
        wert, slug = max((difflib.SequenceMatcher(None, c, k).ratio(), s) for s, k in kandidaten) if c else (0, None)
        eintrag = {
            'media_id': m['id'],
            'posted_at': datetime.strptime(m['timestamp'], '%Y-%m-%dT%H:%M:%S%z').astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'permalink': m.get('permalink'),
        }
        if wert >= SCHWELLE:
            # Wird derselbe Post zweimal gepostet, gilt der erste.
            if slug not in posts or posts[slug]['posted_at'] > eintrag['posted_at']:
                posts[slug] = {'slug': slug, **eintrag}
            ohne.pop(m['id'], None)
        elif eintrag['posted_at'][:10] >= planstart:
            ohne[m['id']] = {**eintrag, 'caption': ' '.join((m.get('caption') or '').split())[:60]}

    plan_slugs = {s for s, _ in kandidaten}
    ergebnis = {
        'stand': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'konto': KONTO,
        'posts': sorted(posts.values(), key=lambda p: p['posted_at'], reverse=True),
        'ohne_plan': sorted(ohne.values(), key=lambda p: p['posted_at'], reverse=True),
    }
    weg = [p['slug'] for p in ergebnis['posts'] if p['slug'] not in plan_slugs]
    print(f'live.json: {len(ergebnis["posts"])} Plan-Posts live, {len(ergebnis["ohne_plan"])} ohne Plan'
          + (f', nicht mehr im Plan: {", ".join(weg)}' if weg else ''))
    if check:
        for p in ergebnis['posts'][:10]:
            print(f'  {p["posted_at"]}  {p["slug"]}')
        return
    neu = json.dumps(ergebnis, ensure_ascii=False, indent=1) + '\n'
    if OUT.exists():
        vorher = json.loads(OUT.read_text(encoding='utf-8'))
        vorher['stand'] = ergebnis['stand']
        if json.dumps(vorher, ensure_ascii=False, indent=1) + '\n' == neu:
            print('unverändert')
            return
    OUT.write_text(neu, encoding='utf-8')


if __name__ == '__main__':
    main()

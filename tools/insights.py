"""Schreibt plan/insights.json: Reichweite und neue Follower je Post, ausgewertet nach Themenmuster.

Grundlage für die Themenwahl (Thomas, 26.11.2026, große Variante). Die Seite /studio/ auf
why-so-curious.com liest die Datei, der Workflow `Insights` schreibt sie jeden Montag neu.

Quelle ist die Graph API wie bei tools/live.py:
- In einer Claude-Session setzt der Proxy das Token für graph.facebook.com ein.
- Im Workflow kommt es aus dem Secret META_TOKEN, nur als Header. Das Token braucht das Recht
  instagram_manage_insights, sonst endet der Lauf mit einem Hinweis.

Was die Datei enthält:
- posts: jeder Beitrag seit 01.09.2026 mit Slug, Muster, Slot (frueh-auto oder hand), Reichweite,
  Views, Saves, Shares, neuen Followern. Reels liefern bei Instagram keine Follower-Zahl.
- muster: je Themenmuster Median-Reichweite, neue Follower je Post und je 1.000 Erreichte.
  Gezählt werden nur Feed-Posts, die mindestens REIF_TAGE alt sind, jüngere wachsen noch.
- slots: Früh-Slot automatisch gegen von Hand, seit Start der Früh-Posts.
- wochen: je Kalenderwoche Posts, Reichweite, neue Follower aus Posts und fürs Konto.
- follower_tag: neue Follower fürs Konto je Tag. Die API gibt nur 30 Tage her, ältere Tage
  bleiben aus früheren Läufen stehen.

Muster je Slug stehen in plan/muster.json.

Aufruf aus dem Repo-Root:
    python3 tools/insights.py            schreibt plan/insights.json
    python3 tools/insights.py --check    zeigt nur die Auswertung
"""
import difflib
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = 'https://graph.facebook.com/v27.0'
KONTO = os.environ.get('IG_USERNAME', 'thefke')
REPO = Path(__file__).resolve().parent.parent
PLAN, POSTED = REPO / 'plan', REPO / 'posted'
OUT = PLAN / 'insights.json'
BERLIN = ZoneInfo('Europe/Berlin')
AB = '2026-09-01'
REIF_TAGE = 3
FRUEH_START = '2026-11-23'
SCHWELLE = 0.6
WOCHENTAGE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']


class ApiFehler(Exception):
    pass


def hole(pfad=None, url=None, **params):
    if url is None:
        url = f'{API}/{pfad}' + ('?' + urllib.parse.urlencode(params) if params else '')
    req = urllib.request.Request(url, headers={'User-Agent': 'wsc-public-insights'})
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
        raise ApiFehler(f'Graph API {e.code}: {fehler.get("code")} {fehler.get("message", e.reason)}')


def konto():
    for seite in hole('me/accounts', fields='instagram_business_account{id,username,followers_count}', limit=50).get('data', []):
        ig = seite.get('instagram_business_account') or {}
        if ig.get('username') == KONTO:
            return ig
    sys.exit(f'Das Token sieht @{KONTO} nicht.')


def norm(s):
    return re.sub(r'\W+', ' ', (s or '').lower()).strip()[:300]


def basis(slug):
    return re.sub(r'-[2-9]$', '', slug)


def muster_von(slug, zuordnung):
    if not slug:
        return None
    b = basis(slug)
    if b in zuordnung:
        return zuordnung[b]
    if b.startswith('after-'):
        return 'after'
    if b.startswith('greatest-'):
        return 'greatest'
    if b.endswith('-single'):
        return 'einzelbild'
    if b.endswith('-reel'):
        return 'reel'
    return 'offen'


def medien(iid):
    felder = 'id,caption,timestamp,media_type,media_product_type,like_count,comments_count,permalink'
    antwort = hole(f'{iid}/media', fields=felder, limit=100)
    liste = antwort.get('data', [])
    while antwort.get('paging', {}).get('next') and liste and liste[-1]['timestamp'][:10] >= AB:
        antwort = hole(url=antwort['paging']['next'])
        liste += antwort.get('data', [])
    return [m for m in liste if m['timestamp'][:10] >= AB]


def werte(mid):
    # Follows und Profilbesuche gibt es nur für Feed-Posts. Bei Reels fragt der zweite Versuch ohne.
    for metrik in ('reach,views,saved,shares,total_interactions,follows,profile_visits',
                   'reach,views,saved,shares,total_interactions'):
        try:
            daten = hole(f'{mid}/insights', metric=metrik).get('data', [])
            return {d['name']: d['values'][0]['value'] for d in daten}
        except ApiFehler as e:
            letzter = e
    raise letzter


def follower_tag(iid):
    tage = {}
    jetzt = int(time.time())
    for i in range(3):
        bis = jetzt - i * 86400 * 29
        try:
            daten = hole(f'{iid}/insights', metric='follower_count', period='day', since=bis - 86400 * 29, until=bis)
        except ApiFehler:
            break  # die API gibt nur rund 30 Tage zurück
        for d in daten.get('data', []):
            for v in d.get('values', []):
                # end_time ist das Ende des Tages, der Wert gehört zum Vortag
                tag = (datetime.strptime(v['end_time'], '%Y-%m-%dT%H:%M:%S%z') - timedelta(days=1)).date().isoformat()
                tage[tag] = v['value']
    return tage


def kennzahlen(posts):
    reach = sum(p['reach'] for p in posts)
    follows = sum(p.get('follows') or 0 for p in posts)
    return {
        'n': len(posts),
        'reach_median': round(statistics.median(p['reach'] for p in posts)) if posts else 0,
        'follows_je_post': round(follows / len(posts), 1) if posts else 0,
        'follows_je_1000': round(1000 * follows / reach, 1) if reach else 0,
        'saves_je_1000': round(1000 * sum(p['saved'] for p in posts) / reach) if reach else 0,
        'shares_je_1000': round(1000 * sum(p['shares'] for p in posts) / reach) if reach else 0,
    }


def main():
    check = '--check' in sys.argv
    regeln = json.loads((PLAN / 'muster.json').read_text(encoding='utf-8'))
    plan = json.loads((PLAN / 'index.json').read_text(encoding='utf-8'))['posts']
    live = json.loads((PLAN / 'live.json').read_text(encoding='utf-8')) if (PLAN / 'live.json').exists() else {'posts': []}
    slug_je_id = {p['media_id']: p['slug'] for p in live.get('posts', [])}
    kandidaten = [(p['folder'][11:], norm(p['caption'])) for p in plan]
    titel = {p['folder'][11:]: p['title'] for p in plan}
    auto = set()
    for f in POSTED.glob('*/post.json'):
        d = json.loads(f.read_text(encoding='utf-8'))
        if d.get('media_id'):
            auto.add(str(d['media_id']))
            slug_je_id.setdefault(str(d['media_id']), d.get('plan', f.parent.name[16:])[11:])

    try:
        ig = konto()
        iid = ig['id']
        liste = medien(iid)
        jetzt = datetime.now(timezone.utc)
        posts = []
        for m in liste:
            w = werte(m['id'])
            slug = slug_je_id.get(m['id'])
            if not slug and m.get('caption'):
                wert, kand = max((difflib.SequenceMatcher(None, norm(m['caption']), k).ratio(), s) for s, k in kandidaten)
                slug = kand if wert >= SCHWELLE else None
            reel = m.get('media_product_type') == 'REELS'
            muster = muster_von(slug, regeln['zuordnung']) or 'offen'
            if reel and muster != 'reel':
                muster = 'reel-fabrik'  # Reels aus content-factory tragen oft die Caption eines Karussells
            zeit = datetime.strptime(m['timestamp'], '%Y-%m-%dT%H:%M:%S%z')
            lokal = zeit.astimezone(BERLIN)
            posts.append({
                'media_id': m['id'],
                'slug': slug,
                'titel': titel.get(slug) if slug else ' '.join((m.get('caption') or '').split())[:60],
                'muster': muster,
                'slot': 'frueh-auto' if m['id'] in auto else 'hand',
                'format': 'reel' if reel else {'CAROUSEL_ALBUM': 'karussell', 'IMAGE': 'einzelbild'}.get(m['media_type'], m['media_type'].lower()),
                'datum': lokal.date().isoformat(),
                'uhrzeit': lokal.strftime('%H:%M'),
                'wochentag': WOCHENTAGE[lokal.weekday()],
                'alter_tage': (jetzt - zeit).days,
                'reach': w.get('reach', 0),
                'views': w.get('views', 0),
                'saved': w.get('saved', 0),
                'shares': w.get('shares', 0),
                'likes': m.get('like_count', 0),
                'comments': m.get('comments_count', 0),
                'follows': w.get('follows'),
                'profile_visits': w.get('profile_visits'),
                'permalink': m.get('permalink'),
            })
        neu_tage = follower_tag(iid)
    except ApiFehler as e:
        hinweis = str(e)
        if 'permission' in hinweis.lower() or ' 10 ' in hinweis or '(#10)' in hinweis:
            hinweis += '. Das Token braucht das Recht instagram_manage_insights.'
        sys.exit(hinweis)

    alt = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    tage = {t['datum']: t['neu'] for t in alt.get('follower_tag', [])}
    tage.update(neu_tage)

    feed = [p for p in posts if p['format'] != 'reel' and p['alter_tage'] >= REIF_TAGE and p['follows'] is not None]
    nach_muster = []
    for key, label in regeln['muster'].items():
        gruppe = [p for p in feed if p['muster'] == key]
        if not gruppe:
            continue
        top = max(gruppe, key=lambda p: p['follows'] or 0)
        nach_muster.append({'muster': key, 'label': label, **kennzahlen(gruppe),
                            'bester': {'slug': top['slug'], 'reach': top['reach'], 'follows': top['follows']}})
    nach_muster.sort(key=lambda x: (-x['follows_je_1000'], -x['n']))

    seit = [p for p in feed if p['datum'] >= FRUEH_START]
    slots = [{'slot': s, **kennzahlen([p for p in seit if p['slot'] == s])} for s in ('frueh-auto', 'hand')]

    wochen = {}
    for p in posts:
        kw = datetime.fromisoformat(p['datum']).strftime('%G-W%V')
        w = wochen.setdefault(kw, {'woche': kw, 'posts': 0, 'reels': 0, 'reach': 0, 'follows_aus_posts': 0, 'neue_follower': 0})
        w['reels' if p['format'] == 'reel' else 'posts'] += 1
        w['reach'] += p['reach']
        w['follows_aus_posts'] += p['follows'] or 0
    for tag, wert in tage.items():
        kw = datetime.fromisoformat(tag).strftime('%G-W%V')
        if kw in wochen:
            wochen[kw]['neue_follower'] += wert

    reels = [p for p in posts if p['format'] == 'reel' and p['alter_tage'] >= REIF_TAGE]
    ergebnis = {
        'stand': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'konto': KONTO,
        'follower_gesamt': ig.get('followers_count'),
        'regeln': f'Muster und Slots zählen nur Feed-Posts ab {REIF_TAGE} Tagen Alter. Reels liefern keine Follower-Zahl.',
        'muster': nach_muster,
        'slots': slots,
        'reels': {'n': len(reels), 'reach_median': round(statistics.median(p['reach'] for p in reels)) if reels else 0},
        'wochen': sorted(wochen.values(), key=lambda w: w['woche'], reverse=True),
        'follower_tag': [{'datum': t, 'neu': tage[t]} for t in sorted(tage, reverse=True)],
        'posts': sorted(posts, key=lambda p: (p['datum'], p['uhrzeit']), reverse=True),
    }

    print(f'@{KONTO}: {ergebnis["follower_gesamt"]} Follower, {len(posts)} Beiträge seit {AB}, {len(feed)} reife Feed-Posts\n')
    print('| Muster | Posts | Reichweite (Median) | Follower je Post | je 1.000 erreicht |')
    print('|---|---|---|---|---|')
    for m in nach_muster:
        print(f'| {m["label"].split(" (")[0]} | {m["n"]} | {m["reach_median"]} | {m["follows_je_post"]} | {m["follows_je_1000"]} |')
    print(f'\nFrüh-Slot seit {FRUEH_START}: ' + ', '.join(f'{s["slot"]} {s["n"]} Posts, {s["follows_je_1000"]} je 1.000' for s in slots))
    print(f'Reels: {ergebnis["reels"]["n"]}, Median-Reichweite {ergebnis["reels"]["reach_median"]}')
    offen = sorted({p['slug'] for p in posts if p['muster'] == 'offen' and p['slug']})
    if offen:
        print(f'Ohne Muster (plan/muster.json ergänzen): {", ".join(offen)}')
    if not check:
        OUT.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

"""Postet fällige Beiträge aus queue/ auf Instagram und verschiebt sie nach posted/.

Ein Beitrag ist ein Ordner in queue/ mit zwei Dateien:

    queue/2026-10-05-0730-phone/
        post.json    {"publish_at": "2026-10-05T07:30:00+02:00", "caption": "..."}
        image.jpg    JPEG, 1080 px breit. Instagram nimmt nur JPEG.

Karussell (seit 19.11.2026): post.json mit "images", einer Liste von Pfaden
relativ zum Repo-Root, meist die Slides eines Plan-Ordners. Dann liegt in
queue/ nur post.json, die Bilder bleiben in plan/. Anlegen mit
tools/queue_plan.py.

    queue/2026-11-23-0812-after-zero-to-one/
        post.json    {"publish_at": "...", "caption": "...", "images": ["plan/2026-11-23-after-zero-to-one/01.jpg", ...]}

Karussell: je Bild ein Container mit is_carousel_item, dann ein Container mit
media_type CAROUSEL und children, dann media_publish. Höchstens 20 Bilder.
Musik kann die API an Karussells nicht hängen (Audio API nur für Reels und nur
mit Facebook-Login, geprüft 19.11.2026).

Ablauf pro fälligem Beitrag, über die Instagram API mit Instagram-Login:

1. Media-Container anlegen: POST /{ig-user-id}/media mit image_url und caption.
   image_url zeigt auf die Datei in diesem öffentlichen Repo, festgenagelt auf
   den Commit, damit sich die URL bis zum Posten nicht ändert.
2. Warten, bis der Container FINISHED meldet.
3. Veröffentlichen: POST /{ig-user-id}/media_publish.
4. Ergebnis in post.json schreiben, Ordner nach posted/ verschieben.

Die API kennt kein eigenes Planen, und ein Container verfällt nach 24 Stunden.
Deshalb läuft dieses Skript stündlich und postet, was fällig ist.

Sprachsperre (seit 27.11.2026): Ist die Caption deutsch, bricht das Skript ab,
bevor es Instagram anfragt. Deutsche Texte gehören auf @thomas.hefke, nie auf
@thefke (tools/sprache.py).

Pro Lauf höchstens ein Beitrag. Hat sich etwas angestaut, weil Läufe
ausgefallen sind, kommt der Rest in den folgenden Stunden. So entsteht nie ein
Schwall von Posts.

Umgebung:
    META_TOKEN       Systemnutzer-Token aus dem Business Manager (wie Workflow Live),
                     geht als Header raus. Die Konto-ID kommt aus me/accounts.
    IG_USERNAME      Konto, Standard thefke
    IG_USER_ID, IG_ACCESS_TOKEN  nur ohne META_TOKEN (Instagram-Login, nie gültig gewesen)
    IG_API           Basis-URL, Standard graph.facebook.com/v27.0 mit META_TOKEN
    IMAGE_BASE_URL   Basis für image_url, Standard raw.githubusercontent.com
                     mit GITHUB_REPOSITORY und GITHUB_SHA

Aufruf:
    python3 tools/publish.py            # zeigt nur, was fällig ist
    python3 tools/publish.py --publish  # postet den nächsten fälligen Beitrag
    python3 tools/publish.py --check    # baut den Container des nächsten Beitrags, postet nicht
"""
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sprache  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
QUEUE = REPO / 'queue'
POSTED = REPO / 'posted'
# Seit 19.11.2026 über das Systemnutzer-Token aus dem Business Manager (Secret META_TOKEN,
# dasselbe wie im Workflow Live) und graph.facebook.com. Der Instagram-Login-Token
# IG_ACCESS_TOKEN war nie gültig (Refresh Token scheitert seit 01.10.2026) und bleibt nur Rückfall.
META = bool(os.environ.get('META_TOKEN'))
API = os.environ.get('IG_API', 'https://graph.facebook.com/v27.0' if META else 'https://graph.instagram.com').rstrip('/')
KONTO = os.environ.get('IG_USERNAME', 'thefke')


def due_posts(now: datetime) -> list[tuple[datetime, Path, dict]]:
    out = []
    for d in sorted(p for p in QUEUE.iterdir() if p.is_dir()):
        meta = json.loads((d / 'post.json').read_text(encoding='utf-8'))
        at = datetime.fromisoformat(meta['publish_at'])
        if at.tzinfo is None:
            raise ValueError(f'{d.name}: publish_at braucht eine Zeitzone, z. B. +02:00')
        for rel in media_paths(d, meta):
            if not (REPO / rel).exists():
                raise FileNotFoundError(f'{d.name}: Bild fehlt: {rel}')
        if len(meta.get('images', [])) > 20:
            raise ValueError(f'{d.name}: höchstens 20 Bilder je Karussell')
        if at <= now:
            out.append((at, d, meta))
    return sorted(out, key=lambda x: x[0])


def media_paths(folder: Path, meta: dict) -> list[str]:
    """Bildpfade relativ zum Repo-Root: Karussell aus "images", sonst das Einzelbild im Ordner."""
    if meta.get('images'):
        return list(meta['images'])
    return [(folder.relative_to(REPO) / meta.get('image', 'image.jpg')).as_posix()]


def url_for(rel: str) -> str:
    base = os.environ.get('IMAGE_BASE_URL')
    if not base:
        repo = os.environ['GITHUB_REPOSITORY']
        ref = os.environ.get('GITHUB_SHA', 'main')
        base = f'https://raw.githubusercontent.com/{repo}/{ref}'
    return f'{base.rstrip("/")}/{urllib.parse.quote(rel)}'


def call(method: str, path: str, params: dict) -> dict:
    headers = {'User-Agent': 'wsc-public-publish'}
    if META:
        headers['Authorization'] = f"Bearer {os.environ['META_TOKEN']}"  # nie in die URL
    else:
        params = {**params, 'access_token': os.environ['IG_ACCESS_TOKEN']}
    data = urllib.parse.urlencode(params).encode()
    url = f'{API}/{path}'
    if method == 'GET':
        req = urllib.request.Request(f'{url}?{data.decode()}' if params else url, headers=headers)
    else:
        req = urllib.request.Request(url, data=data, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        raise RuntimeError(f'{method} {path}: HTTP {e.code} {body}') from None


def wait_finished(container: str) -> None:
    for _ in range(30):
        status = call('GET', container, {'fields': 'status_code'}).get('status_code')
        if status == 'FINISHED':
            return
        if status in ('ERROR', 'EXPIRED'):
            raise RuntimeError(f'Container {container}: {status}')
        time.sleep(5)
    raise RuntimeError(f'Container {container}: nach 150 s nicht fertig')


_IG_ID = None


def ig_user_id() -> str:
    """Mit META_TOKEN die ID des Business-Kontos @thefke aus me/accounts, sonst IG_USER_ID."""
    global _IG_ID
    if _IG_ID:
        return _IG_ID
    if not META:
        _IG_ID = os.environ['IG_USER_ID']
        return _IG_ID
    seiten = call('GET', 'me/accounts', {'fields': 'instagram_business_account{id,username}', 'limit': 50})
    for s in seiten.get('data', []):
        ig = s.get('instagram_business_account') or {}
        if ig.get('username') == KONTO:
            _IG_ID = ig['id']
            return _IG_ID
    raise RuntimeError(f'Das Token sieht @{KONTO} nicht')


def sprachsperre(folder: Path, meta: dict) -> None:
    """Bricht ab, wenn die Caption deutsch ist. Läuft vor jeder Anfrage an Instagram."""
    ort = f'{folder.relative_to(REPO).as_posix()}/post.json'
    m = sprache.meldung(ort, meta.get('caption', ''))
    if not m:
        return
    if os.environ.get('GITHUB_ACTIONS'):
        print(f'::error file={ort}::{m}', flush=True)
    raise SystemExit(f'ABBRUCH {m}\nNichts gepostet. Caption auf Englisch ändern oder den Ordner aus queue/ löschen.')


def build_container(folder: Path, meta: dict) -> str:
    """Legt den Container an und wartet, bis er fertig ist. Veröffentlicht nichts."""
    sprachsperre(folder, meta)
    ig = ig_user_id()
    paths = media_paths(folder, meta)
    if not meta.get('images'):
        url = url_for(paths[0])
        print(f'  Bild: {url}', flush=True)
        container = call('POST', f'{ig}/media', {'image_url': url, 'caption': meta['caption']})['id']
    else:
        children = []
        for rel in paths:
            url = url_for(rel)
            print(f'  Slide: {url}', flush=True)
            child = call('POST', f'{ig}/media', {'image_url': url, 'is_carousel_item': 'true'})['id']
            wait_finished(child)
            children.append(child)
        container = call('POST', f'{ig}/media', {
            'media_type': 'CAROUSEL', 'children': ','.join(children), 'caption': meta['caption']})['id']
    wait_finished(container)
    return container


def publish(folder: Path, meta: dict) -> str:
    container = build_container(folder, meta)
    return call('POST', f'{ig_user_id()}/media_publish', {'creation_id': container})['id']


def main():
    now = datetime.now(timezone.utc)
    due = due_posts(now)
    waiting = sum(1 for p in QUEUE.iterdir() if p.is_dir()) - len(due)
    print(f'fällig: {len(due)}, wartet noch: {waiting}')
    for at, d, _ in due:
        print(f'  {d.name}  (geplant {at.isoformat()})')
    for d in sorted(p for p in QUEUE.iterdir() if p.is_dir()):
        m = sprache.meldung(f'{d.relative_to(REPO).as_posix()}/post.json',
                            json.loads((d / 'post.json').read_text(encoding='utf-8')).get('caption', ''))
        if m:
            print(f'FEHLER {m}')
    if '--check' in sys.argv:
        # Baut den Container für den nächsten Beitrag in queue/, fällig oder nicht, und
        # veröffentlicht nichts. Prüft Token, Bild-URLs und Karussell. Container verfallen nach 24 h.
        nxt = sorted(p for p in QUEUE.iterdir() if p.is_dir())
        if not nxt:
            print('queue/ ist leer, nichts zu prüfen')
            return 0
        meta = json.loads((nxt[0] / 'post.json').read_text(encoding='utf-8'))
        print(f'\nprüfe {nxt[0].name} ({len(media_paths(nxt[0], meta))} Bilder), ohne zu veröffentlichen', flush=True)
        print(f'Container fertig: {build_container(nxt[0], meta)}')
        return 0
    if not due or '--publish' not in sys.argv:
        return 0

    at, folder, meta = due[0]
    print(f'\nposte {folder.name}', flush=True)
    media_id = publish(folder, meta)
    meta.update({'media_id': media_id, 'published_at': datetime.now(timezone.utc).isoformat()})
    (folder / 'post.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    POSTED.mkdir(exist_ok=True)
    shutil.move(str(folder), str(POSTED / folder.name))
    print(f'veröffentlicht: {media_id}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

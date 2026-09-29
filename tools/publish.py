"""Postet fällige Beiträge aus queue/ auf Instagram und verschiebt sie nach posted/.

Ein Beitrag ist ein Ordner in queue/ mit zwei Dateien:

    queue/2026-10-05-0730-phone/
        post.json    {"publish_at": "2026-10-05T07:30:00+02:00", "caption": "..."}
        image.jpg    JPEG, 1080 px breit. Instagram nimmt nur JPEG.

Ablauf pro fälligem Beitrag, über die Instagram API mit Instagram-Login:

1. Media-Container anlegen: POST /{ig-user-id}/media mit image_url und caption.
   image_url zeigt auf die Datei in diesem öffentlichen Repo, festgenagelt auf
   den Commit, damit sich die URL bis zum Posten nicht ändert.
2. Warten, bis der Container FINISHED meldet.
3. Veröffentlichen: POST /{ig-user-id}/media_publish.
4. Ergebnis in post.json schreiben, Ordner nach posted/ verschieben.

Die API kennt kein eigenes Planen, und ein Container verfällt nach 24 Stunden.
Deshalb läuft dieses Skript stündlich und postet, was fällig ist.

Pro Lauf höchstens ein Beitrag. Hat sich etwas angestaut, weil Läufe
ausgefallen sind, kommt der Rest in den folgenden Stunden. So entsteht nie ein
Schwall von Posts.

Umgebung:
    IG_USER_ID       Instagram-User-ID des Creator-Kontos
    IG_ACCESS_TOKEN  langlebiger Token, erneuert von refresh-token.yml
    IG_API           Basis-URL, Standard https://graph.instagram.com
    IMAGE_BASE_URL   Basis für image_url, Standard raw.githubusercontent.com
                     mit GITHUB_REPOSITORY und GITHUB_SHA

Aufruf:
    python3 tools/publish.py            # zeigt nur, was fällig ist
    python3 tools/publish.py --publish  # postet den nächsten fälligen Beitrag
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

REPO = Path(__file__).resolve().parent.parent
QUEUE = REPO / 'queue'
POSTED = REPO / 'posted'
API = os.environ.get('IG_API', 'https://graph.instagram.com').rstrip('/')


def due_posts(now: datetime) -> list[tuple[datetime, Path, dict]]:
    out = []
    for d in sorted(p for p in QUEUE.iterdir() if p.is_dir()):
        meta = json.loads((d / 'post.json').read_text(encoding='utf-8'))
        at = datetime.fromisoformat(meta['publish_at'])
        if at.tzinfo is None:
            raise ValueError(f'{d.name}: publish_at braucht eine Zeitzone, z. B. +02:00')
        if not (d / meta.get('image', 'image.jpg')).exists():
            raise FileNotFoundError(f'{d.name}: Bild fehlt')
        if at <= now:
            out.append((at, d, meta))
    return sorted(out, key=lambda x: x[0])


def image_url(folder: Path, meta: dict) -> str:
    base = os.environ.get('IMAGE_BASE_URL')
    if not base:
        repo = os.environ['GITHUB_REPOSITORY']
        ref = os.environ.get('GITHUB_SHA', 'main')
        base = f'https://raw.githubusercontent.com/{repo}/{ref}'
    rel = folder.relative_to(REPO) / meta.get('image', 'image.jpg')
    return f'{base.rstrip("/")}/{urllib.parse.quote(rel.as_posix())}'


def call(method: str, path: str, params: dict) -> dict:
    params = {**params, 'access_token': os.environ['IG_ACCESS_TOKEN']}
    data = urllib.parse.urlencode(params).encode()
    url = f'{API}/{path}'
    if method == 'GET':
        req = urllib.request.Request(f'{url}?{data.decode()}')
    else:
        req = urllib.request.Request(url, data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        raise RuntimeError(f'{method} {path}: HTTP {e.code} {body}') from None


def publish(folder: Path, meta: dict) -> str:
    ig = os.environ['IG_USER_ID']
    url = image_url(folder, meta)
    print(f'  Bild: {url}', flush=True)
    container = call('POST', f'{ig}/media', {'image_url': url, 'caption': meta['caption']})['id']
    for _ in range(30):
        status = call('GET', container, {'fields': 'status_code'}).get('status_code')
        if status == 'FINISHED':
            break
        if status in ('ERROR', 'EXPIRED'):
            raise RuntimeError(f'Container {container}: {status}')
        time.sleep(5)
    else:
        raise RuntimeError(f'Container {container}: nach 150 s nicht fertig')
    return call('POST', f'{ig}/media_publish', {'creation_id': container})['id']


def main():
    now = datetime.now(timezone.utc)
    due = due_posts(now)
    waiting = sum(1 for p in QUEUE.iterdir() if p.is_dir()) - len(due)
    print(f'fällig: {len(due)}, wartet noch: {waiting}')
    for at, d, _ in due:
        print(f'  {d.name}  (geplant {at.isoformat()})')
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

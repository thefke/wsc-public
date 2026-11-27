"""Sperre für deutsche Captions auf @thefke.

Regel (Thomas, 31.10.2026): Alles, was Thomas auf Deutsch formuliert, geht auf
@thomas.hefke, nie auf @thefke. @thefke ist der englische Buch-Account. Dieses
Modul erkennt deutsche Captions, bevor sie gepostet oder eingeplant werden
(Ja von Thomas, 27.11.2026, Vorschlag V20).

Erkennung ohne Pakete: Gezählt werden typisch deutsche Funktionswörter und
Wörter mit Umlaut oder ß gegen typisch englische Funktionswörter. Wörter, die
in beiden Sprachen vorkommen (in, an, so, was, will, die, man ...), zählen nicht.
Nicht gezählt werden Hashtags, @-Namen, Links und alles in Anführungszeichen
oder Sternchen: Dort stehen Buchtitel und Zitate, die auf Deutsch sein dürfen.

Deutsch heißt: mindestens MIN_DE deutsche Signale und ein deutscher Anteil von
mindestens SCHWELLE an allen gezählten Signalen. Geeicht am Bestand vom
27.11.2026: Alle 197 Captions in plan/, queue/ und posted/ liegen bei
0 % deutsch. Ohne die Ausnahme für Anführungszeichen läge die höchste bei 10 %
(2026-12-22-greatest-explorers, Zitat von Hape Kerkeling).

Aufruf aus dem Repo-Root:
    python3 tools/sprache.py                 # prüft plan/, queue/ und posted/
    python3 tools/sprache.py plan/<ordner>/caption.txt queue/<ordner>/post.json
Exit 1, sobald eine Caption deutsch ist.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHWELLE = 0.5
MIN_DE = 3

DE = set('''
der den dem des das und ist sind nicht nichts ich du er wir ihr sie es
mit für auf ein eine einen einem einer eines kein keine keinen keiner zu zum zur
von vom sich mich dich mir dir uns euch wie auch aber noch wenn dass daß weil denn ob
bei oder nur schon mehr sehr im ins aus nach über unter vor durch gegen ohne
mein meine meinen meinem meiner dein deine deinen deinem deiner sein seine seinen ihre ihren unser unsere
jetzt hier immer mal doch wer wird werden wurde kann können muss müssen soll sollte darf
habe hast haben hatte hätte bist seid gibt gab dann dieser diese dieses diesen jeder jede jedes
warum welche welcher welches weiß wieder heute ganz alles etwas viel viele wirklich einfach
lesen liest gelesen buch bücher buches gerade selbst eigentlich
'''.split())

EN = set('''
the and is are of to a you your yours that it its it's for with this these those not
what my be on have has had i me i'm i've do does don't can can't from they them their there
we our us but or one if all how when just more about who which been than then into out up
would should could every only he she his her him books book read reading reader
'''.split())

# Hashtags, @-Namen und Links zählen nicht, Text in Anführungszeichen oder Sternchen auch nicht.
ENTFERNEN = re.compile(
    r'https?://\S+|www\.\S+|[#@][\w.]+'
    r'|“[^”\n]*”|„[^“”\n]*[“”]|"[^"\n]*"|‚[^‘’\n]*[‘’]|«[^»\n]*»|»[^«\n]*«'
    r'|\*[^*\n]+\*|_[^_\n]+_'
)
WORT = re.compile(r"[a-zäöüß]+(?:'[a-z]+)?")
UMLAUT = re.compile('[äöüß]')

HINWEIS = ('@thefke postet nur Englisch. Deutsche Texte gehören auf @thomas.hefke '
           '(Marke Thomas Hefke, Regel vom 31.10.2026).')


def zaehlen(text: str) -> dict:
    """Zählt deutsche und englische Signale. Ergebnis mit de, en, anteil und deutsch."""
    rest = ENTFERNEN.sub(' ', text).lower().replace('’', "'")
    de = en = 0
    for w in WORT.findall(rest):
        if w in EN:
            en += 1
        elif w in DE or UMLAUT.search(w):
            de += 1
    gesamt = de + en
    anteil = de / gesamt if gesamt else 0.0
    return {'de': de, 'en': en, 'anteil': anteil, 'deutsch': de >= MIN_DE and anteil >= SCHWELLE}


def ist_deutsch(text: str) -> bool:
    return zaehlen(text)['deutsch']


def meldung(ort: str, text: str) -> str | None:
    """Fehlermeldung für eine deutsche Caption, sonst None."""
    z = zaehlen(text)
    if not z['deutsch']:
        return None
    return (f'{ort}: Caption ist deutsch ({z["de"]} deutsche, {z["en"]} englische Signalwörter, '
            f'Anteil deutsch {z["anteil"]:.0%}). {HINWEIS}')


def caption_aus(pfad: Path) -> str:
    if pfad.suffix == '.json':
        return json.loads(pfad.read_text(encoding='utf-8')).get('caption', '')
    return pfad.read_text(encoding='utf-8')


def bestand() -> list[Path]:
    out = sorted(REPO.glob('plan/*/caption.txt'))
    for base in ('queue', 'posted'):
        out += sorted(REPO.glob(f'{base}/*/post.json'))
    return out


def main() -> int:
    pfade = [Path(a) for a in sys.argv[1:]] or bestand()
    treffer = 0
    for p in pfade:
        m = meldung(str(p.relative_to(REPO) if p.is_absolute() and REPO in p.parents else p), caption_aus(p))
        if m:
            treffer += 1
            print(f'FEHLER {m}')
    print(f'geprüft: {len(pfade)}, deutsch: {treffer}')
    return 1 if treffer else 0


if __name__ == '__main__':
    sys.exit(main())

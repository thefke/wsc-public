"""Tests für tools/sprache.py, ohne Netz und ohne Pakete.

Aufruf aus dem Repo-Root: python3 tools/test_sprache.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sprache  # noqa: E402

DEUTSCH = '''30 Ausreden. 30 Bücher.

„Ich habe keine Zeit.“
„Ich bin noch nicht so weit.“

Die meisten von uns nutzen mindestens eine davon.
Für jede gibt es ein Buch, das sie auseinandernimmt.

Welche nutzt du? Sei ehrlich.

#bücher #bookstagram'''

DEUTSCH_KURZ = 'Welches Buch hat dich dieses Jahr wirklich verändert?'

ENGLISCH = '''30 excuses.
30 books.

"I don't have time."
"I'm not ready yet."

Most of us use at least one.
Each one has a book that takes it apart.

Which one do you use? Be honest.

Books from this post: link in bio.

#books #bookstagram #bookrecommendations'''

ENGLISCH_MIT_DEUTSCHEM_TITEL = '''5 books that changed how I think about money.

1. Der Weg zum Glück, by a German author I read on a train.
2. Die Kunst des klaren Denkens by Rolf Dobelli.
3. Über das Geld und die Zeit, still my favourite.

Which one is on your shelf?

Books from this post: link in bio.

#books #bookstagram'''

ENGLISCH_MIT_DEUTSCHEM_ZITAT = '''6 lessons from people who left the map behind.

Hape Kerkeling on the Camino:
“Jeder Mensch sucht nach Halt. Dabei liegt der einzige Halt im Loslassen.”
Everyone looks for something to hold on to. The only hold is letting go.

Whose lesson do you need?

#bookstagram #books'''

ENGLISCH_MIT_TITELN_IN_ANFUEHRUNGSZEICHEN = '''Two German classics on my shelf:
„Die Verwandlung“ and „Der Prozess“ and *Über die Freiheit des Menschen*.

Read them in English if you can.'''


class Erkennung(unittest.TestCase):
    def test_deutsch(self):
        z = sprache.zaehlen(DEUTSCH)
        self.assertTrue(z['deutsch'], z)

    def test_deutsch_kurz(self):
        self.assertTrue(sprache.ist_deutsch(DEUTSCH_KURZ), sprache.zaehlen(DEUTSCH_KURZ))

    def test_englisch(self):
        z = sprache.zaehlen(ENGLISCH)
        self.assertFalse(z['deutsch'], z)
        self.assertEqual(z['de'], 0)

    def test_englisch_mit_deutschem_buchtitel(self):
        z = sprache.zaehlen(ENGLISCH_MIT_DEUTSCHEM_TITEL)
        self.assertFalse(z['deutsch'], z)

    def test_englisch_mit_deutschem_zitat(self):
        z = sprache.zaehlen(ENGLISCH_MIT_DEUTSCHEM_ZITAT)
        self.assertFalse(z['deutsch'], z)
        self.assertEqual(z['de'], 0, 'Zitat in Anführungszeichen zählt nicht')

    def test_titel_in_anfuehrungszeichen_zaehlen_nicht(self):
        z = sprache.zaehlen(ENGLISCH_MIT_TITELN_IN_ANFUEHRUNGSZEICHEN)
        self.assertEqual(z['de'], 0, z)

    def test_hashtags_zaehlen_nicht(self):
        self.assertEqual(sprache.zaehlen('#bücher #lesen #dasbuch @thomas.hefke')['de'], 0)

    def test_leer(self):
        self.assertFalse(sprache.ist_deutsch(''))

    def test_meldung_nennt_ort_und_konto(self):
        m = sprache.meldung('plan/2026-12-01-test/caption.txt', DEUTSCH)
        self.assertIn('plan/2026-12-01-test/caption.txt', m)
        self.assertIn('@thomas.hefke', m)
        self.assertIsNone(sprache.meldung('x', ENGLISCH))


class Bestand(unittest.TestCase):
    def test_alle_captions_im_repo_sind_englisch(self):
        pfade = sprache.bestand()
        if not pfade:
            self.skipTest('kein Bestand im Checkout')
        deutsch = [str(p.relative_to(sprache.REPO)) for p in pfade
                   if sprache.ist_deutsch(sprache.caption_aus(p))]
        self.assertEqual(deutsch, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)

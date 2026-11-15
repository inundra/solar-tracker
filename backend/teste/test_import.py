"""Teste pentru migrări și importul CSV, pe o bază PostgreSQL + PostGIS reală.

Rulare (ATENȚIE: baza de test e golită, folosiți una separată):
    TEST_DATABASE_URL=postgresql://mwitness:mwitness@localhost:5432/mwitness_test \\
        python -m unittest discover -s backend/teste -v

Fără TEST_DATABASE_URL, testele sunt sărite.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import psycopg  # noqa: E402

import importa_csv  # noqa: E402
import migreaza  # noqa: E402

DSN = os.environ.get("TEST_DATABASE_URL")
EXEMPLE = importa_csv.REPO / "validare"

ANTET_PARCURI = ",".join(importa_csv.valideaza_csv.COLOANE_PARCURI)
ANTET_STADII = ",".join(importa_csv.valideaza_csv.COLOANE_STADII)


def parc(pid="GJ-001", lat="44.95", lon="23.10", are_poligon="nu", mwp="", stadiu="santier"):
    sursa_mw = "https://exemplu.ro" if mwp else ""
    return (f"{pid},Parc test {pid},{pid.split('-')[0]},,{lat},{lon},{are_poligon},{mwp},,{sursa_mw},"
            f",,,,,track,{stadiu},2026-11-13,https://exemplu.ro,tester,")


def poligon_in_jurul(lat: float, lon: float, d: float = 0.002) -> dict:
    inel = [[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"parc_id": "GJ-001"}, "geometry": {"type": "Polygon", "coordinates": [inel]}}
    ]}


@unittest.skipUnless(DSN, "setați TEST_DATABASE_URL ca să rulați testele cu baza de date")
class TestImport(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(DSN, autocommit=True)
        self.conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        self.conn.autocommit = False
        migreaza.aplica(self.conn)
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "proiecte_cartate").mkdir()

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.dir)

    def scrie(self, nume: str, antet: str, linii: list[str]) -> Path:
        cale = self.dir / nume
        cale.write_text("\n".join([antet, *linii]) + "\n", encoding="utf-8")
        return cale

    def numar(self, tabel: str) -> int:
        return self.conn.execute(f"SELECT count(*) FROM {tabel}").fetchone()[0]

    def test_migrarile_ruleaza_o_singura_data(self):
        self.assertEqual(migreaza.aplica(self.conn), [])

    def test_exemplele_se_importa_fara_duplicate(self):
        p, s = EXEMPLE / "exemplu_parcuri.csv", EXEMPLE / "exemplu_stadii_lunare.csv"
        prima = importa_csv.importa(self.conn, p, s)
        a_doua = importa_csv.importa(self.conn, p, s)
        self.assertEqual((prima[0].inserate, prima[1].inserate), (2, 6))
        self.assertEqual((a_doua[0].neschimbate, a_doua[1].neschimbate), (2, 6))
        self.assertEqual(self.numar("parcuri"), 2)
        self.assertEqual(self.numar("stadii_adevar"), 6)
        lat, lon, produs = self.conn.execute(
            "SELECT lat, lon, stadiu_produs FROM v_parcuri WHERE parc_id = 'DJ-001'").fetchone()
        self.assertAlmostEqual(lat, 44.391234)
        self.assertAlmostEqual(lon, 23.712345)
        self.assertEqual(produs, "în construcție")

    def test_schimbarea_unei_valori_actualizeaza_linia(self):
        cale = self.scrie("parcuri.csv", ANTET_PARCURI, [parc(stadiu="santier")])
        importa_csv.importa(self.conn, cale, None)
        cale = self.scrie("parcuri.csv", ANTET_PARCURI, [parc(stadiu="panouri", mwp="12.5")])
        (rez,) = importa_csv.importa(self.conn, cale, None)
        self.assertEqual(rez.actualizate, 1)
        self.assertEqual(self.conn.execute("SELECT stadiu_curent, mwp FROM parcuri").fetchone(), ("panouri", 12.5))

    def test_poligonul_se_incarca_din_geojson(self):
        (self.dir / "proiecte_cartate" / "GJ-001.geojson").write_text(json.dumps(poligon_in_jurul(44.95, 23.10)))
        cale = self.scrie("parcuri.csv", ANTET_PARCURI, [parc(are_poligon="da")])
        (rez,) = importa_csv.importa(self.conn, cale, None)
        self.assertEqual(rez.avertismente, [])
        tip, ha = self.conn.execute(
            "SELECT GeometryType(poligon), suprafata_ha FROM v_parcuri").fetchone()
        self.assertEqual(tip, "MULTIPOLYGON")
        self.assertGreater(ha, 5)
        (rez,) = importa_csv.importa(self.conn, cale, None)
        self.assertEqual(rez.neschimbate, 1)

    def test_punct_departe_de_poligon_da_avertisment(self):
        (self.dir / "proiecte_cartate" / "GJ-001.geojson").write_text(json.dumps(poligon_in_jurul(44.95, 23.30)))
        cale = self.scrie("parcuri.csv", ANTET_PARCURI, [parc(are_poligon="da")])
        (rez,) = importa_csv.importa(self.conn, cale, None)
        self.assertTrue(any("de poligon" in a for a in rez.avertismente))

    def test_csv_cu_erori_nu_scrie_nimic(self):
        cale = self.scrie("parcuri.csv", ANTET_PARCURI, [parc(), parc(pid="GJ-002", stadiu="aproape_gata")])
        with self.assertRaises(SystemExit):
            importa_csv.importa(self.conn, cale, None)
        self.assertEqual(self.numar("parcuri"), 0)

    def test_simularea_nu_scrie_nimic(self):
        cale = self.scrie("parcuri.csv", ANTET_PARCURI, [parc()])
        (rez,) = importa_csv.importa(self.conn, cale, None, verifica=True)
        self.assertEqual(rez.inserate, 1)
        self.assertEqual(self.numar("parcuri"), 0)
        self.assertEqual(self.numar("importuri"), 0)

    def test_stadiile_lipsa_se_sterg_doar_la_cerere(self):
        p = self.scrie("parcuri.csv", ANTET_PARCURI, [parc()])
        luni = [f"GJ-001,2025-0{m},nesigur,,,,tester," for m in (1, 2, 3)]
        importa_csv.importa(self.conn, p, self.scrie("stadii.csv", ANTET_STADII, luni))
        mai_putine = self.scrie("stadii.csv", ANTET_STADII, luni[:2])
        _, rez = importa_csv.importa(self.conn, p, mai_putine)
        self.assertEqual(self.numar("stadii_adevar"), 3)
        self.assertTrue(rez.avertismente)
        _, rez = importa_csv.importa(self.conn, p, mai_putine, sterge_lipsa=True)
        self.assertEqual(rez.sterse, 1)
        self.assertEqual(self.numar("stadii_adevar"), 2)

    def test_rezultatele_pipeline_se_compara_cu_adevarul(self):
        importa_csv.importa(self.conn, EXEMPLE / "exemplu_parcuri.csv", EXEMPLE / "exemplu_stadii_lunare.csv")
        with self.conn.transaction():
            self.conn.execute(
                "INSERT INTO stadii_pipeline (parc_id, luna, versiune_model, stadiu, incredere) VALUES"
                " ('DJ-001', '2025-03-01', 'v0', 'santier', 0.8),"
                " ('DJ-001', '2025-05-01', 'v0', 'gata', 0.6)")
        rez = self.conn.execute(
            "SELECT to_char(luna, 'YYYY-MM'), corect FROM v_comparatie_stadii ORDER BY luna").fetchall()
        self.assertEqual(rez, [("2025-03", True), ("2025-05", False)])


if __name__ == "__main__":
    unittest.main()

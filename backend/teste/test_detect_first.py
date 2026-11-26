"""Teste pentru planul detect-first: ATR-uri, detecții, legarea lor, vederile pe județe și API-ul.

Rulare (ATENȚIE: baza de test e golită, folosiți una separată):
    TEST_DATABASE_URL=postgresql://mwitness:mwitness@localhost:5432/mwitness_test \\
        python -m unittest discover -s backend/teste -v
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

import comun  # noqa: E402
import extrage_atr_pdf  # noqa: E402
import importa_atr  # noqa: E402
import importa_csv  # noqa: E402
import importa_detectii  # noqa: E402
import importa_judete  # noqa: E402
import importa_stadii_pipeline  # noqa: E402
import leaga_atr  # noqa: E402
import migreaza  # noqa: E402

DSN = os.environ.get("TEST_DATABASE_URL")
EXEMPLE = importa_csv.REPO / "backend" / "date_brute"
VALIDARE = importa_csv.REPO / "validare"


def patrat(lon: float, lat: float, d: float) -> dict:
    return {"type": "Polygon", "coordinates": [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d],
                                                [lon - d, lat + d], [lon - d, lat - d]]]}


def detectie(did: str, lon: float, lat: float, d: float = 0.003, **props) -> dict:
    return {"type": "Feature", "geometry": patrat(lon, lat, d),
            "properties": {"detectie_id": did, "stadiu_curent": "santier", "sursa": "pipeline"} | props}


class TestFaraBaza(unittest.TestCase):
    def test_judete_dupa_nume_sau_cod(self):
        for v, cod in [("Dolj", "DJ"), ("DOLJ", "DJ"), ("dj", "DJ"), ("Dâmbovița", "DB"), ("Dambovita", "DB"),
                       ("Județul Bistrița-Năsăud", "BN"), ("Municipiul București", "B"), ("Caras Severin", "CS")]:
            self.assertEqual(comun.cod_judet(v), cod, v)
        self.assertIsNone(comun.cod_judet("Atlantida"))

    def test_numere_si_date(self):
        self.assertEqual(comun.numar("45,5"), 45.5)
        self.assertEqual(comun.numar("1.234,5 MW"), 1234.5)
        self.assertEqual(comun.numar("1,234.5"), 1234.5)
        self.assertEqual(str(comun.data("17.05.2023")), "2023-05-17")
        self.assertEqual(str(comun.data("12.2026")), "2026-12-01")
        self.assertEqual(comun.cui("RO 123 456"), "123456")

    def test_tehnologia_se_ghiceste_din_titular(self):
        self.assertEqual(importa_atr.ghiceste_tehnologia("Corbii Mari Solar Plant SRL"), "fotovoltaic")
        self.assertEqual(importa_atr.ghiceste_tehnologia("Baterii Sud BESS SRL"), "stocare")
        self.assertEqual(importa_atr.ghiceste_tehnologia("Solar & Storage Romania SRL"), "hibrid")
        self.assertEqual(importa_atr.ghiceste_tehnologia("Energie Verde SRL"), "necunoscuta")

    def test_tabelul_din_pdf_se_recunoaste_dupa_antet(self):
        tabele = [
            [["Nr. crt", "Nr. și dată ATR", "Titular", "CUI", "Putere aprobată (MW)", "Județ", "Operator", "Etapa",
              "Data estimată PIF"],
             ["1", "1234 / 17.05.2023", "Solarist Tismana 2 SRL", "RO 12345678", "45,5", "GORJ", "DEO", "ATR", "12.2026"],
             ["", "", "TOTAL", "", "45,5", "", "", "", ""]],
            [["2", "55/03.02.2024", "Corbii Mari\nSolar Plant SRL", "", "10", "Dâmbovița", "Transelectrica", "", ""]],
        ]
        randuri = list(extrage_atr_pdf.randuri_din_tabele(tabele))
        self.assertEqual(len(randuri), 2)
        self.assertEqual((randuri[0]["numar_atr"], randuri[0]["data_atr"]), ("1234", "17.05.2023"))
        self.assertEqual((randuri[1]["numar_atr"], randuri[1]["data_atr"]), ("55", "03.02.2024"))
        self.assertEqual(randuri[1]["titular"], "Corbii Mari Solar Plant SRL")

    def test_scorul_de_legatura(self):
        self.assertAlmostEqual(leaga_atr.scor_mw(48, 40, 1.2), 1.0)
        self.assertEqual(leaga_atr.scor_mw(5, 120, 1.2), 0.0)
        self.assertEqual(leaga_atr.scor_loc("Corbii Mari", "CORBII MARI SOLAR PLANT SRL", None), 1.0)
        self.assertEqual(leaga_atr.scor_loc("Ișalnița", "Exemplu Isalnita Solar SRL", None), 1.0)
        self.assertEqual(leaga_atr.scor_loc("Titu", "Alt Dezvoltator SRL", None), 0.0)


    def test_judete_scrise_in_lista_reala(self):
        for v, coduri in [("Dambovta", ["DB"]), ("BISTRITA NASAU", ["BN"]), ("Caraș – Severin", ["CS"]),
                          ("Timisoara", ["TM"]), ("ATIMIS", ["TM"]), ("BBUUCCUURREESSTTII", ["B"]),
                          ("Arad si Timis", ["AR", "TM"]), ("Dâmbovița, Ilfov", ["DB", "IF"]),
                          ("Gorj Oltenia S.A.)", ["GJ"]), ("Atlantida", [])]:
            self.assertEqual(comun.judete_din_text(v), coduri, v)
        self.assertIsNone(comun.cod_judet("Dambovta"))  # fără aproximativ=True rămâne strict

    def test_pif_din_text(self):
        from datetime import date
        for v, asteptat in [
            ("PIF estimat la 31.12.2027", ("estimat", date(2027, 12, 31), 2027)),
            ("Pif estimat 2033", ("estimat", None, 2033)),
            ("PIF/11.04.2012", ("realizat", date(2012, 4, 11), 2012)),
            ("PIF 2014", ("realizat", None, 2014)),
            ("Finalizat cu PIF", ("realizat", None, None)),
            ("Anulat", ("anulat", None, None)),
            ("retehnologizat", ("retehnologizat", None, None)),
            ("PIF/03.06.2013(2.860 MW).", ("realizat", date(2013, 6, 3), 2013)),
            ("PIF estimat la 31.06.2026", ("estimat", date(2026, 6, 30), 2026)),
            ("12.2026", ("estimat", date(2026, 12, 1), 2026)),
            ("", (None, None, None)),
        ]:
            self.assertEqual(comun.pif(v), asteptat, v)

    def test_cui_si_mw_murdare(self):
        self.assertEqual(comun.cui_tolerant("L. 45427207"), ("45427207", True))
        self.assertEqual(comun.cui_tolerant("ROMANIA SRL 22160860"), ("22160860", True))
        self.assertEqual(comun.cui_tolerant("RO 123456"), ("123456", False))
        self.assertEqual(comun.mw_tolerant("45,5"), (45.5, False))
        self.assertEqual(comun.mw_tolerant("HSA0.69"), (0.69, True))
        self.assertEqual(comun.mw_tolerant("3S2R1L7).16"), (None, True))
        self.assertEqual(str(comun.data("10/21/2025")), "2025-10-21")

    def test_pdf_cu_text_care_trece_peste_celula(self):
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            self.skipTest("reportlab nu e instalat")
        import pdfplumber
        cale = Path(tempfile.mkdtemp()) / "atr.pdf"
        c = canvas.Canvas(str(cale), pagesize=(600, 300))
        xs, ys = [20, 200, 300, 400, 560], [250, 220, 190]
        for x in xs:
            c.line(x, ys[-1], x, ys[0])
        for y in ys:
            c.line(xs[0], y, xs[-1], y)
        for x, h in zip(xs, ["Titular", "Judet", "Putere MW", "Data PIF"]):
            c.drawString(x + 3, 230, h)
        c.drawString(23, 200, "Exemplu Isalnita Solar")
        c.drawString(203, 200, "Gorj")
        c.drawString(215, 201, "Oltenia SA)")          # text vărsat peste celula județului
        c.drawString(303, 200, "12.5")
        c.drawString(403, 200, "PIF 2014")
        c.drawString(403.3, 200, "PIF 2014")            # literă dublată (text îngroșat)
        c.save()
        with pdfplumber.open(cale) as doc:
            tabele = [t for p in doc.pages for t in extrage_atr_pdf.tabele_din_pagina(p)]
        (rand,) = list(extrage_atr_pdf.randuri_din_tabele(tabele))
        self.assertEqual(rand["data_pif"], "PIF 2014")
        self.assertEqual(comun.judete_din_text(rand["judet"]), ["GJ"])
        shutil.rmtree(cale.parent)


@unittest.skipUnless(DSN, "setați TEST_DATABASE_URL ca să rulați testele cu baza de date")
class TestDetectFirst(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(DSN, autocommit=True)
        self.conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        self.conn.autocommit = False
        migreaza.aplica(self.conn)
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.dir)

    def unu(self, sql: str, params=None):
        return self.conn.execute(sql, params).fetchone()

    def geojson(self, *features: dict) -> Path:
        cale = self.dir / "detectii.geojson"
        cale.write_text(json.dumps({"type": "FeatureCollection", "features": list(features)}), encoding="utf-8")
        return cale

    def incarca_exemplele(self):
        rez = importa_atr.importa(self.conn, EXEMPLE / "exemplu_atr.csv")
        self.assertEqual(rez.erori, [])
        rez = importa_detectii.importa(self.conn, EXEMPLE / "exemplu_detectii.geojson")
        self.assertEqual(rez.erori, [])

    # --- ATR ---

    def test_atr_se_importa_fara_duplicate(self):
        prima = importa_atr.importa(self.conn, EXEMPLE / "exemplu_atr.csv")
        a_doua = importa_atr.importa(self.conn, EXEMPLE / "exemplu_atr.csv")
        self.assertEqual((prima.inserate, a_doua.neschimbate), (4, 4))
        self.assertEqual(self.unu("SELECT count(*), sum(mw) FROM atr"), (4, 200.5))
        self.assertEqual(self.unu("SELECT judet, cui, tehnologie, data_pif::text FROM atr WHERE numar = '1001/12.03.2023'"),
                         ("DJ", "11111111", "fotovoltaic", "2026-12-01"))
        self.assertEqual(self.unu("SELECT tehnologie FROM atr WHERE numar = '1003'"), ("stocare",))
        self.assertEqual(self.unu("SELECT count(*) FROM companii"), (4,))

    def test_liniile_nereparabile_se_sar_iar_restul_se_importa(self):
        cale = self.dir / "atr.csv"
        cale.write_text("numar_atr,titular,judet,mw,sursa\n1,Bun SRL,Dolj,10,x\n2,Rău SRL,Atlantida,5,x\n3,Fără MW SRL,DJ,,x\n",
                        encoding="utf-8")
        rez = importa_atr.importa(self.conn, cale)
        self.assertEqual((rez.erori, rez.linii, len(rez.respinse)), ([], 1, 2))
        self.assertEqual(self.unu("SELECT count(*) FROM atr"), (1,))
        iesire = importa_atr.scrie_respinse(rez, cale)
        self.assertIn("Atlantida", iesire.read_text(encoding="utf-8"))

    def test_cu_strict_orice_problema_opreste_importul(self):
        cale = self.dir / "atr.csv"
        cale.write_text("numar_atr,titular,judet,mw,sursa\n1,Bun SRL,Dolj,10,x\n2,Rău SRL,Atlantida,5,x\n", encoding="utf-8")
        rez = importa_atr.importa(self.conn, cale, strict=True)
        self.assertEqual(len(rez.erori), 1)
        self.assertEqual(self.unu("SELECT count(*) FROM atr"), (0,))

    def test_celulele_murdare_din_lista_reala(self):
        cale = self.dir / "atr.csv"
        cale.write_text(
            "numar_atr,data_atr,titular,cui,judet,mw,data_pif,sursa\n"
            "10,17.05.2023,Alfa Solar SRL,L. 45427207,Dambovta,\"12,5\",PIF estimat la 31.12.2027,x\n"
            "11,,Beta Energy SRL,SRL21566895,Arad si Timis,40,Pif estimat 2033,x\n"
            "12,,Gama PV SRL,RO 123456,BBUUCCUURREESSTTII,HSA0.69,PIF/11.04.2012,x\n"
            ",,Delta Solar SRL,,Timisoara,5,Finalizat cu PIF,x\n"
            "14,,Epsilon SRL,,Gorj Oltenia S.A.),3S2R1L7).16,Anulat,x\n"
            "15,10/21/2025,Zeta Solar SRL,,BISTRITA NASAU,7,PIF estimat la 31.06.2026,x\n",
            encoding="utf-8")
        rez = importa_atr.importa(self.conn, cale)
        self.assertEqual(rez.erori, [])
        self.assertEqual((rez.linii, len(rez.respinse)), (5, 1))
        self.assertIn("MW", rez.respinse[0]["motiv"])
        r = dict(zip(["judet", "cui", "mw", "stare", "data_pif", "an", "reparat"], self.unu(
            "SELECT judet, cui, mw::float8, stare_pif, data_pif::text, an_pif, reparat FROM atr WHERE numar = '10'")))
        self.assertEqual(r, {"judet": "DB", "cui": "45427207", "mw": 12.5, "stare": "estimat",
                             "data_pif": "2027-12-31", "an": 2027, "reparat": True})
        self.assertEqual(self.unu("SELECT judet, judete_secundare, stare_pif, data_pif, an_pif, pif_text FROM atr WHERE numar = '11'"),
                         ("AR", ["TM"], "estimat", None, 2033, "Pif estimat 2033"))
        self.assertEqual(self.unu("SELECT judet, mw::float8, stare_pif, an_pif FROM atr WHERE numar = '12'"),
                         ("B", 0.69, "realizat", 2012))
        self.assertEqual(self.unu("SELECT judet, stare_pif FROM atr WHERE titular = 'Delta Solar SRL'"), ("TM", "realizat"))
        self.assertTrue(self.unu("SELECT numar FROM atr WHERE titular = 'Delta Solar SRL'")[0].startswith("fara-numar-"))
        self.assertEqual(self.unu("SELECT judet, data_atr::text, data_pif::text FROM atr WHERE numar = '15'"),
                         ("BN", "2025-10-21", "2026-06-30"))
        # al doilea import: aceleași linii, fără duplicate (și numărul generat e stabil)
        a_doua = importa_atr.importa(self.conn, cale)
        self.assertEqual((a_doua.inserate, a_doua.neschimbate), (0, 5))
        self.assertEqual(self.unu("SELECT stare_pif FROM v_atr WHERE numar = '11'"), ("estimat",))

    # --- detecții ---

    def test_detectiile_si_jurnalul_se_importa(self):
        self.incarca_exemplele()
        rez = importa_detectii.importa(self.conn, EXEMPLE / "exemplu_detectii.geojson")
        self.assertEqual((rez.neschimbate, rez.jurnal), (3, 3))
        self.assertEqual(self.unu("SELECT count(*) FROM jurnal_detectii"), (3,))
        # datele lipsă vin din jurnal: prima imagine cu șantier, prima cu panouri, ultima decisivă
        self.assertEqual(self.unu("SELECT data_defrisare::text, data_module::text, data_stadiu::text FROM detectii"
                                  " WHERE detectie_id = 'DJ-EX-0001'"), ("2025-05-02", "2025-09-19", "2025-09-19"))
        ha, mwp, din_suprafata = self.unu("SELECT suprafata_ha, mwp, mwp_din_suprafata FROM v_detectii WHERE detectie_id = 'DJ-EX-0001'")
        self.assertTrue(40 < ha < 46)
        self.assertAlmostEqual(float(mwp), float(ha) * 0.7, delta=0.1)
        self.assertTrue(din_suprafata)

    def test_detectie_peste_un_parc_se_leaga_de_el(self):
        importa_csv.importa(self.conn, VALIDARE / "exemplu_parcuri.csv", None)
        lat, lon = self.unu("SELECT lat, lon FROM v_parcuri WHERE parc_id = 'DJ-001'")
        rez = importa_detectii.importa(self.conn, self.geojson(detectie("DJ-P-1", lon, lat, judet="DJ")))
        self.assertEqual(rez.legate_de_parcuri, 1)
        self.assertEqual(self.unu("SELECT parc_id FROM detectii"), ("DJ-001",))

    def test_fara_judet_si_fara_contur_e_eroare(self):
        rez = importa_detectii.importa(self.conn, self.geojson(detectie("X-1", 23.7, 44.3)))
        self.assertTrue(rez.erori)
        self.assertEqual(self.unu("SELECT count(*) FROM detectii"), (0,))

    def test_judetul_se_ia_din_contur(self):
        contur = self.dir / "judete.geojson"
        contur.write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"shapeName": "Dolj County", "shapeISO": "RO-DJ"},
             "geometry": patrat(23.6, 44.2, 0.5)}]}), encoding="utf-8")
        n, necunoscute = importa_judete.importa(self.conn, contur)
        self.assertEqual((n, necunoscute), (1, []))
        rez = importa_detectii.importa(self.conn, self.geojson(detectie("X-1", 23.7, 44.3)))
        self.assertEqual(rez.erori, [])
        self.assertEqual(self.unu("SELECT judet FROM detectii"), ("DJ",))

    def test_detectie_invalida_nu_scrie_nimic(self):
        rau = detectie("X-2", 23.7, 44.3, judet="DJ", stadiu_curent="aproape_gata")
        rez = importa_detectii.importa(self.conn, self.geojson(detectie("X-1", 23.7, 44.3, judet="DJ"), rau))
        self.assertEqual(len(rez.erori), 1)
        self.assertEqual(self.unu("SELECT count(*) FROM detectii"), (0,))

    def test_acelasi_parc_din_doua_surse_se_numara_o_data(self):
        importa_detectii.importa(self.conn, self.geojson(
            detectie("TZ-1", 23.7, 44.3, sursa="tz-sam", judet="DJ", stadiu_curent="gata")))
        importa_detectii.importa(self.conn, self.geojson(
            detectie("DJ-1", 23.7005, 44.3, sursa="pipeline", judet="DJ", stadiu_curent="gata"),
            detectie("DJ-2", 23.9, 44.1, sursa="pipeline", judet="DJ", stadiu_curent="gata")))
        self.assertEqual(self.unu("SELECT duplicat_al FROM detectii WHERE detectie_id = 'TZ-1'"), ("DJ-1",))
        self.assertEqual(self.unu("SELECT count(*) FROM detectii WHERE duplicat_al IS NOT NULL"), (1,))
        self.assertEqual(self.unu("SELECT nr_detectii FROM v_judete WHERE judet = 'DJ'"), (2,))

    # --- legarea de ATR-uri și vederile ---

    def test_candidatii_se_propun_si_se_confirma(self):
        self.incarca_exemplele()
        rez = leaga_atr.propune(self.conn)
        self.assertEqual(rez["DJ-EX-0001"], 1)
        titular, scor, motive = self.unu(
            "SELECT a.titular, l.scor, l.motive FROM legaturi_atr l JOIN atr a ON a.id = l.atr_id"
            " WHERE l.detectie_id = 'DJ-EX-0001'")
        self.assertEqual(titular, "Exemplu Isalnita Solar SRL")
        self.assertGreater(scor, 0.6)
        self.assertEqual(motive["loc"], 1.0)
        # ATR-ul de stocare nu e propus pentru o detecție fotovoltaică
        self.assertEqual(self.unu("SELECT count(*) FROM legaturi_atr l JOIN atr a ON a.id = l.atr_id"
                                  " WHERE a.tehnologie = 'stocare'"), (0,))

        atr_id = self.unu("SELECT id FROM atr WHERE titular = 'Exemplu Isalnita Solar SRL'")[0]
        leaga_atr.decide(self.conn, "DJ-EX-0001", atr_id, "confirmata", "tester", "APM Dolj")
        self.assertEqual(self.unu("SELECT atr_titular FROM v_detectii WHERE detectie_id = 'DJ-EX-0001'"),
                         ("Exemplu Isalnita Solar SRL",))
        self.assertEqual(self.unu("SELECT stare_teren, localitate FROM v_atr WHERE id = %s", (atr_id,)),
                         ("panouri", "Ișalnița"))
        self.assertEqual(self.unu("SELECT count(*) FROM v_atr WHERE stare_teren = 'fara_santier_legat'"), (3,))
        # o nouă propunere nu atinge legătura confirmată
        leaga_atr.propune(self.conn)
        self.assertEqual(self.unu("SELECT stare FROM legaturi_atr WHERE detectie_id = 'DJ-EX-0001'"), ("confirmata",))
        with self.assertRaises(psycopg.errors.UniqueViolation):
            leaga_atr.decide(self.conn, "DJ-EX-0001", atr_id + 1, "confirmata", "tester")

    def test_candidatul_respins_nu_revine(self):
        self.incarca_exemplele()
        leaga_atr.propune(self.conn)
        atr_id = self.unu("SELECT atr_id FROM legaturi_atr WHERE detectie_id = 'DJ-EX-0001'")[0]
        leaga_atr.decide(self.conn, "DJ-EX-0001", atr_id, "respinsa", "tester")
        leaga_atr.propune(self.conn)
        self.assertEqual(self.conn.execute(
            "SELECT stare FROM legaturi_atr WHERE detectie_id = 'DJ-EX-0001'").fetchall(), [("respinsa",)])

    def test_harta_pe_judete(self):
        self.incarca_exemplele()
        dj = self.unu("SELECT nr_atr, mw_aprobat, mw_aprobat_stocare, nr_detectii, mwp_construit, mwp_in_constructie,"
                      " nr_santiere, procent_vizibil_pe_teren FROM v_judete WHERE judet = 'DJ'")
        self.assertEqual(dj[:4], (3, 185, 25, 2))
        self.assertEqual(dj[4], 0)
        self.assertGreater(dj[5], 25)
        self.assertEqual(dj[6], 2)
        self.assertGreater(dj[7], 0)
        gj = self.unu("SELECT mwp_construit FROM v_judete WHERE judet = 'GJ'")[0]
        self.assertGreater(gj, 30)
        self.assertEqual(self.unu("SELECT count(*) FROM v_judete"), (42,))

    def test_stadiile_pipeline_pentru_parcuri(self):
        importa_csv.importa(self.conn, VALIDARE / "exemplu_parcuri.csv", VALIDARE / "exemplu_stadii_lunare.csv")
        cale = self.dir / "stadii_pipeline.csv"
        cale.write_text(
            "parc_id,luna,versiune_model,stadiu,incredere,sursa_imagine,data_imagine,id_imagine,cer_senin\n"
            "DJ-001,2025-03,v0.1,santier,0.8,sentinel-2,2025-03-14,S2B_TEST,0.9\n"
            "DJ-001,2025-05,v0.1,gata,0.6,,,,\n", encoding="utf-8")
        erori, ins, act = importa_stadii_pipeline.importa(self.conn, cale)
        self.assertEqual((erori, ins, act), ([], 2, 0))
        self.assertEqual(importa_stadii_pipeline.importa(self.conn, cale)[1:], (0, 2))
        self.assertEqual(self.unu("SELECT count(*) FROM observatii"), (1,))
        self.assertEqual(self.conn.execute("SELECT corect FROM v_comparatie_stadii ORDER BY luna").fetchall(),
                         [(True,), (False,)])
        cale.write_text("parc_id,luna,versiune_model,stadiu\nXX-999,2025-03,v0.1,santier\n", encoding="utf-8")
        self.assertTrue(importa_stadii_pipeline.importa(self.conn, cale)[0])


@unittest.skipUnless(DSN, "setați TEST_DATABASE_URL ca să rulați testele cu baza de date")
class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        import api

        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
            conn.autocommit = False
            migreaza.aplica(conn)
            importa_csv.importa(conn, VALIDARE / "exemplu_parcuri.csv", VALIDARE / "exemplu_stadii_lunare.csv")
            importa_atr.importa(conn, EXEMPLE / "exemplu_atr.csv")
            importa_detectii.importa(conn, EXEMPLE / "exemplu_detectii.geojson")
            leaga_atr.propune(conn)
            atr_id = conn.execute("SELECT id FROM atr WHERE titular LIKE 'Exemplu Isalnita%'").fetchone()[0]
            leaga_atr.decide(conn, "DJ-EX-0001", atr_id, "confirmata", "tester", "APM Dolj")
        cls.client = TestClient(api.creeaza_app(DSN))

    def get(self, url: str):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, r.text)
        return r

    def test_harta_se_serveste(self):
        self.assertIn("MWitness", self.get("/").text)

    def test_judete(self):
        fc = self.get("/api/judete").json()
        self.assertEqual(len(fc["features"]), 42)
        dj = next(f for f in fc["features"] if f["properties"]["judet"] == "DJ")
        self.assertEqual(dj["geometry"]["type"], "Point")
        self.assertEqual(dj["properties"]["nr_legate_de_atr"], 1)

    def test_parcuri_si_detectii(self):
        self.assertEqual(len(self.get("/api/parcuri").json()["features"]), 2)
        fc = self.get("/api/detectii?judet=dj").json()
        self.assertEqual({f["properties"]["detectie_id"] for f in fc["features"]}, {"DJ-EX-0001", "DJ-EX-0002"})
        self.assertEqual(len(self.get("/api/detectii?stadiu=gata").json()["features"]), 1)
        d = self.get("/api/detectii/DJ-EX-0001").json()
        self.assertEqual(len(d["jurnal"]), 3)
        self.assertEqual(d["legaturi_atr"][0]["stare"], "confirmata")
        p = self.get("/api/parcuri/DJ-001").json()
        self.assertEqual(len(p["stadii_adevar"]), 6)

    def test_cautare_atr(self):
        r = self.get("/api/atr?q=isalnita").json()
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["rezultate"][0]["stare_teren"], "panouri")
        self.assertEqual(self.get("/api/atr?judet=DJ").json()["total"], 3)
        self.assertEqual(self.get("/api/atr?cui=RO22222222").json()["total"], 1)
        self.assertEqual(self.get("/api/atr?stare_teren=fara_santier_legat").json()["total"], 3)
        self.assertEqual(len(self.get("/api/companii/11111111").json()["atr"]), 1)

    def test_rapoarte(self):
        t = self.get("/api/detectii/DJ-EX-0001/raport").text
        self.assertIn("S2B_MSIL2A_20250502_EXEMPLU", t)
        self.assertIn("Exemplu Isalnita Solar SRL", t)
        self.assertIn("Confirmat de tester", t)
        self.assertIn("# Raport de dovezi", self.get("/api/parcuri/DJ-001/raport").text)

    def test_404(self):
        self.assertEqual(self.client.get("/api/detectii/NU-EXISTA").status_code, 404)
        self.assertEqual(self.client.get("/api/parcuri/XX-999").status_code, 404)


if __name__ == "__main__":
    unittest.main()

"""API-ul MWitness și harta (issue #16), peste baza PostgreSQL + PostGIS.

Pornire:
    pip install -r backend/requirements.txt
    uvicorn api:app --app-dir backend/src --reload
    # harta: http://localhost:8000/   documentația API: http://localhost:8000/docs

Toate răspunsurile sunt doar citire. Geometriile sunt GeoJSON în WGS84.
"""

from __future__ import annotations

import os
from datetime import date

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from psycopg.rows import dict_row

import raport
from db import BACKEND, citeste_env

HARTA = BACKEND / "web" / "harta.html"


def _feature_collection(randuri: list[dict], camp_geometrie: str = "geometrie") -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": r.pop(camp_geometrie), "properties": r} for r in randuri
    ]}


def creeaza_app(dsn: str | None = None) -> FastAPI:
    app = FastAPI(title="MWitness API", version="0.2",
                  description="Parcuri solare, detecții satelitare, ATR-uri și harta aprobat vs construit.")

    def conexiune() -> psycopg.Connection:
        citeste_env()
        adresa = dsn or os.environ.get("DATABASE_URL")
        if not adresa:
            raise HTTPException(500, "Lipsește DATABASE_URL")
        return psycopg.connect(adresa, row_factory=dict_row)

    def interogare(sql: str, params: dict | tuple | None = None) -> list[dict]:
        with conexiune() as conn:
            return conn.execute(sql, params).fetchall()

    def unul(sql: str, params, mesaj: str) -> dict:
        randuri = interogare(sql, params)
        if not randuri:
            raise HTTPException(404, mesaj)
        return randuri[0]

    @app.get("/", include_in_schema=False)
    def harta():
        return FileResponse(HARTA)

    @app.get("/api/sanatate", summary="Starea bazei: câte înregistrări are fiecare tabel")
    def sanatate():
        return unul(
            "SELECT (SELECT count(*) FROM parcuri) AS parcuri, (SELECT count(*) FROM detectii) AS detectii,"
            " (SELECT count(*) FROM atr) AS atr, (SELECT count(*) FROM legaturi_atr WHERE stare = 'confirmata')"
            " AS legaturi_confirmate, (SELECT max(importat_la) FROM importuri) AS ultimul_import", None, "")

    @app.get("/api/judete", summary="Harta națională: MW aprobați (ATR) față de MWp detectați, pe județ")
    def judete():
        randuri = interogare(
            "SELECT ST_AsGeoJSON(coalesce(contur, ST_SetSRID(ST_MakePoint(lon, lat), 4326)), 5)::json AS geometrie,"
            " judet, nume, resedinta, lat, lon, nr_atr, mw_aprobat, mw_aprobat_fotovoltaic, mw_aprobat_stocare,"
            " nr_detectii, mwp_construit, mwp_in_constructie, nr_santiere, nr_legate_de_atr, procent_vizibil_pe_teren"
            " FROM v_judete ORDER BY mw_aprobat DESC, judet")
        return _feature_collection(randuri)

    @app.get("/api/parcuri", summary="Parcurile din setul de adevăr, cu stadiul curent")
    def parcuri(judet: str | None = None, rol: str | None = None):
        randuri = interogare(
            "SELECT ST_AsGeoJSON(coalesce(poligon, geom), 6)::json AS geometrie, parc_id, nume, judet, uat, lat, lon,"
            " mwp, mwac, detinator, cui, atr_numar, rol, stadiu_curent, stadiu_produs, data_verificare, suprafata_ha"
            " FROM v_parcuri WHERE (%(j)s::text IS NULL OR judet = %(j)s) AND (%(r)s::text IS NULL OR rol = %(r)s)"
            " ORDER BY parc_id", {"j": judet and judet.upper(), "r": rol})
        return _feature_collection(randuri)

    @app.get("/api/parcuri/{parc_id}", summary="Un parc: stadiile lunare (adevăr și pipeline) și detecțiile legate")
    def parc(parc_id: str):
        p = unul("SELECT ST_AsGeoJSON(coalesce(poligon, geom), 6)::json AS geometrie, * FROM v_parcuri WHERE parc_id = %s",
                 (parc_id,), f"Nu există parcul {parc_id}")
        p.pop("geom", None)
        p.pop("poligon", None)
        p["stadii_adevar"] = interogare(
            "SELECT to_char(luna, 'YYYY-MM') AS luna, stadiu, sursa_imagine, data_imagine, id_imagine, verificat_de, note"
            " FROM stadii_adevar WHERE parc_id = %s ORDER BY luna", (parc_id,))
        p["stadii_pipeline"] = interogare(
            "SELECT to_char(s.luna, 'YYYY-MM') AS luna, s.versiune_model, s.stadiu, s.incredere, s.mwp_estimat,"
            " s.mwp_min, s.mwp_max, o.data_imagine, o.sursa_imagine, o.id_imagine"
            " FROM stadii_pipeline s LEFT JOIN observatii o ON o.id = s.observatie_id"
            " WHERE s.parc_id = %s ORDER BY s.luna, s.versiune_model", (parc_id,))
        p["detectii"] = interogare(
            "SELECT detectie_id, sursa, stadiu_curent, mwp, atr_id, atr_titular FROM v_detectii WHERE parc_id = %s",
            (parc_id,))
        return p

    @app.get("/api/detectii", summary="Detecțiile (parcuri și șantiere găsite pe imagini), ca GeoJSON")
    def detectii(judet: str | None = None, stadiu: str | None = None, sursa: str | None = None,
                 cu_duplicate: bool = False):
        randuri = interogare(
            "SELECT ST_AsGeoJSON(poligon, 6)::json AS geometrie, detectie_id, sursa, judet, uat, tip, stadiu_curent,"
            " stadiu_produs, data_stadiu, data_defrisare, data_module, incredere, lat, lon, suprafata_ha, mwp, mwp_min,"
            " mwp_max, mwp_din_suprafata, parc_id, duplicat_al, atr_id, atr_numar, atr_titular, atr_cui, atr_mw"
            " FROM v_detectii WHERE (%(j)s::text IS NULL OR judet = %(j)s) AND (%(s)s::text IS NULL OR stadiu_curent = %(s)s)"
            " AND (%(src)s::text IS NULL OR sursa = %(src)s) AND (%(dup)s OR duplicat_al IS NULL)"
            " ORDER BY judet, detectie_id",
            {"j": judet and judet.upper(), "s": stadiu, "src": sursa, "dup": cu_duplicate})
        return _feature_collection(randuri)

    @app.get("/api/detectii/{detectie_id}", summary="O detecție: jurnalul de dovezi și ATR-urile candidate")
    def detectie(detectie_id: str):
        d = unul("SELECT ST_AsGeoJSON(poligon, 6)::json AS geometrie, * FROM v_detectii WHERE detectie_id = %s",
                 (detectie_id,), f"Nu există detecția {detectie_id}")
        d.pop("poligon", None)
        d["jurnal"] = interogare(
            "SELECT data_imagine, stadiu, sursa_imagine, id_imagine, tile, cer_senin, suprafata_ha, versiune_pipeline, note"
            " FROM jurnal_detectii WHERE detectie_id = %s ORDER BY data_imagine, sursa_imagine", (detectie_id,))
        d["legaturi_atr"] = interogare(
            "SELECT l.atr_id, l.stare, l.scor, l.motive, l.decis_de, l.decis_la, l.note, a.numar, a.titular, a.cui,"
            " a.mw, a.etapa, a.data_pif FROM legaturi_atr l JOIN atr a ON a.id = l.atr_id"
            " WHERE l.detectie_id = %s ORDER BY (l.stare = 'confirmata') DESC, l.scor DESC", (detectie_id,))
        return d

    @app.get("/api/atr", summary="Caută ATR-uri după titular, CUI sau județ, cu ce s-a găsit pe teren")
    def atr(q: str | None = Query(None, description="text din numele titularului sau numărul ATR"),
            cui: str | None = None, judet: str | None = None,
            stare_teren: str | None = Query(None, description="fara_santier_legat, santier, panouri, gata, ..."),
            limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
        filtru = ("(%(q)s::text IS NULL OR titular ILIKE '%%' || %(q)s || '%%' OR numar ILIKE '%%' || %(q)s || '%%')"
                  " AND (%(cui)s::text IS NULL OR cui = %(cui)s) AND (%(j)s::text IS NULL OR judet = %(j)s)"
                  " AND (%(st)s::text IS NULL OR stare_teren = %(st)s)")
        params = {"q": q, "cui": cui and cui.upper().removeprefix("RO").strip(), "j": judet and judet.upper(),
                  "st": stare_teren, "limit": limit, "offset": offset}
        total = interogare(f"SELECT count(*) AS n, coalesce(sum(mw), 0) AS mw FROM v_atr WHERE {filtru}", params)[0]
        randuri = interogare(
            "SELECT id, numar, data_atr, titular, cui, judet, judet_nume, mw, operator, etapa, data_pif, tehnologie,"
            " localitate, sursa, detectie_id, stare_teren, stadiu_produs, mwp_detectat, data_defrisare, data_module,"
            f" candidati FROM v_atr WHERE {filtru} ORDER BY mw DESC, id LIMIT %(limit)s OFFSET %(offset)s", params)
        return {"total": total["n"], "mw_total": total["mw"], "rezultate": randuri}

    @app.get("/api/companii/{cui}", summary="O companie (după CUI) și toate ATR-urile ei")
    def companie(cui: str):
        cui = cui.upper().removeprefix("RO").strip()
        c = unul("SELECT * FROM companii WHERE cui = %s", (cui,), f"Nu există compania cu CUI {cui}")
        c["atr"] = interogare(
            "SELECT id, numar, data_atr, judet, mw, etapa, data_pif, tehnologie, detectie_id, stare_teren, stadiu_produs"
            " FROM v_atr WHERE cui = %s ORDER BY mw DESC", (cui,))
        return c

    @app.get("/api/detectii/{detectie_id}/raport", response_class=PlainTextResponse,
             summary="Raportul de dovezi datat al unei detecții (Markdown)")
    def raport_detectie(detectie_id: str):
        d = detectie(detectie_id)
        return PlainTextResponse(raport.detectie(d, date.today()), media_type="text/markdown; charset=utf-8")

    @app.get("/api/parcuri/{parc_id}/raport", response_class=PlainTextResponse,
             summary="Raportul de dovezi datat al unui parc din setul de adevăr (Markdown)")
    def raport_parc(parc_id: str):
        p = parc(parc_id)
        return PlainTextResponse(raport.parc(p, date.today()), media_type="text/markdown; charset=utf-8")

    return app


app = creeaza_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))

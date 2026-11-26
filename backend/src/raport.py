"""Rapoartele de dovezi datate (Markdown), pentru o detecție sau un parc. Folosite de api.py.

Raportul spune ce s-a văzut, când și pe ce imagine, ca oricine să poată verifica: data imaginii,
produsul (ex. S2B_MSIL2A_...), tile-ul și versiunea pipeline-ului.
"""

from __future__ import annotations

from datetime import date

STADIU_PRODUS = {"teren_gol": "neînceput", "santier": "în construcție", "panouri": "în construcție",
                 "gata": "construit", "nesigur": "nesigur"}


def _v(x, sufix: str = "") -> str:
    if x is None or x == "":
        return "–"
    if isinstance(x, float) or hasattr(x, "as_integer_ratio"):
        x = f"{float(x):.2f}".rstrip("0").rstrip(".")
    return f"{x}{sufix}"


def _tabel(antet: list[str], randuri: list[list]) -> list[str]:
    if not randuri:
        return ["_Nicio înregistrare._"]
    linii = ["| " + " | ".join(antet) + " |", "|" + "---|" * len(antet)]
    linii += ["| " + " | ".join(_v(c).replace("|", "/") for c in r) + " |" for r in randuri]
    return linii


def detectie(d: dict, azi: date) -> str:
    l = [f"# Raport de dovezi: detecția {d['detectie_id']}", "",
         f"Generat de MWitness pe {azi.isoformat()}. Sursa detecției: {d['sursa']}"
         + (f" (versiunea {d['versiune_pipeline']})" if d.get("versiune_pipeline") else "") + ".", "",
         "## Rezumat", "",
         f"- **Stadiu:** {STADIU_PRODUS.get(d['stadiu_curent'], d['stadiu_curent'])} (`{d['stadiu_curent']}`),"
         f" pe imaginea din {_v(d.get('data_stadiu'))}" + (f", încredere {_v(d.get('incredere'))}" if d.get("incredere") is not None else ""),
         f"- **Loc:** județul {d['judet']}" + (f", {d['uat']}" if d.get("uat") else "")
         + f"; centrul la {d['lat']:.5f}, {d['lon']:.5f}",
         f"- **Suprafață:** {_v(d.get('suprafata_ha'), ' ha')}",
         f"- **Putere estimată:** {_v(d.get('mwp'))} MWp (interval {_v(d.get('mwp_min'))}–{_v(d.get('mwp_max'))})"
         + (", estimată din suprafață" if d.get("mwp_din_suprafata") else ", din pipeline"),
         f"- **Început lucrări (defrișare):** {_v(d.get('data_defrisare'))}",
         f"- **Primele panouri:** {_v(d.get('data_module'))}"]
    if d.get("parc_id"):
        l.append(f"- **Parc din setul de adevăr:** {d['parc_id']}")
    if d.get("duplicat_al"):
        l.append(f"- **Același parc ca detecția** {d['duplicat_al']} (nu se numără de două ori)")

    l += ["", "## ATR", ""]
    confirmate = [x for x in d.get("legaturi_atr", []) if x["stare"] == "confirmata"]
    propuse = [x for x in d.get("legaturi_atr", []) if x["stare"] == "propusa"]
    if confirmate:
        a = confirmate[0]
        l += [f"Legată de ATR-ul **{a['numar']}**, titular **{a['titular']}**" + (f" (CUI {a['cui']})" if a.get("cui") else "")
              + f", {_v(a['mw'])} MW, etapa {_v(a.get('etapa'))}, PIF estimat {_v(a.get('data_pif'))}.",
              f"Confirmat de {_v(a.get('decis_de'))} pe {_v(a['decis_la'].date() if a.get('decis_la') else None)}"
              + (f": {a['note']}" if a.get("note") else ".")]
    elif propuse:
        l += ["Niciun ATR confirmat încă. Candidați propuși automat (după județ, MW și localitate):", ""]
        l += _tabel(["ATR", "Titular", "MW", "Scor"], [[x["numar"], x["titular"], x["mw"], x["scor"]] for x in propuse])
    else:
        l.append("Niciun ATR legat și niciun candidat.")

    l += ["", "## Jurnalul imaginilor", ""]
    l += _tabel(["Data", "Stadiu", "Sursa", "Produs", "Tile", "Cer senin", "Suprafață (ha)"],
                [[j["data_imagine"], j["stadiu"], j["sursa_imagine"], j["id_imagine"], j.get("tile"), j.get("cer_senin"),
                  j.get("suprafata_ha")] for j in d.get("jurnal", [])])
    l += ["", "_Stadiile vin din imagini satelitare și pot greși; `nesigur` înseamnă că imaginile nu permit o decizie."
          " MWp estimați din suprafață folosesc densitatea din tabelul `parametri`._", ""]
    return "\n".join(l)


def parc(p: dict, azi: date) -> str:
    l = [f"# Raport de dovezi: {p['nume']} ({p['parc_id']})", "",
         f"Generat de MWitness pe {azi.isoformat()}. Parc din setul de adevăr, rol `{p['rol']}`.", "",
         "## Rezumat", "",
         f"- **Stadiu curent:** {p['stadiu_produs']} (`{p['stadiu_curent']}`), verificat pe {_v(p.get('data_verificare'))}"
         f" de {_v(p.get('verificat_de'))}",
         f"- **Loc:** județul {p['judet']}" + (f", {p['uat']}" if p.get("uat") else "") + f"; {p['lat']:.5f}, {p['lon']:.5f}",
         f"- **Putere:** {_v(p.get('mwp'))} MWp / {_v(p.get('mwac'))} MWac (sursa: {_v(p.get('sursa_mw'))})",
         f"- **Deținător:** {_v(p.get('detinator'))}" + (f", CUI {p['cui']}" if p.get("cui") else ""),
         f"- **ATR:** {_v(p.get('atr_numar'))}" + (f" din {p['atr_data']}" if p.get("atr_data") else "")
         + (f", {_v(p['atr_mw'])} MW" if p.get("atr_mw") is not None else ""),
         f"- **Sursa:** {p['sursa']}", "",
         "## Stadiul lună de lună (verificat manual)", ""]
    l += _tabel(["Luna", "Stadiu", "Sursa imaginii", "Data imaginii", "Produs", "Verificat de"],
                [[s["luna"], s["stadiu"], s.get("sursa_imagine"), s.get("data_imagine"), s.get("id_imagine"),
                  s["verificat_de"]] for s in p.get("stadii_adevar", [])])
    l += ["", "## Stadiul prezis de pipeline", ""]
    l += _tabel(["Luna", "Model", "Stadiu", "Încredere", "MWp", "Imagine"],
                [[s["luna"], s["versiune_model"], s["stadiu"], s.get("incredere"), s.get("mwp_estimat"),
                  s.get("id_imagine")] for s in p.get("stadii_pipeline", [])])
    l.append("")
    return "\n".join(l)

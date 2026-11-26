# Pornim de la satelit, nu de la lista ATR („detect-first”)

**Data:** 21 noiembrie 2026 (decizia), 26 noiembrie 2026 (aplicată în backend)

## Context

Un om din domeniu ne-a spus că nu putem afla unde sunt parcurile aprobate. Am verificat sursele publice: lista Guvernului cu titularii de ATR (aprilie–mai 2026) dă titularul, CUI-ul, MW, operatorul, etapa și data PIF, dar locația doar la nivel de **județ**. Anunțurile APM și primăriile dau localitatea sau parcela, dar sunt împrăștiate. Nicio sursă nu dă coordonatele tuturor ATR-urilor.

## Decizie

1. **Pornim de la satelit.** Pipeline-ul detectează parcurile și șantierele noi în zonele de studiu (Dolj+Gorj, Dâmbovița+Giurgiu). Seturile deschise (TZ-SAM, OSM) completează parcurile deja construite.
2. **Legăm detecțiile de ATR-uri** după județ, MW (din suprafață), localitatea din numele titularului și anunțurile APM. Scriptul propune candidați; omul confirmă. Cele 30 de proiecte din livrabil se leagă manual.
3. **Harta națională e pe județ:** MW aprobați (lista ATR) față de MWp detectați. Atât permit datele publice.
4. **Clientul poate aduce lista lui** (bancă, investitor, Transelectrica): atunci verificăm amplasamentele lui, fără pasul de legare.

## Ce înseamnă pentru backend

Migrarea `002_detect_first.sql`: tabelele `judete`, `companii`, `atr`, `detectii`, `jurnal_detectii`, `legaturi_atr`, `parametri` și vederile `v_detectii`, `v_atr`, `v_judete`. Detalii în [`backend/schema.md`](../../backend/schema.md).

## Surse

Nota completă cu sursele (Guvern, Transelectrica, ANRE, APM, primării, TZ-SAM) e în fișierele proiectului: `mwitness/locatii-parcuri-aprobate.md`.

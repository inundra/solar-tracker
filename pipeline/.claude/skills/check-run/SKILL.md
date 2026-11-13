---
name: check-run
description: Leave-one-park-out self-check of the MWitness pipeline on all parks; prints stage, date and MWp error vs the ±8% target. Use before demos, after param changes, and for backlog item P11.
---

1. Preflight as in `/pipeline-task` step 2 (EE auth is needed only if caches are missing or `--refresh` is used).
2. For each park P in `config/sites.yaml`:
   - fit the classifier and the MWp density factor on the **other 4 parks only**,
   - run `python -m src.run --site P` with that fit; confirm `provenance.held_out == true`.
3. Compare against ground truth, **read-only**, from `../validare/proiecte_cartate/` (plus `reported_mwp` in `sites.yaml` for CHECK parks). This is the only place validare data may be read; never write the comparison back into `src/`, `labels/` or `config/`.
4. Print one table:

   | park | role | stage acc | clearing err (days) | modules err (days) | MWp est [low, high] | MWp reported | rel err | within ±8% | panel IoU | # clear obs |

   Plus the mean per metric and how many parks ended `nesigur`.
5. Flag any rel err > 8%, any date err > 30 days, and any metric that looks suspiciously perfect (possible leakage: run `tests/test_no_leakage.py` and say so).
6. Save the table as `data/check_runs/<YYYY-MM-DD>_<git-short-hash>.md` (gitignored). The validation team owns `validare/rezultate/`: offer them the table, don't write there.
7. If ground truth is missing for a park, report it as "no GT" rather than skipping it silently.
8. Add a `LOG.md` entry (`check-run`) with the means, the flags and the table path, and replace section 3 "Current results" in `APPROACH.md` with the new summary (date + commit).

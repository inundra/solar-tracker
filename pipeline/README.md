# Satellite Pipeline (MWitness)

**Owner:** Satellite Pipeline team

Turns Sentinel imagery into a dated construction record for each solar / BESS project. Deadline: **11 Dec 2026**.

- **Sources:** Sentinel-2 (optical) and Sentinel-1 (radar, for cloudy periods).
- **Platform:** Google Earth Engine; openEO / CDSE is the fallback only (no Cloud Score+ there).
- **Cloud mask:** Cloud Score+ (`cs_cdf ≥ 0.60`).
- **Outputs per project:** stage per date (`neînceput`, `în construcție`, `construit`, `nesigur`; exact strings, used by the backend), clearing date, modules-appear date, MWp and MWac as intervals estimated from panel area, and an evidence log (image date, product, tile, clear fraction). Format: `CONTRACT.md`.
- **Study areas** (6 parks, `config/sites.yaml`):
  - TRACK (under construction, follow progress): Tismana 1, Tismana 2, Rovinari (Gorj), Ișalnița (Dolj)
  - CHECK (finished, verify the model): Văcărești, Titu (Dâmbovița)

Keys and auth files (Earth Engine, openEO) never go into the repo.

## Layout

```
pipeline/
├── README.md        ← you are here
├── CLAUDE.md        ← agent brief: mission, hard rules, architecture, EE gotchas
├── BACKLOG.md       ← ordered tasks with "done when", weeks 2–5
├── CONTRACT.md      ← output schema the backend and validation teams consume
├── APPROACH.md      ← living doc: current approach, why, status, results
├── LOG.md           ← append-only work log, newest first
├── requirements.txt
├── config/
│   ├── sites.yaml          ← the 6 park AOIs (hand-drawn) and roles
│   ├── sites.example.yaml  ← template
│   └── params.yaml         ← every threshold in one place
├── src/             ← reusable code (extraction, classification, stage, MWp, evidence, CLI)
├── tests/           ← pytest; Earth Engine tests behind marker `ee`
├── notebooks/       ← exploration and prototypes only; clear outputs before commit
├── data/            ← cache, run logs, time-lapses (gitignored)
├── outputs/         ← per-site JSON results (gitignored)
└── .claude/         ← agent settings, reviewer subagent, /pipeline-task and /check-run skills
```

## Setup (once per machine)

1. `python -m venv .venv; .venv\Scripts\activate; pip install -r pipeline\requirements.txt`
2. A Google Cloud project with the Earth Engine API enabled and registered for noncommercial use.
3. `earthengine authenticate` (opens a browser; credentials land in `~/.config/earthengine/`, outside the repo).
4. `setx EE_PROJECT "<your-gcp-project-id>"`, then open a new terminal.

## Run

```
python -m pytest -q                       # offline tests
python -m pytest -q -m ee                 # Earth Engine smoke tests (needs auth)
python -m src.run --site tismana_1 --dry  # set up and log, no data
python -m src.run --site <id> [--refresh]
```

## Working with the Claude agent

Start Claude Code **from `solar-tracker/pipeline/`** (not the repo root). That way `CLAUDE.md` and `.claude/` load automatically, and edits outside `pipeline/` (validare, backend, business) need your approval, which matches the team rule that other folders go through PR review.

| You type | What happens |
|---|---|
| `/pipeline-task` | Agent picks the next open item in `BACKLOG.md`, does it test-first, runs on one park, gets a review from the reviewer subagent, commits, asks before pushing. |
| `/pipeline-task P4` | Same, for a specific item. |
| `/check-run` | Leave-one-park-out on all 6 parks; prints the metric table (stage accuracy, date error, MWp error vs ±8%). |

## Keeping track: what's done and why

| Where | What | Updated when |
|---|---|---|
| `APPROACH.md` | The approach **right now**: each step, how, why, status; current results; limits; open questions; rejected alternatives | Every task that changes what or why; every `/check-run` |
| `LOG.md` | History: dated entries (done / why / result / not checked / next / commit), never rewritten | Every task, check-run, notable finding |
| `data/logs/*.log` | Run logs: params hash, scenes, clear obs, each stage decision with evidence ID (gitignored) | Every pipeline run |

The agent must update these (Definition of done in `CLAUDE.md`), and the reviewer subagent blocks commits that skip them. To catch up after a week away: read `APPROACH.md`, then the top of `LOG.md`.

## The workflow in one picture

```
 sites.yaml ─► EE extract (S2+CS+, S1) ─► per-site time series CSV (cached, gitignored)
                                              │
                    pure Python, unit-tested ◄┘
                    ├─ stage.py  → stage per date + clearing / modules dates
                    ├─ mwp.py    → MWp interval, MWac interval
                    └─ evidence.py → evidence log rows
                                              │
                                              ▼
                           outputs/*.json per CONTRACT.md ─► backend (DB) + validare (metrics)
```

The key design choice: **Earth Engine only extracts numbers; all decisions (stage, dates, MWp) are pure Python over a cached CSV.** That keeps the logic testable offline, fast to iterate, and cheap on EE quota.

## Open team decisions

Tracked in `APPROACH.md` § 5 (Open questions). The agent stops and asks on any of them.

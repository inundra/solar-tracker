---
name: pipeline-task
description: Do one MWitness pipeline backlog item end to end (branch, test-first, run on one park, review, commit). Use when asked to work on the pipeline or given a backlog ID like P4.
---

Argument: optional backlog ID (e.g. `P4`). Without it, take the first `todo` item in `BACKLOG.md` whose predecessors are `done`.

1. **Orient.** Re-read the `CLAUDE.md` rules, `APPROACH.md`, and the top 3 `LOG.md` entries. Read the item in `BACKLOG.md`, its "done when", and the code it touches. Mark it `doing`.
2. **Preflight.** If the item needs Earth Engine: check `EE_PROJECT` is set and `python -c "import ee, os; ee.Initialize(project=os.environ['EE_PROJECT'])"` works. If not, stop, tell the human to run `earthengine authenticate` and set `EE_PROJECT`, mark `blocked(ee-auth)`.
3. **Branch.** `git switch -c pipeline/<short-desc>` from an up-to-date `main` (ask before pulling if the tree is dirty).
4. **Plan in 3–6 lines** in the chat: files to touch, params used, test cases. If the plan needs a new threshold or a contract change, stop and ask.
5. **Test first** for pure logic (`stage.py`, `mwp.py`, `evidence.py`, parsing): write the failing test against a fixture CSV, then implement. EE code gets a small `@pytest.mark.ee` smoke test.
6. **Implement** the smallest change that meets "done when". Thresholds go to `config/params.yaml`.
7. **Run for real** on one TRACK park, the smallest date range that shows the behaviour. Show the key numbers (scene count, clear obs, stage dates, MWp) in the chat. If something looks off, say so; don't paper over it.
8. **Review.** Launch the `pipeline-reviewer` subagent on the diff. Fix all BLOCKING findings, re-run tests.
9. **Hygiene.** `nbstripout` on touched notebooks; `git diff --cached --stat` shows no data, rasters, secrets, or files outside `pipeline/`.
10. **Record, then commit.** Add a `LOG.md` entry at the top (done / why / result with numbers and run-log path / not checked / next). If the approach, a reason, or current results changed, update `APPROACH.md` (rows, status, "Last updated"). Set the `BACKLOG.md` status to `done`. Commit code and records together as `pipeline: <what> (P4)`. In the LOG entry, the `Commit:` line holds the branch name (the hash isn't known before committing).
11. **Hand back**: summary (what changed, numbers from step 7, what wasn't checked), then ask whether to push and open a PR. If a param changed reported results, draft the `docs/decizii/` note text for the human.

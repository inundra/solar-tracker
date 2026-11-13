# Pipeline output contract (PROPOSAL: needs OK from Backend and Validation teams)

One JSON file per site: `outputs/<site_id>.json`, UTF-8. Backend imports it into PostGIS; validation compares it against `validare/proiecte_cartate/`.

```json
{
  "site_id": "tismana_1",
  "atr_id": null,
  "role": "TRACK",
  "generated_at": "2026-11-20T10:00:00Z",
  "provenance": {
    "git_commit": "abc1234",
    "params_hash": "sha1 of config/params.yaml",
    "collections": ["COPERNICUS/S2_SR_HARMONIZED", "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED", "COPERNICUS/S1_GRD"],
    "date_range": ["2022-01-01", "2026-11-20"],
    "held_out": true
  },
  "current_stage": "în construcție",
  "clearing_date": {"from": "2025-03-04", "to": "2025-03-19"},
  "modules_date":  {"from": "2025-09-10", "to": "2025-10-02"},
  "mwp": {"low": 42.0, "high": 51.0},
  "mwac": {"low": 33.0, "high": 44.0},
  "panel_area_ha": 61.2,
  "stage_series": [
    {"date": "2025-03-19", "stage": "în construcție", "evidence_ids": ["e12"]}
  ],
  "evidence": [
    {
      "id": "e12",
      "claim": "clearing",
      "image_date": "2025-03-19",
      "product": "COPERNICUS/S2_SR_HARMONIZED",
      "image_id": "20250319T092031_20250319T092611_T34TFQ",
      "tile": "T34TFQ",
      "clear_frac": 0.97,
      "values": {"veg_frac": 0.08, "bare_frac": 0.81}
    }
  ],
  "timelapse": "data/timelapse/tismana_1.gif"
}
```

Rules:
- `stage` ∈ `neînceput`, `în construcție`, `construit`, `nesigur`.
- Dates are intervals; `null` when the event hasn't happened.
- Geometry is not duplicated here; backend owns site geometry (`amplasamente`) and joins on `site_id` / `atr_id`.
- `held_out: true` means the fitted parts (classifier, density factor) did not see this park.
- Breaking changes: bump a `"schema_version"` field and tell both teams.

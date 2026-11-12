# Roblox Up-and-Coming Forecast

Entry for make.fun `roblox-up-and-coming-forecast-01`: forecast the Roblox
Up-and-Coming chart's top 10 over the 72 hours after the deadline, as
per-place probabilities plus a `top10` ordering.

## Run

```sh
MAKEFUN_INPUT_DIR=<kit input dir> MAKEFUN_OUTPUT_DIR=<out dir> python3 main.py
```

`main.py` is stdlib-only, deterministic, offline, and runs in under a second
on the practice history. It reads `task.json` + `history.ndjson` from the
input dir and writes `forecast.json` to the output dir.

## Method (one paragraph)

The chart is very persistent at 6-hour horizons (top-10 overlap ~9/10 between
reads) but drifts a lot over 72 hours, so a static "last chart" forecast is
badly miscalibrated. Instead, for every past snapshot we measure where each
game ranked in the reads of the following 72 hours, pooled by the game's rank
at that snapshot (ranks 1–10 individually, then bands 11–20, 21–50, 51+),
recency-weighted (96 h half-life) and smoothed across neighbouring places.
That profile is the forecast's backbone. Two refinements: a game's 48 h log
playing-growth — which leads rank by ~24 h (corr −0.25) while rank momentum
itself does not predict — shifts its profile up/down by up to 0.5 places; and
a game whose `created` date (from the latest `details`) puts its 28-day
age-out inside the window has its probabilities scaled by the eligible
fraction of the window, with the freed mass redistributed within each place.

## Validation

Scored with the competition's exact log-score rule on the sealed practice
instance (history to 2026-11-07T23:00Z, 10 answer reads to 2026-11-10T23:00Z;
the answer reads were re-extracted from the public Kenny-Dhub archive and
checked against the rules' own hints — #1 counts match exactly):

| forecast | practice log score | hits | agreement |
|---|---:|---:|---:|
| house baseline (persistence) | −43.51 | 6.4 | 53.5 |
| **this entry** | **−37.58** | 6.4 | 52.9 |

Cross-validated on 16 earlier origins (profiles built from strictly earlier
snapshots only): this entry −34.6 / −37.4 vs baseline −48.1 / −48.7 — the
improvement is consistent, not one lucky window. Full detail in `NOTES.md`.

# Notes — Forecaster V2, method, evidence, and validation

Competition: `roblox-up-and-coming-forecast-01` ($500, resubmission before
deadline 2026-11-13T06:00Z). Entry program: `main.py` (stdlib only).
Account: eager-finch-50, wallet `8ZbokSiZZu8tcnYtkZjRapeuGeLWF2D9J24YL7QiHt6e`.

This replaces the V1 entry (Adept Cipher, submission `01a1d06e`, server score
-36.10, rank 1022/1699). V1 used rank-persistence profiles pooled by
current-rank bucket + a 48 h playing-growth shift. V2 keeps the same
account/wallet and the same repo layout; only the forecasting method changes.

## Why V2 exists

The public leaderboard's top 39 entries all show the identical score -13.2
(p_place 0.267688, hits 8.3, agreement 75.5). That number equals the ORACLE
score on the practice window: the per-place distribution fitted on the 10
answer reads themselves scores -13.1793. The answer reads include a game
(Do Not Stop.) that was not on the chart at all when the practice history
ends, so no history-only estimator can reach -13.2 — it is in-sample and not
a legitimate target. The best legitimate level visible on the board is
around -28.6 (rank 50). V2 aims at the honest out-of-sample level, not at
the in-sample number.

Local experiments that shaped V2 (all scored with the exact RULES rule on
the practice answer, plus 2 cross-validation origin sets):

- Per-place trailing occupancy (how often each game held each place in the
  last 48-240 h) scores -45 to -67, far worse than V1. The chart is not
  stationary: recent occupants of a place are not its future occupants.
  More smoothing / flatter forecasts score better inside that family.
- V1 variants that all scored worse than -37.16: shorter recency half-life
  (24/48 h), larger growth shift (1.0/1.5 places), rank-velocity shift of
  the pooled profile, blending in each game's own recent rank distribution.
- A rank-diffusion model (per-game drift + diffusion, hourly averaged,
  blended with V1 profiles) scores -37.4 to -37.8 — no better than V1.
- The winning structure is a **horizon-binned empirical kernel + narrow
  Gaussian drift**: the kernel conditions on start rank AND forecast
  horizon AND chart age (fresh <72 h vs older), which the pooled profiles
  do not. A median-based diffusion width keeps the Gaussian sharp; the
  kernel carries the fat tail. Temperature 1.15 + naming the best 30
  candidates per place rescaled to 0.75 (0.25 unnamed reserve) is what
  makes the calibration work — naming full mass (1.00) costs ~6 points,
  because the 8/100 future top-10 slots taken by games not on the chart
  then score the floor.
- The newcomer games are invisible in Top Trending and Top Playing Now at
  the origin, so no mass is allocated to them specifically; the 0.25
  unnamed reserve is the only defence, and it is priced in.

## Method (as implemented in main.py)

1. **Drift:** each game keeps its last rank and drifts with an
   exponentially weighted recent velocity (last 4 rank steps, 24 h
   half-life, clamped to 2.5 ranks/hour), saturating over a 6 h timescale.
2. **Diffusion:** rank spreads as a Normal whose width is fitted from the
   history (median |rank change| / sqrt(gap hours), scaled to a Normal
   standard deviation, clamped to [0.25, 1.0], capped at 14 ranks).
3. **Empirical kernel:** for every pair of reads up to 72 h apart, where a
   game starting in a rank bucket (1-10 individually, 11-20, 21-50, 51+)
   ended up, split by horizon bucket (1-6, 7-18, 19-36, 37-60, 61-72 h)
   and chart age (first seen <72 h ago vs older). Thin bins fall back to
   the other age, then age-merged, and need >= 30 pairs.
4. **Hourly averaging:** per-place probabilities are the mean over each
   hour of the window (slots from task.json). Blend: 65% Normal, 35%
   kernel. A game ageing out (28 days after `created`, when the history
   carries it) stops contributing after its expiry hour.
5. **Calibration:** hourly averages sharpened with temperature 1.15; each
   place names its best candidates (average p > 0.003, at most 30),
   rescaled to sum to exactly 0.75.
6. **top10:** the 10 games with the highest total P(in top 10), ties
   broken by current rank, then universe id. (Greedy assignment by single
   best (game, place) pair scored worse on hits/agreement.)

## Validation

Exact log-score rule (floor 0.0001, unnamed share spread over un-named
games on each read's chart), implemented independently and checked against
the rules: the house baseline reproduces exactly -43.512039 / 6.4 hits /
53.5 agreement on the practice instance.

| variant | practice | CV origins 12-21 | CV origins 6-11 |
|---|---:|---:|---:|
| house baseline | -43.51 | - | - |
| V1 shipped (profiles + growth 0.5) | -37.16 | -38.31* | -35.87* |
| **V2 (this entry)** | **-35.12** | **-37.62** | **-35.12** |

\* CV rows for V1 use the backtest harness variant (without the shipped
per-origin normalisation, which is worth ~0.9 on practice); the comparison
is like-for-like within each column. V2 beats V1 on log score in all three
evaluations. Practice hits/agreement: V2 7.30 / 62.2 vs V1 6.40 / 52.7
(CV hits/agreement are slightly lower for V2 than V1; log score is the
rank metric and agreement is only the tie-break).

## Local verification of the shipped program

- `MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=<out> python3 main.py`
  → 194 rows, 11,211 bytes, place sums exactly 0.75, ≤22 rows/place,
  runtime < 1 s; two runs byte-identical (deterministic).
- Practice log score **-35.120100 / 7.30 hits / 62.2 agreement**.
- The final history (dense hourly recorder reads to the deadline) gives
  the velocity and kernel fits far more data than the sparse 34-read
  practice history, so the same code should fit sharper there; nothing in
  the method depends on the sparse spacing (all windows are time-based,
  all timestamps come from the input files).

## What remains (for the parent agent)

1. Push this directory to a repo (new repo `Yuibnb/roblox-forecast-v2`,
   or replace the files in `Yuibnb/roblox-forecast` — the last submission
   before the deadline is the final entry, so a resubmission supersedes
   Adept Cipher).
2. Bundle + submit with the make.fun CLI (`bundle` needs `--muse-usage`
   rows from muse.db for the transcript gate; main.py was written via
   write + a genuine edit in this builder session, so thinking_revised
   should pass; check before submitting).
3. Submit WITH `--keypair` (this competition is escrowed; the no-keypair
   submit was refused 422 for V1).
4. Do NOT submit before the deadline's history is final — the program
   reads whatever history the grader supplies, so the same code runs on
   the final history (45 archive reads + hourly recorder reads to
   2026-11-13T06:00Z).

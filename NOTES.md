# Notes — method, evidence, and validation

Competition: `roblox-up-and-coming-forecast-01` ($500, deadline 2026-11-13T06:00Z).
Entry program: `main.py` (stdlib only). Account: eager-finch-50,
wallet `8ZbokSiZZu8tcnYtkZjRapeuGeLWF2D9J24YL7QiHt6e`.

## What the data showed

Practice history: 34 archive reads, 2026-10-30T07:36:30Z → 2026-11-07T20:53:19Z,
gaps 3.6–9.8 h, ~97 games per read, 207 distinct games, 39 ever in the top 10.
No `details` (no created dates, votes, genres) in the archive reads — the
final history's hourly recorder reads carry them.

- **Rank is persistent short-term, drifty over 72 h.** Top-10 overlap between
  consecutive reads is mostly 8–10/10, but the #1 changed 13 times across the
  archive's 45 reads and the top 10 changed in 42 of 44 consecutive pairs.
- **Playing-count growth does NOT explain rank contemporaneously**
  (corr ≈ −0.02), but **it leads rank by ~24 h (corr −0.25)**: games whose
  playing grew fast in the past 24 h climb over the next 24 h. Example: Sweep
  The Moon's playing went 3,764 → 45,252 (+12×) while its rank was still #29;
  it then took #1 in 2 of the 10 practice reads.
- **Rank momentum does not predict** (corr +0.05 between past and future
  24 h rank change; every bucket mean-reverts downward).
- **New games can jump straight to the top.** Do Not Stop. was not on the
  chart at all at history end, yet took #1 in the last 3 practice reads.
  Survive Your Ideas first appeared in the very last history read — at #1 —
  then held #1 in none of the 10 practice reads (mostly #5). A brand-new #1
  is usually a flash in the pan; the profile for origin rank #1 already
  prices that in (P(stay #1) ≈ 0.37, spread over places 1–6).
- **Pooled 72 h rank-persistence profiles** (origin rank → distribution over
  places in the next 72 h, n ≈ 298 origin/future pairs per top-10 rank):
  #1 stays top-10 98.7% of the time, P(#1) = 0.37; #2 P(top-10) = 0.87;
  #7 only 0.39; #10 only 0.28. Ranks 11–20 each enter the top 10 with
  P ≈ 0.14; ranks 21–50 with P ≈ 0.035; ranks 51+ with P ≈ 0.016.

## Model (as implemented in main.py)

1. **Profiles.** For every snapshot with a later read within 72 h, record
   each game's future ranks, pooled by origin-rank bucket (1..10, 11–20,
   21–50, 51+). Origins recency-weighted, half-life 96 h (weight relative to
   the last snapshot). Profiles smoothed across neighbouring places with a
   3-point moving average.
2. **Growth shift.** 48 h log playing-growth per game (nearest snapshot ≥48 h
   before, else the earliest), percentile-ranked across the chart; the profile
   is shifted by `0.5 × (percentile − 0.5) × 2` places (max ±0.5), linearly
   interpolated. Games with no usable growth history get no shift.
3. **Age-out.** Games leave the chart 28 days after `created`. The latest
   `details` give `created` per game; a game's probabilities are scaled by
   the fraction of the window before its age-out, and the freed mass is
   redistributed proportionally within each place (place sums preserved).
   Verified with a synthetic test: a game ageing out 24 h into the window
   kept ~1/3 of its mass, a game ageing out at the window start went to 0,
   and the top 10 re-ordered accordingly.
4. **Output.** All rows with p ≥ 0.001 are named; each place's rows sum to
   ≤ 1 (rescaled if ever above); `top10` = the 10 games with the highest
   P(in top 10), ties broken by current rank then universe id.

## Validation

Exact log-score rule (floor 0.0001, unnamed share spread over un-named games
on each read's chart), implemented independently and checked against the
rules: the house baseline reproduces **exactly −43.512039 / 6.4 hits / 53.5
agreement** on the practice instance, so the scorer and the answer set
(10 reads re-extracted from the Kenny-Dhub archive commits) are correct.

| variant | practice | CV origins 6–11 | CV origins 12–21 |
|---|---:|---:|---:|
| house baseline | −43.51 | −48.12 | −48.66 |
| profile only | −38.64 | −37.11 | −38.41 |
| profile + growth shift 0.5 (24 h) | −38.13 | −35.87 | −38.31 |
| **profile + growth 48 h + smooth + recency 96 h (chosen)** | **−37.58** | **−34.65** | **−37.40** |

Rejected by cross-validation (looked better on the single practice window
only): naming only the top 15–60 rows per place (practice −35.0 but CV
−35.4/−38.5), and larger growth shifts (1.0–1.5 places). The chosen
configuration is the robust middle: good on practice and on both CV sets.

Per-read practice scores for the chosen entry decay through the window
(−28.0 on the first read → −51.6 on the last), as expected for a static
forecast of a drifting chart; the profile already averages over the window,
so this is priced in.

## Local verification of the shipped program

- `MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=/tmp/rf-out1 python3 main.py`
  → 940 rows, 53,737 bytes, place sums 0.86–0.97, ≤97 rows/place, runtime
  0.17 s; two runs byte-identical (deterministic).
- The shipped file scores **−37.58 / 6.4 hits / 52.9 agreement** on practice.
- Age-out path verified with synthetic `details` (see above).

## What remains (for the parent agent)

1. Create the public GitHub repo (needs Doni's GitHub approval) and push this
   directory: `main.py`, `LICENSE`, `README.md`, `NOTES.md`,
   `.makefun/owner.json`.
2. Bundle + submit with the make.fun CLI (`bundle` needs `--muse-usage` rows
   from muse.db for the transcript gate; the session that wrote the code must
   have ≥5 assistant turns with text, ≥2 file-write messages for main.py,
   and the transcript must reproduce ≥30% of main.py's counted lines).
3. Do NOT submit before the deadline's history is final — the program reads
   whatever history the grader supplies, so the same code runs on the final
   history (45 archive reads + hourly recorder reads to 2026-11-13T06:00Z).
   Re-run locally against the final history if it is published before the
   deadline, as a smoke test.

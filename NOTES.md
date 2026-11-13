# Notes — Forecaster V3, method, evidence, and validation

Competition: `roblox-up-and-coming-forecast-01` ($500, resubmission before
deadline 2026-11-13T06:00Z). Entry program: `main.py` (stdlib only).
Account: eager-finch-50, wallet `8ZbokSiZZu8tcnYtkZjRapeuGeLWF2D9J24YL7QiHt6e`.
Live entry: V2 (Lucid Locus, submission `01a1d23a-d320-7142-af33-93a98a0f7ddf`).
V3 is a resubmission candidate built 2026-11-13 ~09:30 WIB (sprint, report due
11:30 WIB; parent decides whether to submit).

## What V3 changes (one idea: finer kernel bins)

V2's empirical kernel was binned by start-rank x horizon (1-6, 7-18, 19-36,
37-60, 61-72 h) x chart-age (binary: first seen <72 h vs older). V3 splits
both binning dimensions finer:

- chart-age: 0-24 h, 1-3 d, 3-7 d, 7 d+ (a game first seen 12 h ago behaves
  differently from one first seen 60 h ago; the binary split hid that).
- horizon: 1-3, 4-9, 10-18, 19-36, 37-60, 61-72 h (the 1-3 h split
  separates the immediate-churn regime, which matters most for the first
  answer reads).

Each bin still needs >= 30 pairs, with fallback to other age bins, then
age-merged, then no kernel (diffusion only). Everything else is V2 exactly:
EWMA velocity (last 4 steps, 24 h half-life, clamp +-2.5/h, 6 h saturation),
Normal diffusion (median |dRank|/sqrt(gap), clamp [0.25, 1.0], cap 14),
65/35 Normal/kernel blend, hourly averaging, temperature 1.15, top 30
candidates/place above 0.003 rescaled to 0.75 named (0.25 unnamed reserve),
28-day age-out, top10 by total P(in top 10).

## Validation (local scorer, exact RULES rule, log score is the rank metric)

Practice (origin = last kit read Nov 7 20:53Z, answer = 10 reads Nov 8-10):
- V3: **-34.9854**, hits 7.30, agreement 60.9 (197 rows, place sums 0.75)
- V2: -35.1201, hits 7.30, agreement 62.2
- House baseline: -43.51

Cross-validation (origins truncated, future reads within 72 h, >= 3 reads):
- origins 12-21: V3 -37.6047 vs V2 -37.6227
- origins 6-11:  V3 -35.1169 vs V2 -35.1214
- origins 22-33: V3 -35.8389 vs V2 -35.8744 (extra check added by the sprint)

V3 beats V2 on log score in all four evaluations. Margins are small
(+0.005 to +0.135) but consistent in sign — the only variant in the whole
sprint grid that improved on every evaluation. Determinism verified: two
runs of the shipped `main.py` on kit practice input are byte-identical.

## What else was tried in the sprint (all measured practice + CV12-21 + CV6-11)

Advisor consultations (APInex, cost 0): free/deepseek-v4-pro-0813 (heavy
reasoning), free/gpt-6-luna (second opinion), free/gemini-3.8-flash via the
second APInex key (third opinion). Harness: `roblox-forecast-research/
exp_v3.py` (parameterized copy of V2; baseline reproduces V2 exactly:
-35.1201 / -37.6227 / -35.1214). Grids in `exp_v3_grid1/2/3.log`.

- Kernel collapse to 2-way (rank x horizon, Gemini's #1 pick): practice
  -35.2071, CV12-21 -37.6317 — WORSE. The age signal is real; dropping it
  hurts. 1-way kernel: -35.0294 practice but CV6-11 -35.9992 — reject.
  2-way rank x age: practice -34.8193 but CV12-21 -38.0915 — reject.
  No kernel at all: -35.4300 — the kernel earns its keep.
- Temperature 1.0 (Gemini proposal 3, first half): -35.3034 practice,
  worse everywhere. Temperature 1.25: practice -34.9727 but CV12-21
  -37.6922 — reject. V2's 1.15 stays.
- Named/reserve split sweep 0.6/0.7/0.8 (Gemini proposal 2): all worse
  than 0.75 (0.6: -35.6880; 0.7: -35.2069; 0.8: -35.1652). Churn-based
  per-place split: -36.7479 practice, -39.8332 CV12-21 — much worse,
  reject. The 0.75/0.25 split is near-optimal on this data. (Note: the
  unnamed reserve is spread UNIFORMLY by the grader, so "velocity-weighted
  reserve" is not implementable — the only lever is how much mass is named.)
- Sigma widening for long horizons (Gemini proposal 3, second half):
  x1.5 for h>36: practice -35.2056 (worse); linear widening: -35.2580
  (worse). Luna's opposite idea (sigma shrinking with horizon): practice
  -35.0130 but CV12-21 -37.7666 — reject. Per-rank-bucket sigma: practice
  -35.0107 but CV6-11 -37.6519 — reject.
- Velocity variants: long (8 steps, 48 h half-life): -35.5836 — worse.
  Short (2 steps, 12 h half-life): practice -34.8378, CV6-11 -34.9975,
  but CV12-21 -37.6635 (slightly worse) — alone it fails the rule.
  Combined with fine age bins it passes the original 3 evaluations
  (practice -34.7981, CV12-21 -37.6060, CV6-11 -34.9915) but FAILS the
  late-origin check (CV22-33 -35.9378 vs V2 -35.8744) and drops hits to
  6.40 — higher variance alternative, NOT recommended over V3.
- Floor 0.0 (name everything): practice -34.9405 but CV12-21 -38.0270,
  CV6-11 -36.0546 — reject. Cap 100: identical (cap 30 never binds).
  Alpha 0.5/0.2: both worse. Top-20 kernel routing (Gemini's C): practice
  -35.1095, CV worse — reject. min_pairs 15: practice -34.8548 but
  CV6-11 -35.3044 — reject. min_pairs 50: worse everywhere.
- Playing-count growth as a feature: diagnostic first — correlation
  between past-24h log playing growth and next-24h rank change is -0.017
  (2,786 pairs, no quartile pattern). NOT a signal; not implemented.
  (Rank already prices playing growth — the chart is a growth sort.)

## Advisor errors caught (do not repeat)

- All three APInex advisors (deepseek, luna, gemini) misread the newcomer
  rate as "8 of 10 slots (80%)". The verified fact is **8 of 100 slots
  (8%)**. Any "birth process" reasoning built on 80% is wrong; the
  newcomer mass is small and the 0.25 unnamed reserve already covers it.
- Deepseek's idea #3 (trajectory-weighted scoring) is NOT implementable:
  the competition's scorer is FIXED (mean log score per read, one
  distribution); the forecast cannot change how the grader scores.
- Gemini claimed the reserve allocation "is already velocity-weighted" —
  false; the grader spreads unnamed mass uniformly. Gemini's "new entrant
  feature" (recommendation A) is also already present: the kernel's age
  split IS the new-entrant feature; V3 refines it.
- Luna's horizon-adaptive diffusion (sigma shrinking with horizon) is the
  opposite of Gemini's widening; both were tested — both fail.

## Most influential advisor quote

Deepseek-v4-pro-0813 (on the kernel): "The empirical kernel is the largest
variance source... age-bucket <72h arbitrary, CV spread 2.5 points mostly
kernel noise." That pointed at the kernel binning — but the fix that worked
was FINER bins (V3), not collapsing them: collapsing the kernel (Gemini's
#1 pick) made things worse, because the age signal is real and the 30-pair
floor plus fallback already regularizes the thin bins.

## The -13.2 cluster (unchanged from V2)

The 20 best practice entries score -13.2 with identical values. The oracle
(per-place distribution fitted ON the 10 answer reads themselves) scores
-13.1793, and the answers contain a game absent from the chart when
history ended. The cluster is in-sample, not a legitimate target; the final
(13-16 Nov) is graded out-of-sample for everyone, so it should collapse.
V3's -34.99 is the honest out-of-sample level of this method; a prize is
possible but NOT guaranteed.

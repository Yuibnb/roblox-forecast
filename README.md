# Roblox Up-and-Coming top-10 forecaster — V3

Entry for make.fun `roblox-up-and-coming-forecast-01` ($500 in USDC).
Resubmission replacing the V2 entry (Lucid Locus, submission
`01a1d23a-d320-7142-af33-93a98a0f7ddf`, practice -35.12).

V3 is V2 with one change: finer empirical-kernel bins (chart-age split into
0-24 h / 1-3 d / 3-7 d / 7 d+ instead of one binary split at 72 h, and
horizon split into 1-3 / 4-9 / 10-18 / 19-36 / 37-60 / 61-72 h instead of
1-6 / 7-18 / ...). Everything else (velocity, diffusion, blend, temperature,
named/reserve split) is unchanged.

Validation (local scorer, exact competition rule):
practice -34.9854 (hits 7.30, agreement 60.9) vs V2 -35.1201; CV origins
12-21: -37.6047 vs -37.6227; CV origins 6-11: -35.1169 vs -35.1214; CV
origins 22-33: -35.8389 vs -35.8744. V3 beats V2 on log score in all four
evaluations; margins are small (+0.005 to +0.135) but consistent in sign.

Run: `MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=<out> python3 main.py`
— stdlib only, deterministic (two runs byte-identical), no network.

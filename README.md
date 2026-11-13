# Roblox Up-and-Coming top-10 forecaster — V2

Entry for make.fun `roblox-up-and-coming-forecast-01` ($500 in USDC).
Resubmission replacing the V1 entry (Adept Cipher, server score -36.10).

## Method

Rank-diffusion forecast blended with a horizon- and age-binned empirical
transition kernel, averaged hour by hour over the 72 h window. Per place,
the best 30 candidates are named and rescaled to 0.75, leaving a 0.25
unnamed reserve for games entering the chart mid-window. Games age out
28 days after creation when the history carries a `created` date.

See `NOTES.md` for the full method, the evidence, and the validation.

## Validation (local scorer, exact RULES rule)

| | practice log score | hits | agreement |
|---|---:|---:|---:|
| V1 (shipped) | -37.16 | 6.40 | 52.7 |
| **V2 (this entry)** | **-35.12** | 7.30 | 62.2 |
| house baseline | -43.51 | 6.40 | 53.5 |

Cross-validation: V2 beats V1 on log score on both origin sets
(12-21: -37.62 vs -38.31; 6-11: -35.12 vs -35.87).

## Run it

```sh
MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library only, no network, deterministic
(two runs byte-identical).

## License

MIT — see `LICENSE`.

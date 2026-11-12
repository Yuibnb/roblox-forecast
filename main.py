#!/usr/bin/env python3
"""Roblox Up-and-Coming top-10 forecaster (make.fun roblox-up-and-coming-forecast-01).

Method (validated on the practice instance, see NOTES.md):
  * Empirical rank-persistence profiles: for every past snapshot (origin), look at
    where each game ranked in the reads of the following 72 h, pooled by the
    game's rank at the origin (ranks 1..10 individually, then bands 11-20,
    21-50, 51+). Origins are recency-weighted (half-life 96 h) and the
    profiles are smoothed across neighbouring places (3-point moving average).
  * Growth adjustment: a game's 48 h log playing-growth, percentile-ranked
    against the other games on the chart, shifts its profile up/down by up to
    0.5 places (fast growers climb, slow growers sink). Playing growth leads
    rank by ~24 h (corr -0.25); rank momentum itself does not predict.
  * Age-out: a game published more than 28 days before a window read leaves
    the chart. When the latest `details` carry a `created` date, the game's
    probabilities are scaled by the fraction of the window before it ages
    out, and the freed mass is redistributed proportionally within each place.
  * Every game with p >= 0.001 is named (truncating the tail looked better on
    the single 10-read practice window but was worse on 16 cross-validated
    origins, so the tail stays).

Stdlib only, deterministic, no network, no wall clock: every timestamp comes
from the input files. Reads $MAKEFUN_INPUT_DIR (default /input) and writes
$MAKEFUN_OUTPUT_DIR/<task.output> (default /output/forecast.json).
"""

import bisect
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

WINDOW_HOURS = 72.0
RECENCY_HALF_LIFE_H = 96.0
GROWTH_HOURS = 48.0
SHIFT_PLACES = 0.5
MIN_P = 0.001
MAX_AGE_DAYS = 28


def parse_ts(s):
    if s is None:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def bucket_of(rank):
    if rank <= 10:
        return rank
    if rank <= 20:
        return 11
    if rank <= 50:
        return 21
    return 51


def chart_map(snap):
    """universe_id -> (rank, playing)."""
    out = {}
    for g in snap.get("up_and_coming") or []:
        out[int(g["universe_id"])] = (int(g["rank"]), int(g["playing"] or 0))
    return out


def build_profiles(snaps, times):
    """profiles[bucket][place] = P(rank=place in a future read within 72h)."""
    n = len(snaps)
    prof = defaultdict(Counter)
    tot = defaultdict(float)
    last_t = times[-1]
    for i in range(n):
        t0 = times[i]
        fut = [j for j in range(i + 1, n)
               if (times[j] - t0).total_seconds() <= WINDOW_HOURS * 3600]
        if not fut:
            continue
        age_h = (last_t - t0).total_seconds() / 3600.0
        w = 0.5 ** (age_h / RECENCY_HALF_LIFE_H)
        origin = chart_map(snaps[i])
        fut_maps = [chart_map(snaps[j]) for j in fut]
        for uid, (r, _p) in origin.items():
            b = bucket_of(r)
            for fm in fut_maps:
                tot[b] += w
                rr = fm.get(uid)
                if rr is not None:
                    prof[b][rr[0]] += w
    out = {}
    for b in tot:
        out[b] = {k: v / tot[b] for k, v in prof[b].items() if k <= 15}
    return out


def smooth_profiles(profiles):
    out = {}
    for b, prof in profiles.items():
        sm = {}
        for k in range(1, 16):
            vals = [prof.get(k + d, 0.0) for d in (-1, 0, 1) if 1 <= k + d <= 15]
            sm[k] = sum(vals) / len(vals)
        out[b] = sm
    return out


def interp_prob(prof, x):
    if x < 1:
        return prof.get(1, 0.0)
    if x > 15:
        return 0.0
    lo = math.floor(x)
    hi = math.ceil(x)
    if lo == hi:
        return prof.get(lo, 0.0)
    return prof.get(lo, 0.0) + (prof.get(hi, 0.0) - prof.get(lo, 0.0)) * (x - lo)


def growth_over(snaps, times, origin_i, uid, hours):
    """Log playing growth over ~`hours` before snapshot origin_i; None if n/a."""
    t_i = times[origin_i]
    cur = chart_map(snaps[origin_i]).get(uid)
    if not cur or cur[1] <= 0:
        return None
    j = None
    for jj in range(origin_i, -1, -1):
        if (t_i - times[jj]).total_seconds() >= hours * 3600:
            j = jj
            break
    if j is None:
        j = 0
    prev = chart_map(snaps[j]).get(uid)
    if not prev or prev[1] <= 0:
        return None
    dt = (t_i - times[j]).total_seconds() / 3600.0
    if dt < 6:
        return None
    return math.log(cur[1] / prev[1])


def latest_created(snaps):
    """universe_id -> created datetime, from the newest snapshot carrying details."""
    created = {}
    for snap in reversed(snaps):
        det = snap.get("details")
        if not det:
            continue
        for key, val in det.items():
            try:
                uid = int(key)
            except (TypeError, ValueError):
                continue
            if uid in created or not isinstance(val, dict):
                continue
            c = parse_ts(val.get("created"))
            if c is not None:
                created[uid] = c
        if len(created) >= 200:
            break
    return created


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    with open(os.path.join(in_dir, "task.json")) as f:
        task = json.load(f)
    places = int(task.get("places", 10))
    out_name = task.get("output", "forecast.json")
    window_from = parse_ts(task["window"]["from"])
    window_until = parse_ts(task["window"]["until"])
    window_h = (window_until - window_from).total_seconds() / 3600.0

    snaps = []
    with open(os.path.join(in_dir, "history.ndjson")) as f:
        for line in f:
            line = line.strip()
            if line:
                snaps.append(json.loads(line))
    times = [parse_ts(s["at"]) for s in snaps]
    origin_i = len(snaps) - 1
    origin = chart_map(snaps[origin_i])

    profiles = smooth_profiles(build_profiles(snaps, times))

    # 48h playing growth, percentile-ranked across the chart.
    growths = {}
    for uid in origin:
        g = growth_over(snaps, times, origin_i, uid, GROWTH_HOURS)
        if g is not None:
            growths[uid] = g
    sorted_g = sorted(growths.values())

    def growth_pct(uid):
        g = growths.get(uid)
        if g is None or not sorted_g:
            return 0.5
        return bisect.bisect_left(sorted_g, g) / len(sorted_g)

    # Per-game, per-place probabilities.
    probs = {}
    p_top10 = {}
    for uid in sorted(origin):
        r, _p = origin[uid]
        prof = profiles.get(bucket_of(r))
        if not prof:
            continue
        shift = SHIFT_PLACES * (growth_pct(uid) - 0.5) * 2.0
        for k in range(1, places + 1):
            v = interp_prob(prof, k + shift)
            if v > 0:
                probs[(uid, k)] = v
        p_top10[uid] = sum(probs.get((uid, k), 0.0) for k in range(1, places + 1))

    # Age-out: scale by the eligible fraction of the window, then redistribute
    # the freed mass proportionally within each place.
    created = latest_created(snaps)
    if created:
        pre_sum = {k: sum(v for (u, kk), v in probs.items() if kk == k)
                   for k in range(1, places + 1)}
        for uid in list(p_top10):
            c = created.get(uid)
            if c is None:
                continue
            age_out = c + timedelta(days=MAX_AGE_DAYS)
            frac = (age_out - window_from).total_seconds() / 3600.0 / window_h
            frac = max(0.0, min(1.0, frac))
            if frac < 1.0:
                for k in range(1, places + 1):
                    if (uid, k) in probs:
                        probs[(uid, k)] *= frac
        for k in range(1, places + 1):
            post = sum(v for (u, kk), v in probs.items() if kk == k)
            if post > 0 and pre_sum[k] > post:
                factor = min(pre_sum[k], 1.0) / post
                for key in [key for key in probs if key[1] == k]:
                    probs[key] *= factor
        p_top10 = {uid: sum(probs.get((uid, k), 0.0) for k in range(1, places + 1))
                   for uid in p_top10}

    # Drop negligible rows; cap each place at 1.
    probs = {(u, k): v for (u, k), v in probs.items() if v >= MIN_P}
    for k in range(1, places + 1):
        s = sum(v for (u, kk), v in probs.items() if kk == k)
        if s > 1.0:
            for key in [key for key in probs if key[1] == k]:
                probs[key] /= s

    # top10: highest P(in top 10); ties broken by current rank, then id.
    ranked = sorted(p_top10.items(),
                    key=lambda kv: (-kv[1], origin.get(kv[0], (10 ** 9,))[0], kv[0]))
    top10 = [uid for uid, _ in ranked[:places]]
    # Fallback (should not happen): pad with the current chart order.
    if len(top10) < places:
        for g in snaps[origin_i].get("up_and_coming") or []:
            uid = int(g["universe_id"])
            if uid not in top10:
                top10.append(uid)
            if len(top10) == places:
                break

    rows = [{"universe_id": u, "place": k, "p": round(v, 6)}
            for (u, k), v in sorted(probs.items(), key=lambda kv: (kv[0][1], -kv[1], kv[0][0]))]
    out = {"probabilities": rows, "top10": top10}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, out_name), "w") as f:
        json.dump(out, f)
        f.write("\n")
    print(f"wrote {os.path.join(out_dir, out_name)}: "
          f"{len(rows)} rows, {len(top10)} top10, "
          f"place sums {[round(sum(v for (u, kk), v in probs.items() if kk == k), 3) for k in range(1, places + 1)]}")


if __name__ == "__main__":
    main()

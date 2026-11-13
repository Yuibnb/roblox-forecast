#!/usr/bin/env python3
"""Roblox Up-and-Coming top-10 forecaster v3 (make.fun roblox-up-and-coming-forecast-01).

V3 = V2 with finer empirical-kernel bins (the single change that improved
practice AND every cross-validation set; see NOTES.md):
  * chart-age bins: 0-24 h, 1-3 d, 3-7 d, 7 d+ (V2 used one binary split
    at 72 h). Fresh games behave differently at 12 h old than at 60 h old,
    and the finer split lets the kernel price that without memorizing the
    practice window (each bin still needs >= 30 pairs, with fallback to
    other ages, then age-merged).
  * horizon bins: 1-3, 4-9, 10-18, 19-36, 37-60, 61-72 h (V2 merged 1-6 h).
    Early hours matter most for the first answer reads, and the split at
    3 h separates the immediate-churn regime from the rest.
Everything else is V2 exactly: EWMA velocity (last 4 steps, 24 h half-life,
clamp 2.5 ranks/h, 6 h saturation), Normal diffusion (median |rank change| /
sqrt(gap), clamp [0.25, 1.0], cap 14), blend 65% Normal / 35% kernel,
hourly averaging over the window, temperature 1.15, top 30 candidates per
place above 0.003 rescaled to 0.75 named (0.25 unnamed reserve), 28-day
age-out, top10 by total P(in top 10).

Validation (local scorer, exact RULES rule; practice answer = 10 archive
reads Nov 8-10, origin = last kit read Nov 7 20:53Z):
  * V3 practice: log score -34.9854, hits 7.30, agreement 60.9
    (V2 shipped entry: -35.1201 / 7.30 / 62.2; house baseline: -43.51).
  * Cross-validation, origins 12-21: V3 -37.6047 vs V2 -37.6227.
  * Cross-validation, origins 6-11: V3 -35.1169 vs V2 -35.1214.
  * Cross-validation, origins 22-33: V3 -35.8389 vs V2 -35.8744.
  V3 beats V2 on log score in all four evaluations (margins are small,
  +0.005 to +0.135, but consistent in sign). The public leaderboard's
  -13.2 cluster equals the oracle score (distribution fitted on the answer
  reads themselves, which include a game not on the chart at all), so it
  is in-sample and not a legitimate target; -35.0 is the honest
  out-of-sample level of this method.

Stdlib only, deterministic, no network, no wall clock: every timestamp
comes from the input files. Reads $MAKEFUN_INPUT_DIR (default /input) and
writes $MAKEFUN_OUTPUT_DIR/<task.output> (default /output/forecast.json).
"""

import json
import math
import os
from datetime import datetime, timedelta

ALPHA = 0.35          # empirical-kernel blend weight (Normal gets 1-ALPHA)
TEMP = 1.15           # temperature on the hourly averages (>1 sharpens)
NAMED = 0.75          # probability mass named per place (rest is unnamed)
SIGMA_MAX = 1.0       # clamp on the fitted diffusion width
SIGMA_MIN = 0.25
SPREAD_CAP = 14.0     # cap on the Normal spread, in ranks
VEL_TAU = 6.0         # velocity saturation timescale, hours
VEL_CLAMP = 2.5       # ranks per hour
VEL_HALFLIFE = 24.0   # velocity recency half-life, hours
CAP = 30              # candidates named per place
FLOOR = 0.003         # minimum average probability to name
MIN_PAIRS = 30        # pairs needed before a kernel bin is trusted
MAX_AGE_DAYS = 28     # games leave the chart this long after creation

RANK_BUCKETS = [(1, 10), (11, 20), (21, 50), (51, 1000000)]
# V3: finer horizon split (1-3 h separated from 4-9 h).
HOUR_BUCKETS = [(1, 3), (4, 9), (10, 18), (19, 36), (37, 60), (61, 72)]
N_AGE_BINS = 4        # V3: 0-24 h, 1-3 d, 3-7 d, 7 d+ (V2: binary at 72 h)


def parse_ts(s):
    if s is None:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def rank_bucket(rank):
    if rank <= 10:
        return rank
    if rank <= 20:
        return 11
    if rank <= 50:
        return 21
    return 51


def hour_bucket(hour):
    for index, (low, high) in enumerate(HOUR_BUCKETS):
        if low <= hour <= high:
            return index
    return len(HOUR_BUCKETS) - 1


def age_bucket(age_hours):
    """V3 chart-age bin: 0 = 0-24 h, 1 = 1-3 d, 2 = 3-7 d, 3 = 7 d+."""
    if age_hours < 24:
        return 0
    if age_hours < 72:
        return 1
    if age_hours < 168:
        return 2
    return 3


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    with open(os.path.join(in_dir, "task.json")) as f:
        task = json.load(f)
    places = int(task.get("places", 10))
    window = task.get("window") or {}
    slots = int(window.get("slots", 72))
    out_name = task.get("output", "forecast.json")

    reads = []
    with open(os.path.join(in_dir, "history.ndjson")) as f:
        for line in f:
            line = line.strip()
            if line:
                reads.append(json.loads(line))
    reads.sort(key=lambda rec: parse_ts(rec["at"]))
    times = [parse_ts(rec["at"]) for rec in reads]
    charts = [{int(row["universe_id"]): int(row["rank"])
               for row in rec.get("up_and_coming") or []}
              for rec in reads]
    last_time = times[-1]
    last_chart = charts[-1]

    # Per-game rank series, first-seen time, and creation date (when given).
    series = {}
    first_seen = {}
    created = {}
    for rec, when, chart in zip(reads, times, charts):
        for uid in chart:
            series.setdefault(uid, []).append((when, chart[uid]))
            if uid not in first_seen:
                first_seen[uid] = when
        for key in sorted(rec.get("details") or {}):
            info = rec["details"][key] or {}
            stamp = info.get("created")
            if not stamp:
                continue
            try:
                uid = int(key)
            except (TypeError, ValueError):
                continue
            if uid not in created:
                made = parse_ts(stamp)
                if made is not None:
                    created[uid] = made

    # Empirical transition kernel: counts[(rank bucket, hour bucket,
    # age bucket)][place] = landings inside the top 10; totals also count
    # landings outside it, so each bin's distribution sums to P(staying
    # in the top 10). Built from every pair of reads up to 72 h apart.
    counts = {}
    totals = {}
    n_reads = len(reads)
    for i in range(n_reads):
        start = times[i]
        for j in range(i + 1, n_reads):
            gap = (times[j] - start).total_seconds() / 3600.0
            if gap > 72:
                break
            hb = hour_bucket(max(1, int(round(gap))))
            for uid, rank2 in charts[j].items():
                rank1 = charts[i].get(uid)
                if rank1 is None:
                    continue
                age = (start - first_seen[uid]).total_seconds() / 3600.0
                ab = age_bucket(age)
                key = (rank_bucket(rank1), hb, ab)
                totals[key] = totals.get(key, 0) + 1
                if rank2 <= places:
                    counts.setdefault(key, [0] * places)[rank2 - 1] += 1

    def kernel_dist(rb, hb, ab):
        """P(place) for a bin, falling back to coarser bins when thin.
        Order: the game's own age bin, then the other age bins (newest
        first is not assumed -- any bin with enough pairs will do), then
        all ages merged. Every step still needs >= MIN_PAIRS."""
        for other_age in [ab] + [a for a in range(N_AGE_BINS) if a != ab]:
            key = (rb, hb, other_age)
            if totals.get(key, 0) >= MIN_PAIRS:
                total = totals[key]
                return [c / total for c in counts.get(key, [0] * places)]
        merged = [0] * places
        total = 0
        for other_age in range(N_AGE_BINS):
            key = (rb, hb, other_age)
            if key in totals:
                for p in range(places):
                    merged[p] += counts.get(key, [0] * places)[p]
                total += totals[key]
        if total >= MIN_PAIRS:
            return [c / total for c in merged]
        return None

    # Diffusion width: median |rank change| / sqrt(gap), scaled to a
    # Normal standard deviation. 0.55 when there is no data.
    steps = []
    for uid in sorted(series):
        points = series[uid]
        for (t_a, r_a), (t_b, r_b) in zip(points, points[1:]):
            gap = (t_b - t_a).total_seconds() / 3600.0
            if gap > 0:
                steps.append(abs(r_b - r_a) / math.sqrt(gap))
    sigma = median(steps) / 0.6745 if steps else 0.55
    sigma = min(SIGMA_MAX, max(SIGMA_MIN, sigma))

    def velocity(uid):
        """Recent rank drift per hour, weighted toward the newest steps."""
        points = series[uid]
        pairs = list(zip(points, points[1:]))[-4:]
        weighted = 0.0
        weight_total = 0.0
        for (t_a, r_a), (t_b, r_b) in pairs:
            gap = (t_b - t_a).total_seconds() / 3600.0
            if gap <= 0:
                continue
            age = (last_time - t_b).total_seconds() / 3600.0
            w = 0.5 ** (age / VEL_HALFLIFE)
            weighted += w * ((r_b - r_a) / gap)
            weight_total += w
        if weight_total == 0:
            return 0.0
        return min(VEL_CLAMP, max(-VEL_CLAMP, weighted / weight_total))

    # Average per-place probabilities over the forecast hours.
    averages = {}
    for uid in sorted(last_chart):
        rank0 = last_chart[uid]
        drift = velocity(uid)
        born = created.get(uid)
        expiry = born + timedelta(days=MAX_AGE_DAYS) if born else None
        rb = rank_bucket(rank0)
        age_now = (last_time - first_seen[uid]).total_seconds() / 3600.0
        ab = age_bucket(age_now)
        sums = [0.0] * places
        for hour in range(1, slots + 1):
            # Past expiry every later hour is expired too: stop here, and
            # the average below still divides by the full window.
            if expiry is not None and last_time + timedelta(hours=hour) > expiry:
                break
            displacement = drift * VEL_TAU * (1.0 - math.exp(-hour / VEL_TAU))
            mean = rank0 + displacement
            spread = min(SPREAD_CAP, sigma * math.sqrt(hour))
            hb = hour_bucket(hour)
            kern = kernel_dist(rb, hb, ab)
            sums[0] += ((1.0 - ALPHA) * norm_cdf((1.5 - mean) / spread)
                        + (ALPHA * kern[0] if kern else 0.0))
            for place in range(2, places + 1):
                normal_p = (norm_cdf((place + 0.5 - mean) / spread)
                            - norm_cdf((place - 0.5 - mean) / spread))
                sums[place - 1] += ((1.0 - ALPHA) * normal_p
                                    + (ALPHA * kern[place - 1]
                                       if kern else 0.0))
        vals = [total / slots for total in sums]
        if TEMP != 1.0:
            vals = [value ** TEMP for value in vals]
        averages[uid] = vals

    # Per place: keep the best candidates above the floor, at most CAP,
    # rescaled to sum to exactly NAMED (the rest is the unnamed reserve).
    rows = []
    for place in range(1, places + 1):
        candidates = [(averages[uid][place - 1], uid)
                      for uid in sorted(averages)
                      if averages[uid][place - 1] > FLOOR]
        candidates.sort(key=lambda item: (-item[0], item[1]))
        candidates = candidates[:CAP]
        total = sum(prob for prob, _ in candidates)
        if total <= 0:
            continue
        scaled = [(uid, prob / total * NAMED) for prob, uid in candidates]
        rounded = [(uid, round(prob, 6)) for uid, prob in scaled]
        drift_fix = round(NAMED - sum(prob for _, prob in rounded), 6)
        if drift_fix and rounded:
            widest = max(range(len(rounded)),
                         key=lambda index: rounded[index][1])
            uid, prob = rounded[widest]
            rounded[widest] = (uid, round(prob + drift_fix, 6))
        for uid, prob in rounded:
            rows.append({"universe_id": uid, "place": place, "p": prob})
    rows.sort(key=lambda row: (row["place"], -row["p"], row["universe_id"]))

    # top10: the games with the highest total P(in top 10); ties broken
    # by current rank, then universe id.
    p_top10 = {}
    for row in rows:
        p_top10[row["universe_id"]] = (p_top10.get(row["universe_id"], 0.0)
                                        + row["p"])
    ranked = sorted(p_top10.items(),
                    key=lambda kv: (-kv[1], last_chart.get(kv[0], 10 ** 9),
                                    kv[0]))
    top10 = [uid for uid, _ in ranked[:places]]
    if len(top10) < places:
        for uid in sorted(last_chart, key=lambda u: last_chart[u]):
            if uid not in top10:
                top10.append(uid)
            if len(top10) == places:
                break

    out = {"probabilities": rows, "top10": top10}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, out_name), "w") as f:
        f.write(json.dumps(out) + "\n")
    print(f"wrote {os.path.join(out_dir, out_name)}: "
          f"{len(rows)} rows, {len(top10)} top10, "
          f"place sums {[round(sum(r['p'] for r in rows if r['place'] == k), 3) for k in range(1, places + 1)]}")


if __name__ == "__main__":
    main()

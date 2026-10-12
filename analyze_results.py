"""Summarise trial_history.jsonl: failure rate, best result and runtime per study."""
import json
import sys
from collections import defaultdict
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "trial_history.jsonl"
studies = defaultdict(list)
for line in path.read_text().splitlines():
    if line.strip():
        r = json.loads(line)
        studies[r.get("study", "legacy (no study tag)")].append(r)

for name, rows in studies.items():
    ok = [r for r in rows if r.get("score") is not None]
    mean_min = sum(r["elapsed_sec"] for r in rows) / len(rows) / 60
    print(f"\n== {name} ==")
    print(f"records: {len(rows)}  scored: {len(ok)}  failed: {len(rows) - len(ok)} "
          f"({100 * (len(rows) - len(ok)) / len(rows):.0f}% failure)  mean runtime: {mean_min:.1f} min")
    if ok:
        b = min(ok, key=lambda r: r["score"])
        m = b["metrics"]
        print(f"best score {b['score']:.3f}: WNS {m['setup_ws']:.3f} ns, power {m['power_total']:.3f} W, "
              f"core area {m['core_area']:.0f} um2, utilization {m['utilization']:.2f}")

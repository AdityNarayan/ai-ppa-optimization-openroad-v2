import json
import sys
from pathlib import Path

METRIC_KEYS = {
    "setup_ws": "finish__timing__setup__ws",
    "setup_tns": "finish__timing__setup__tns",
    "hold_ws": "finish__timing__hold__ws",
    "hold_tns": "finish__timing__hold__tns",
    "setup_viol_cnt": "finish__timing__drv__setup_violation_count",
    "hold_viol_cnt": "finish__timing__drv__hold_violation_count",
    "fmax": "finish__timing__fmax",
    "power_total": "finish__power__total",
    "power_internal": "finish__power__internal__total",
    "power_switching": "finish__power__switching__total",
    "power_leakage": "finish__power__leakage__total",
    "die_area": "finish__design__die__area",
    "core_area": "finish__design__core__area",
    "utilization": "finish__design__instance__utilization",
    "warnings": "finish__flow__warnings__count",
    "errors": "finish__flow__errors__count",
}

def find_metrics_file(results_root, platform, design, variant="base"):
    return Path(results_root) / "logs" / platform / design / variant / "6_report.json"

def parse_metrics(json_path):
    if not json_path.exists():
        return {"_error": f"metrics file not found: {json_path}", "_success": False}
    try:
        with open(json_path, "r") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        return {"_error": f"invalid JSON in {json_path}: {e}", "_success": False}
    result = {"_success": True, "_error": None}
    missing = []
    for clean_name, real_key in METRIC_KEYS.items():
        if real_key in raw:
            result[clean_name] = raw[real_key]
        else:
            result[clean_name] = None
            missing.append(real_key)
    if missing:
        result["_missing_keys"] = missing
    return result

# Reference design point used to normalise power and area (AES-128, sky130hd,
# ORFS default config). Change these if you switch design or PDK.
BASELINE = {"power_total": 0.583, "core_area": 220156.0}

def compute_ppa_score(metrics, weights=None):
    """Scalar PPA cost, lower is better.

    score = w_t * timing_penalty + w_p * power/BASELINE.power + w_a * area/BASELINE.area

    timing_penalty is 0 when setup WNS >= 0 (timing met) and
    10*|WNS| + |TNS| otherwise. Design choice: once timing is met there is no
    extra reward for more slack, so the optimiser then trades only power and
    area. Failed runs score inf.
    """
    if not metrics.get("_success"):
        return float("inf")
    if weights is None:
        weights = {"timing": 1.0, "power": 1.0, "area": 1.0}
    setup_ws = metrics.get("setup_ws") or 0.0
    setup_tns = metrics.get("setup_tns") or 0.0
    power = metrics.get("power_total") or 0.0
    core_area = metrics.get("core_area") or 0.0
    timing_penalty = 0.0
    if setup_ws < 0:
        timing_penalty = abs(setup_ws) * 10.0 + abs(setup_tns) * 1.0
    power_norm = power / BASELINE["power_total"]
    area_norm = core_area / BASELINE["core_area"]
    return weights["timing"] * timing_penalty + weights["power"] * power_norm + weights["area"] * area_norm

def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_metrics.py <path_to_6_report.json>")
        sys.exit(1)
    json_path = Path(sys.argv[1])
    metrics = parse_metrics(json_path)
    print(json.dumps(metrics, indent=2))
    if metrics.get("_success"):
        score = compute_ppa_score(metrics)
        print(f"\nComputed PPA score (lower=better): {score:.4f}")

if __name__ == "__main__":
    main()

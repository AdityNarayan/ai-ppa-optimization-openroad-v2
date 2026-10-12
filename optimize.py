import argparse
import json
import os
import time
from pathlib import Path
from functools import partial
import optuna

from search_space import suggest_params
from runner import run_trial, get_metrics_path, cleanup_trial
from parse_metrics import parse_metrics, compute_ppa_score

# All outputs live next to the code so the dashboard (app.py) and a fresh clone
# always read and write the same files. Override with PPA_DATA_DIR if needed.
DATA_DIR = Path(os.environ.get("PPA_DATA_DIR", Path(__file__).resolve().parent))
LOG_FILE = DATA_DIR / "trial_history.jsonl"
BEST_FILE = DATA_DIR / "best_result.json"
STORAGE = f"sqlite:///{DATA_DIR / 'optuna_study.db'}"


def objective(trial, timeout_seconds, weights, meta):
    params = suggest_params(trial)
    print(f"\n{'='*60}\nTrial {trial.number}: {params}\n{'='*60}")
    start = time.time()
    run_result = run_trial(params, trial.number, timeout_seconds=timeout_seconds)
    elapsed = time.time() - start
    record = {
        **meta,
        "trial_number": trial.number,
        "params": params,
        "elapsed_sec": elapsed,
        "make_success": run_result["success"],
    }
    if not run_result["success"]:
        print(f"Trial {trial.number} FAILED (make returncode={run_result['returncode']}, elapsed={elapsed:.0f}s)")
        print("stdout tail:\n", run_result["stdout_tail"])
        print("stderr tail:\n", run_result["stderr_tail"])
        record["score"] = None
        record["error"] = "make_failed"
        record["returncode"] = run_result["returncode"]
        record["stdout_tail"] = run_result["stdout_tail"]
        record["stderr_tail"] = run_result["stderr_tail"]
        append_log(record)
        cleanup_trial(trial.number)
        return float("inf")
    metrics_path = get_metrics_path(trial.number)
    metrics = parse_metrics(metrics_path)
    if not metrics.get("_success"):
        print(f"Trial {trial.number}: metrics parse failed: {metrics.get('_error')}")
        record["score"] = None
        record["error"] = metrics.get("_error")
        append_log(record)
        cleanup_trial(trial.number)
        return float("inf")
    score = compute_ppa_score(metrics, weights)
    record["metrics"] = metrics
    record["score"] = score
    append_log(record)
    cleanup_trial(trial.number)
    print(f"Trial {trial.number}: score={score:.4f} (setup_ws={metrics['setup_ws']}, power={metrics['power_total']}, core_area={metrics['core_area']}, elapsed={elapsed:.0f}s)")
    return score


def append_log(record):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def make_sampler(name, seed):
    if name == "tpe":
        return optuna.samplers.TPESampler(seed=seed)
    if name == "random":
        return optuna.samplers.RandomSampler(seed=seed)
    raise ValueError(f"Unknown sampler: {name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=2400, help="Per-trial timeout in seconds (default 2400 = 40 min)")
    parser.add_argument("--sampler", choices=["tpe", "random"], default="tpe",
                        help="tpe = Bayesian optimization (Optuna TPE); random = baseline for comparison")
    parser.add_argument("--seed", type=int, default=42, help="Sampler seed, for reproducible runs")
    parser.add_argument("--study-name", default=None,
                        help="Defaults to aes_ppa_<sampler>_seed<seed>; one study per sampler/seed keeps runs separable")
    parser.add_argument("--w-timing", type=float, default=1.0)
    parser.add_argument("--w-power", type=float, default=1.0)
    parser.add_argument("--w-area", type=float, default=1.0)
    args = parser.parse_args()

    study_name = args.study_name or f"aes_ppa_{args.sampler}_seed{args.seed}"
    weights = {"timing": args.w_timing, "power": args.w_power, "area": args.w_area}
    meta = {"study": study_name, "sampler": args.sampler, "seed": args.seed, "weights": weights}

    study = optuna.create_study(
        direction="minimize",
        study_name=study_name,
        storage=STORAGE,
        sampler=make_sampler(args.sampler, args.seed),
        load_if_exists=True,
    )

    study.optimize(partial(objective, timeout_seconds=args.timeout, weights=weights, meta=meta),
                   n_trials=args.trials)
    print("\n\n===== OPTIMIZATION COMPLETE =====")
    print(f"Best score: {study.best_value:.4f}")
    print(f"Best params: {study.best_params}")
    with open(BEST_FILE, "w") as f:
        json.dump({"study": study_name, "best_score": study.best_value,
                   "best_params": study.best_params}, f, indent=2)
    print(f"\nFull trial history: {LOG_FILE}")
    print(f"Best result summary: {BEST_FILE}")


if __name__ == "__main__":
    main()

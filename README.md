# AI-Driven PPA Optimization using OpenROAD

Automatically explores floorplan, placement, and CTS parameters for a digital
design (AES-128 on the SkyWater sky130hd PDK), running the real OpenROAD
RTL-to-GDSII flow (via OpenROAD-flow-scripts) for every candidate configuration,
and uses Bayesian Optimization (Optuna) to search for the configuration that
minimizes a combined Power / Performance / Area (PPA) score.

## What this does

1. search_space.py defines the tunable parameters based on ORFS's own
   autotuner.json ranges for this design.
2. runner.py generates an isolated per-trial design config and runs the
   real make flow through OpenROAD-flow-scripts.
3. parse_metrics.py reads OpenROAD's 6_report.json output after each run
   and computes a scalar PPA score.
4. optimize.py runs the Optuna study: suggest parameters, run the real
   flow, score, repeat.
5. app.py is a Streamlit dashboard for viewing results and triggering new
   trials directly from a browser.

## Requirements

- OpenROAD + OpenROAD-flow-scripts built and working
- Python 3.10+
- pip install -r requirements.txt

## Usage

Run optimization trials (Bayesian / TPE, reproducible):
python3 optimize.py --trials 15 --timeout 2400 --sampler tpe --seed 42

Random-search baseline for comparison (same budget and seed):
python3 optimize.py --trials 15 --sampler random --seed 42

Summarise results (failure rate, best trial, runtime per study):
python3 analyze_results.py

All outputs (trial_history.jsonl, best_result.json, optuna_study.db) are written
next to the code; set PPA_DATA_DIR to change that.

Launch the dashboard:
streamlit run app.py



## Important: Runtime Expectations

This project drives the **real OpenROAD RTL-to-GDSII flow** for every trial —
it is not a simulation or mock. Each trial runs actual synthesis, floorplanning,
placement, clock-tree synthesis, and routing on real hardware.

- A single trial typically takes **15-40 minutes** depending on the parameters
  chosen (some configurations are more routing-congested or placement-heavy
  than others).
- In the logged runs, 31 of 44 trial records (about 70%) failed in the flow, so
  budget for this. (Run `python3 analyze_results.py` for the exact numbers.)
- Some trials will fail (routing congestion, placer crashes on edge-case
  parameters) — this is expected and part of what the optimizer learns to
  avoid over time. Failed trials are logged and scored as `inf` so Optuna
  steers away from similar configurations.
- Requires a working OpenROAD + OpenROAD-flow-scripts installation with the
  sky130hd PDK set up (not included in this repo — see
  https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts for setup).

## Baseline vs Best Result

| Metric | Baseline | Best Trial |
|---|---|---|
| Setup WNS | -0.111 ns | -0.045 ns |
| Setup violations | 28 | 7 |
| Power | 0.583 W | 0.643 W |
| Core area | 220156 um2 | 309710 um2 |
| PPA score | 4.10 | 3.09 |

## Scoring

score = w_t * timing_penalty + w_p * power / 0.583 W + w_a * core_area / 220156 um2

The timing penalty is 0 when setup WNS >= 0, otherwise 10*|WNS| + |TNS|. Power
and area are normalised to the ORFS default AES run (see BASELINE in
parse_metrics.py). The best trial above still has negative WNS (-0.045 ns): it
improves timing over the baseline by spending extra area (+41%) and power (+10%).
Weights can be changed with --w-timing / --w-power / --w-area.

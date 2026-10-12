import streamlit as st
import json
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

HISTORY_FILE = BASE_DIR / "trial_history.jsonl"
BEST_FILE = BASE_DIR / "best_result.json"
PID_FILE = BASE_DIR / ".optimizer.pid"

st.set_page_config(
    page_title="AES PPA Optimizer",
    page_icon="⚡",
    layout="wide"
)

def load_trials():
    trials = []
    if not HISTORY_FILE.exists():
        return trials
    try:
        with open(HISTORY_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    trials.append(data)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        st.error(f"Could not read trial history: {e}")
    return trials


def successful_trials(trials):
    valid = []
    for trial in trials:
        if trial.get("make_success") is True:
            score = trial.get("score")
            if score is not None:
                try:
                    if float(score) != float("inf"):
                        valid.append(trial)
                except Exception:
                    pass
    return valid


def get_best_trial(trials):
    valid = successful_trials(trials)
    if not valid:
        return None
    return min(valid, key=lambda x: float(x.get("score", float("inf"))))


def optimizer_running():
    if not PID_FILE.exists():
        return False, None
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True, pid
    except Exception:
        try:
            PID_FILE.unlink()
        except Exception:
            pass
        return False, None


st.title("AI-Driven PPA Optimization using OpenROAD")

st.markdown(
    """
    ### AES-128 on SKY130HD
    **AI-driven exploration of floorplan, placement and CTS parameters**
    """
)

st.sidebar.header("Dashboard Controls")

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

auto_refresh = st.sidebar.checkbox("Auto refresh", value=False)

if auto_refresh:
    time.sleep(5)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.write("### Run New Trial")

n_trials_input = st.sidebar.number_input("Number of trials", min_value=1, max_value=5, value=1)
timeout_input = st.sidebar.number_input("Timeout (minutes)", min_value=10, max_value=90, value=40)

running_now, running_pid = optimizer_running()

if running_now:
    st.sidebar.warning(f"A run is already active (PID {running_pid}). Wait for it to finish before starting another.")
else:
    if st.sidebar.button("▶️ Start New Trial(s)"):
        cmd = [
            "python3", str(BASE_DIR / "optimize.py"),
            "--trials", str(n_trials_input),
            "--timeout", str(int(timeout_input * 60)),
        ]
        log_file = open(BASE_DIR / "live_run.log", "a")
        proc = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT)
        PID_FILE.write_text(str(proc.pid))
        st.sidebar.success(f"Started (PID {proc.pid}). This runs in the background - each trial realistically takes 15-40+ minutes.")

st.sidebar.markdown("---")
st.sidebar.write("### Data Sources")
st.sidebar.code("trial_history.jsonl")
st.sidebar.code("best_result.json")

trials = load_trials()
valid_trials = successful_trials(trials)
best_trial = get_best_trial(trials)
running, pid = optimizer_running()

if running:
    st.success(f"🟢 Optimization is currently running — PID: {pid}")
else:
    st.info("🔵 Optimization is currently not running.")

total_trials = len(trials)
successful_count = len(valid_trials)
failed_count = total_trials - successful_count

st.subheader("Optimization Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Trials", total_trials)

with col2:
    st.metric("Successful Trials", successful_count)

with col3:
    st.metric("Failed Trials", failed_count)

with col4:
    if best_trial:
        st.metric("Best Score", f"{float(best_trial['score']):.4f}")
    else:
        st.metric("Best Score", "N/A")

st.subheader("🏆 Best Optimization Result")

if best_trial:
    metrics = best_trial.get("metrics", {})
    params = best_trial.get("params", {})

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric("Best Score", f"{float(best_trial['score']):.4f}")

    with c2:
        setup_ws = metrics.get("setup_ws")
        if setup_ws is not None:
            st.metric("Setup Slack", f"{float(setup_ws):.4f}")
        else:
            st.metric("Setup Slack", "N/A")

    with c3:
        power = metrics.get("power_total")
        if power is not None:
            st.metric("Power", f"{float(power):.4f}")
        else:
            st.metric("Power", "N/A")

    with c4:
        area = metrics.get("core_area")
        if area is not None:
            st.metric("Core Area", f"{float(area):,.0f}")
        else:
            st.metric("Core Area", "N/A")

    with c5:
        elapsed = best_trial.get("elapsed_sec")
        if elapsed is not None:
            minutes = float(elapsed) / 60
            st.metric("Runtime", f"{minutes:.1f} min")
        else:
            st.metric("Runtime", "N/A")

    st.write(f"**Best trial:** {best_trial.get('trial_number', 'N/A')}")

else:
    st.warning("No successful optimization trial with a valid score was found.")

if best_trial:
    st.subheader("⚙️ Best Configuration")
    params = best_trial.get("params", {})
    if params:
        parameter_rows = []
        for name, value in params.items():
            parameter_rows.append({"Parameter": name, "Value": value})
        st.dataframe(parameter_rows, use_container_width=True, hide_index=True)

if best_trial:
    st.subheader("📊 Best Trial PPA Metrics")
    metrics = best_trial.get("metrics", {})
    metric_rows = []
    for name, value in metrics.items():
        if name.startswith("_"):
            continue
        metric_rows.append({"Metric": name, "Value": value})
    st.dataframe(metric_rows, use_container_width=True, hide_index=True)

st.subheader("📈 Optimization Progress")

if valid_trials:
    chart_data = []
    best_so_far = float("inf")
    for i, trial in enumerate(valid_trials):
        score = float(trial["score"])
        if score < best_so_far:
            best_so_far = score
        chart_data.append({"Execution": i + 1, "Score": score, "Best So Far": best_so_far})
    st.line_chart(chart_data, x="Execution", y=["Score", "Best So Far"])
else:
    st.info("No successful trials available for plotting.")

st.subheader("📊 PPA Metrics Across Successful Trials")

if valid_trials:
    rows = []
    for i, trial in enumerate(valid_trials):
        metrics = trial.get("metrics", {})
        rows.append({
            "Execution": i + 1,
            "Score": trial.get("score"),
            "Power": metrics.get("power_total"),
            "Core Area": metrics.get("core_area"),
            "Setup Slack": metrics.get("setup_ws"),
            "Utilization": metrics.get("utilization"),
            "Fmax": metrics.get("fmax")
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

st.subheader("🔬 All Optimization Trials")

if trials:
    rows = []
    for i, trial in enumerate(trials):
        metrics = trial.get("metrics", {})
        rows.append({
            "Execution": i + 1,
            "Trial": trial.get("trial_number"),
            "Status": "Success" if trial.get("make_success") is True else "Failed",
            "Score": trial.get("score"),
            "Utilization": metrics.get("utilization"),
            "Power": metrics.get("power_total"),
            "Core Area": metrics.get("core_area"),
            "Setup Slack": metrics.get("setup_ws"),
            "Elapsed (sec)": trial.get("elapsed_sec"),
            "Error": trial.get("error")
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.warning("trial_history.jsonl does not contain any trials.")

if best_trial:
    with st.expander("View Best Trial Raw Data"):
        st.json(best_trial)

st.sidebar.markdown("---")
st.sidebar.write("### File Status")

if HISTORY_FILE.exists():
    st.sidebar.success("✓ trial_history.jsonl found")
else:
    st.sidebar.error("✗ trial_history.jsonl missing")

if BEST_FILE.exists():
    st.sidebar.success("✓ best_result.json found")
else:
    st.sidebar.warning("best_result.json missing")

st.sidebar.caption(f"Data directory: {BASE_DIR}")

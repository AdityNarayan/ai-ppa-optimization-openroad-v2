import subprocess
import os
import shutil
from pathlib import Path

ORFS_FLOW_DIR = Path.home() / "OpenROAD-flow-scripts" / "flow"
REAL_DESIGN_DIR = ORFS_FLOW_DIR / "designs" / "sky130hd" / "aes"
REAL_SRC_DIR = ORFS_FLOW_DIR / "designs" / "src" / "aes"

PLATFORM = "sky130hd"
VARIANT = "base"
CLEANUP_AFTER_TRIAL = True


def _nickname(trial_number):
    return f"aes_trial_{trial_number}"


def _ensure_symlink(link_path, target_path):
    if link_path.is_symlink() or link_path.exists():
        link_path.unlink()
    os.symlink(target_path, link_path)


def make_trial_config(params, trial_number):
    nickname = _nickname(trial_number)
    trial_design_dir = ORFS_FLOW_DIR / "designs" / "sky130hd" / nickname
    trial_src_dir = ORFS_FLOW_DIR / "designs" / "src" / nickname

    trial_design_dir.mkdir(parents=True, exist_ok=True)

    for item in REAL_DESIGN_DIR.iterdir():
        if item.name == "config.mk":
            continue
        _ensure_symlink(trial_design_dir / item.name, item)

    if trial_src_dir.is_symlink():
        trial_src_dir.unlink()
    if not trial_src_dir.exists():
        os.symlink(REAL_SRC_DIR, trial_src_dir)

    base_text = (REAL_DESIGN_DIR / "config.mk").read_text()
    base_text = base_text.replace(
        "export DESIGN_NICKNAME = aes",
        f"export DESIGN_NICKNAME = {nickname}",
    )

    override_lines = [f"\n# --- trial {trial_number} overrides ---"]
    for key, value in params.items():
        override_lines.append(f"export {key} = {value}")

    trial_config_path = trial_design_dir / "config.mk"
    trial_config_path.write_text(base_text + "\n".join(override_lines) + "\n")

    return trial_config_path


def run_trial(params, trial_number, timeout_seconds=3600):
    config_path = make_trial_config(params, trial_number)
    cmd = ["make", f"DESIGN_CONFIG={config_path}"]
    try:
        result = subprocess.run(
            cmd, cwd=ORFS_FLOW_DIR, capture_output=True, text=True, timeout=timeout_seconds,
        )
        success = result.returncode == 0
        stdout_tail = "\n".join(result.stdout.splitlines()[-40:])
        stderr_tail = "\n".join(result.stderr.splitlines()[-40:])
        return {"success": success, "returncode": result.returncode,
                "stdout_tail": stdout_tail, "stderr_tail": stderr_tail, "config_path": config_path}
    except subprocess.TimeoutExpired:
        return {"success": False, "returncode": -1,
                "stdout_tail": f"TIMEOUT after {timeout_seconds}s", "stderr_tail": "", "config_path": config_path}


def get_metrics_path(trial_number):
    nickname = _nickname(trial_number)
    return ORFS_FLOW_DIR / "logs" / PLATFORM / nickname / VARIANT / "6_report.json"


def cleanup_trial(trial_number):
    if not CLEANUP_AFTER_TRIAL:
        return
    nickname = _nickname(trial_number)
    results_dir = ORFS_FLOW_DIR / "results" / PLATFORM / nickname
    if results_dir.exists():
        shutil.rmtree(results_dir, ignore_errors=True)

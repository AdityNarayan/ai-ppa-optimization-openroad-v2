PARAMS = {
    "CORE_UTILIZATION": ("int", 20, 50, 1),
    "CORE_ASPECT_RATIO": ("float", 0.5, 2.0, None),
    "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT": ("int", 0, 3, 1),
    "CELL_PAD_IN_SITES_DETAIL_PLACEMENT": ("int", 0, 3, 1),
    "PLACE_DENSITY_LB_ADDON": ("float", 0.0, 0.2, None),
    "CTS_CLUSTER_SIZE": ("int", 10, 200, 1),
    "CTS_CLUSTER_DIAMETER": ("int", 20, 400, 1),
}

def suggest_params(trial):
    params = {}
    for name, (ptype, low, high, step) in PARAMS.items():
        if ptype == "int":
            params[name] = trial.suggest_int(name, low, high, step=step or 1)
        elif ptype == "float":
            params[name] = trial.suggest_float(name, low, high)
        else:
            raise ValueError(f"Unknown param type for {name}: {ptype}")
    return params

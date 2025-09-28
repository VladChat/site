import os, json

ROOT = os.path.dirname(os.path.dirname(__file__))

def load_configs():
    with open(os.path.join(ROOT, "config/config.json"), "r", encoding="utf-8") as f:
        base_config = json.load(f)

    writer_config_path = os.path.join(ROOT, "config/writer.json")
    if os.path.exists(writer_config_path):
        with open(writer_config_path, "r", encoding="utf-8") as f:
            writer_config = json.load(f)
    else:
        writer_config = {}

    state_path = os.path.join(ROOT, "data/state.json")
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {"posts": []}

    return {
        "root": ROOT,
        "base_config": base_config,
        "writer_config": writer_config,
        "state_path": state_path,
        "state": state,
    }

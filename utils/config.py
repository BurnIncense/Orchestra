import os
import re
import yaml


def load_config(path: str = "config/settings.yaml") -> dict:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, path) if not os.path.isabs(path) else path

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r'\$\{([^}]+)\}', lambda m: os.environ.get(
        m.group(1).split(":-")[0],
        m.group(1).split(":-")[1] if ":-" in m.group(1) else ""
    ), content)

    return yaml.safe_load(content) or {}

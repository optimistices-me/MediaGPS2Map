"""Application configuration.

Loads settings from config.json with optional env-var overrides.
AMAP_API_KEY can be set via the AMAP_API_KEY environment variable.
"""

import json
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"

DEFAULTS: dict[str, Any] = {"batch_size": 200, "directories": []}


def load_config(config_file: str = CONFIG_FILE) -> dict[str, Any]:
    """Load configuration from a JSON file and apply env-var overrides."""
    config = DEFAULTS.copy()

    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load %s: %s. Using defaults.", config_file, e)
    else:
        logger.info("%s not found, using defaults.", config_file)

    # Environment variable override (keeps API key out of VCS)
    env_key = os.environ.get("AMAP_API_KEY")
    if env_key:
        config["AMAP_API_KEY"] = env_key

    # Normalise directory separators
    config["directories"] = [d.replace("\\", "/") for d in config["directories"]]

    return config

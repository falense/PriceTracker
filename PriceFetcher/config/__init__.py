"""Configuration module."""

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses default config/settings.yaml

    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_dir = Path(__file__).parent
        config_path = config_dir / "settings.yaml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Override with environment variables if present
    if "DATABASE_PATH" in os.environ:
        config["storage"]["database"] = os.environ["DATABASE_PATH"]

    if "LOG_LEVEL" in os.environ:
        config["logging"]["level"] = os.environ["LOG_LEVEL"]

    if "MIN_CONFIDENCE" in os.environ:
        config["validation"]["min_confidence"] = float(os.environ["MIN_CONFIDENCE"])

    return config

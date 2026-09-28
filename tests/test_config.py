"""
Unit tests for CryNet ConfigManager
"""

import json
import pytest
from pathlib import Path
from core.config_manager import ConfigManager, DEFAULT_SETTINGS


def test_default_config_creation(tmp_path):
    mgr = ConfigManager(base_dir=tmp_path)
    assert mgr.get("camera_index") == 0
    assert mgr.get("smoothing") == 0.65
    assert mgr.get("sensitivity") == 1.2
    assert (tmp_path / "config" / "settings.json").exists()


def test_corrupted_config_fallback(tmp_path):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    settings_file = cfg_dir / "settings.json"

    # Write corrupt JSON
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write("{ INVALID JSON DATA %%%")

    mgr = ConfigManager(base_dir=tmp_path)
    # Should safely fallback to default without raising exception
    assert mgr.get("camera_index") == DEFAULT_SETTINGS["camera_index"]
    assert mgr.get("sensitivity") == DEFAULT_SETTINGS["sensitivity"]


def test_save_and_reload(tmp_path):
    mgr = ConfigManager(base_dir=tmp_path)
    mgr.set("sensitivity", 2.5, save=True)

    # Reload from disk
    mgr2 = ConfigManager(base_dir=tmp_path)
    assert mgr2.get("sensitivity") == 2.5

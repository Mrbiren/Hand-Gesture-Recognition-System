"""
Unit tests for CryNet CalibrationManager
"""

import pytest
from core.calibration import CalibrationManager
from core.config_manager import ConfigManager


def test_calibration_wizard_flow(tmp_path):
    cfg = ConfigManager(base_dir=tmp_path)
    calib = CalibrationManager(config_manager=cfg)

    # Start wizard
    step, instr = calib.start_wizard("Display 1")
    assert step == "TOP_LEFT"
    assert calib.is_calibrating is True

    # Step 1: Top-Left
    done, next_step, _ = calib.record_step(0.2, 0.2)
    assert not done
    assert next_step == "TOP_RIGHT"

    # Step 2: Top-Right
    done, next_step, _ = calib.record_step(0.8, 0.2)
    assert not done
    assert next_step == "BOTTOM_LEFT"

    # Step 3: Bottom-Left
    done, next_step, _ = calib.record_step(0.2, 0.8)
    assert not done
    assert next_step == "BOTTOM_RIGHT"

    # Step 4: Bottom-Right
    done, next_step, _ = calib.record_step(0.8, 0.8)
    assert done is True
    assert calib.is_calibrating is False

    # Check bounds
    assert calib.min_x == pytest.approx(0.2, abs=0.01)
    assert calib.max_x == pytest.approx(0.8, abs=0.01)
    assert calib.min_y == pytest.approx(0.2, abs=0.01)
    assert calib.max_y == pytest.approx(0.8, abs=0.01)

    # Check normalization mapping
    norm_x, norm_y = calib.map_to_normalized_interaction_space(0.5, 0.5)
    assert norm_x == pytest.approx(0.5, abs=0.05)
    assert norm_y == pytest.approx(0.5, abs=0.05)

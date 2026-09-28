"""
Unit tests for CryNet Safety Controller
"""

import pytest
from core.safety_controller import SafetyController


def test_safety_initial_state():
    safety = SafetyController()
    assert safety.is_enabled is False
    assert safety.is_paused is False
    assert safety.is_action_allowed() is False
    safety.stop()


def test_safety_toggle():
    safety = SafetyController()
    enabled = safety.toggle_enabled()
    assert enabled is True
    assert safety.is_action_allowed() is True

    enabled2 = safety.toggle_enabled()
    assert enabled2 is False
    assert safety.is_action_allowed() is False
    safety.stop()


def test_safety_emergency_stop():
    safety = SafetyController()
    safety.toggle_enabled()
    assert safety.is_action_allowed() is True

    # Trigger ESC emergency stop
    safety.trigger_emergency_stop()
    assert safety.is_enabled is False
    assert safety.is_action_allowed() is False
    assert "EMERGENCY" in safety.pause_reason
    safety.stop()


def test_safety_pause_and_resume():
    safety = SafetyController()
    safety.toggle_enabled()
    assert safety.is_action_allowed() is True

    safety.pause_control("GESTURE CONTROL PAUSED")
    assert safety.is_paused is True
    assert safety.is_action_allowed() is False

    safety.resume_control()
    assert safety.is_paused is False
    assert safety.is_action_allowed() is True
    safety.stop()


def test_safety_destructive_action_blocking():
    safety = SafetyController()
    assert safety.validate_action_safe("move_cursor") is True
    assert safety.validate_action_safe("click") is True
    assert safety.validate_action_safe("shutdown -s -t 0") is False
    assert safety.validate_action_safe("format C:") is False
    assert safety.validate_action_safe("del /f /q") is False
    safety.stop()

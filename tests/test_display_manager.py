"""
Unit tests for CryNet DisplayManager
"""

import pytest
from core.display_manager import DisplayInfo, DisplayManager, VirtualDesktopInfo


def test_display_manager_init():
    mgr = DisplayManager()
    assert len(mgr.displays) >= 1
    assert mgr.mode in ("HOME", "OFFICE")
    assert mgr.get_target_display() is not None


def test_multi_monitor_mapping():
    mgr = DisplayManager()

    # Mock multi-monitor layout: Monitor 1 (0, 0, 1920, 1080), Monitor 2 (1920, 0, 4480, 1440)
    disp1 = DisplayInfo(
        index=0, name="Display 1", left=0, top=0, right=1920, bottom=1080,
        width=1920, height=1080, is_primary=True, device_name="\\\\.\\DISPLAY1"
    )
    disp2 = DisplayInfo(
        index=1, name="Display 2", left=1920, top=0, right=4480, bottom=1440,
        width=2560, height=1440, is_primary=False, device_name="\\\\.\\DISPLAY2"
    )

    mgr.displays = [disp1, disp2]
    mgr.set_target_display(1)

    # Test center mapping (0.5, 0.5) on Display 2
    px, py = mgr.map_normalized_to_target_screen(0.5, 0.5)
    assert px == 1920 + 1280  # 3200
    assert py == 0 + 720      # 720

    # Test top-left corner (0.0, 0.0) on Display 2
    px0, py0 = mgr.map_normalized_to_target_screen(0.0, 0.0)
    assert px0 == 1920
    assert py0 == 0


def test_negative_coordinates_mapping():
    mgr = DisplayManager()

    # Secondary monitor placed to the LEFT of primary monitor: Left=-1920, Top=0
    disp_neg = DisplayInfo(
        index=0, name="Display Left", left=-1920, top=0, right=0, bottom=1080,
        width=1920, height=1080, is_primary=False, device_name="\\\\.\\DISPLAY1"
    )
    mgr.displays = [disp_neg]
    mgr.set_target_display(0)

    # Test center mapping
    px, py = mgr.map_normalized_to_target_screen(0.5, 0.5)
    assert px == -1920 + 960  # -960
    assert py == 540

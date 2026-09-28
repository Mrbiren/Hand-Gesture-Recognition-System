"""
CryNet Display Manager
Detects Windows multi-monitor configuration, virtual desktop bounds,
resolutions, DPI-awareness, negative coordinates, and maps gesture coordinates
to the user-selected target display.
"""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger("CryNet.DisplayManager")

# Enable Per-Monitor DPI Awareness so Windows API returns true physical pixels
try:
    shcore = ctypes.windll.shcore
    # PROCESS_PER_MONITOR_DPI_AWARE = 2
    shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception as e:
        logger.warning(f"Could not set DPI awareness: {e}")


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


@dataclass
class DisplayInfo:
    index: int
    name: str
    left: int
    top: int
    right: int
    bottom: int
    width: int
    height: int
    is_primary: bool
    device_name: str

    @property
    def label(self) -> str:
        role = "Primary" if self.is_primary else "External"
        return f"Display {self.index + 1} — {role} ({self.width}x{self.height} at [{self.left}, {self.top}])"


@dataclass
class VirtualDesktopInfo:
    x_min: int = 0
    y_min: int = 0
    width: int = 1920
    height: int = 1080


class DisplayManager:
    """Detects and manages Windows multi-monitor setups and maps coordinates."""

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.displays: List[DisplayInfo] = []
        self.target_display_index: int = 0
        self.virtual_desktop: VirtualDesktopInfo = VirtualDesktopInfo()
        self.mode: str = "HOME"  # HOME (1 display) or OFFICE (2+ displays)
        self._last_display_check: float = 0.0
        self._last_display_sig: Optional[tuple] = None
        self.refresh_displays()

    def refresh_displays(self) -> List[DisplayInfo]:
        """Queries Windows for all active physical/virtual monitors."""
        monitors: List[DisplayInfo] = []
        user32 = self.user32

        # Virtual Desktop metrics
        SM_XVIRTUALSCREEN = 76
        SM_YVIRTUALSCREEN = 77
        SM_CXVIRTUALSCREEN = 78
        SM_CYVIRTUALSCREEN = 79

        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

        self.virtual_desktop = VirtualDesktopInfo(x_min=vx, y_min=vy, width=vw, height=vh)

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                left = int(info.rcMonitor.left)
                top = int(info.rcMonitor.top)
                right = int(info.rcMonitor.right)
                bottom = int(info.rcMonitor.bottom)
                width = right - left
                height = bottom - top
                is_primary = bool(info.dwFlags & 1)
                device_name = str(info.szDevice)
                idx = len(monitors)
                monitors.append(
                    DisplayInfo(
                        index=idx,
                        name=f"Display {idx + 1}",
                        left=left,
                        top=top,
                        right=right,
                        bottom=bottom,
                        width=width,
                        height=height,
                        is_primary=is_primary,
                        device_name=device_name,
                    )
                )
            return True

        user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)

        # Fallback if EnumDisplayMonitors returned nothing (e.g. headless/mock)
        if not monitors:
            monitors.append(
                DisplayInfo(
                    index=0,
                    name="Display 1",
                    left=0,
                    top=0,
                    right=1920,
                    bottom=1080,
                    width=1920,
                    height=1080,
                    is_primary=True,
                    device_name="\\\\.\\DISPLAY1",
                )
            )

        self.displays = monitors

        # Determine mode
        if len(self.displays) == 1:
            self.mode = "HOME"
            # In Home mode default to Display 1
            if self.target_display_index >= len(self.displays):
                self.target_display_index = 0
        else:
            self.mode = "OFFICE"
            # In Office mode, default to Display 2 (index 1) if available and not yet explicitly set
            if self.target_display_index >= len(self.displays):
                self.target_display_index = 1 if len(self.displays) > 1 else 0

        curr_sig = (len(self.displays), self.mode, self.target_display_index)
        if self._last_display_sig != curr_sig:
            self._last_display_sig = curr_sig
            logger.info(
                f"Detected {len(self.displays)} display(s). Mode: {self.mode}. "
                f"Target: Display {self.target_display_index + 1}"
            )
        return self.displays

    def get_target_display(self) -> Optional[DisplayInfo]:
        """Returns the currently selected target display or None if disconnected."""
        if 0 <= self.target_display_index < len(self.displays):
            return self.displays[self.target_display_index]
        return None

    def set_target_display(self, index: int) -> bool:
        """Sets the active target display index."""
        if 0 <= index < len(self.displays):
            self.target_display_index = index
            logger.info(f"Target display changed to index {index} ({self.displays[index].label})")
            return True
        logger.warning(f"Invalid target display index {index}. Total displays: {len(self.displays)}")
        return False

    def check_target_valid(self) -> bool:
        """Verifies if the current target display is still connected (throttled to avoid I/O overhead)."""
        now = time.time()
        if now - self._last_display_check > 2.0:
            self._last_display_check = now
            self.refresh_displays()
        return self.target_display_index < len(self.displays)

    def map_normalized_to_target_screen(
        self, norm_x: float, norm_y: float
    ) -> Optional[Tuple[int, int]]:
        """
        Maps normalized coordinates [0.0, 1.0] from gesture interaction space
        to physical Windows desktop pixel coordinates (X, Y) on the target monitor.
        Handles negative coords, custom resolutions, and off-center placement.
        """
        target = self.get_target_display()
        if not target:
            return None

        # Clamp normalized inputs
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))

        # Calculate exact pixel position on target monitor
        screen_x = int(target.left + norm_x * target.width)
        screen_y = int(target.top + norm_y * target.height)

        # Clamp within target display rectangle
        screen_x = max(target.left, min(target.right - 1, screen_x))
        screen_y = max(target.top, min(target.bottom - 1, screen_y))

        return screen_x, screen_y

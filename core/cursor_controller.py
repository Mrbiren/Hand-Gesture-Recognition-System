"""
CryNet Cursor Controller
Provides native Windows mouse and keyboard simulation using Win32 SendInput.
Supports multi-monitor absolute virtual desktop positioning, jitter smoothing,
dead zone thresholding, acceleration curves, drag, scroll, and navigation shortcuts.
"""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import logging
import math
import time
from typing import Optional, Tuple

logger = logging.getLogger("CryNet.CursorController")

# Win32 Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
VK_MENU = 0x12       # ALT key
VK_LEFT = 0x25       # Left arrow
VK_RIGHT = 0x27      # Right arrow

# Structures
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUTUNION),
    ]


class CursorController:
    """Controls mouse movement, clicks, drags, scroll, and shortcuts via SendInput."""

    def __init__(
        self,
        sensitivity: float = 1.2,
        smoothing: float = 0.65,
        dead_zone: float = 0.002,
        acceleration: float = 1.3,
        scroll_sensitivity: float = 1.0,
    ):
        self.user32 = ctypes.windll.user32
        self.is_dragging: bool = False
        self.last_screen_x: Optional[float] = None
        self.last_screen_y: Optional[float] = None
        self.filtered_x: Optional[float] = None
        self.filtered_y: Optional[float] = None

        # Configurable parameters
        self.sensitivity: float = sensitivity
        self.smoothing: float = smoothing
        self.dead_zone: float = dead_zone  # Low-latency dead-zone threshold
        self.acceleration: float = acceleration
        self.scroll_sensitivity: float = scroll_sensitivity

    def update_config(
        self,
        sensitivity: float = 1.2,
        smoothing: float = 0.65,
        dead_zone: float = 0.002,
        acceleration: float = 1.3,
        scroll_sensitivity: float = 1.0,
    ) -> None:
        self.sensitivity = max(0.1, min(5.0, sensitivity))
        self.smoothing = max(0.0, min(0.95, smoothing))
        self.dead_zone = max(0.0, min(0.05, dead_zone))
        self.acceleration = max(1.0, min(3.0, acceleration))
        self.scroll_sensitivity = max(0.1, min(5.0, scroll_sensitivity))

    def reset_state(self) -> None:
        """Resets filters and releases any active drag."""
        if self.is_dragging:
            self.mouse_up()
        self.last_screen_x = None
        self.last_screen_y = None
        self.filtered_x = None
        self.filtered_y = None

    def _send_mouse_event(self, flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> None:
        """Sends native Windows Mouse Input event."""
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = dx
        inp.union.mi.dy = dy
        inp.union.mi.mouseData = data
        inp.union.mi.dwFlags = flags
        inp.union.mi.time = 0
        inp.union.mi.dwExtraInfo = None

        res = self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if res == 0:
            logger.debug(f"SendInput mouse event failed: flags={flags}")

    def move_to(
        self,
        target_x: int,
        target_y: int,
        virtual_left: int,
        virtual_top: int,
        virtual_width: int,
        virtual_height: int,
    ) -> None:
        """
        Moves mouse cursor with low-latency adaptive velocity smoothing.
        - Fast movement: near-instant response with high alpha
        - Slow movement: high smoothing and jitter suppression
        """
        if self.filtered_x is None or self.filtered_y is None:
            # Immediate first-frame activation without lag
            self.filtered_x = float(target_x)
            self.filtered_y = float(target_y)
        else:
            dx = float(target_x) - self.filtered_x
            dy = float(target_y) - self.filtered_y
            dist = math.hypot(dx, dy)

            # Refined dead zone: filter sub-pixel hand tremor
            pixel_dead_zone = max(1.5, self.dead_zone * virtual_width)
            if dist < pixel_dead_zone:
                return

            # Adaptive velocity-based alpha
            # Slow precision motion -> lower alpha (smooth, jitter-free)
            # Fast flick motion -> high alpha (zero-latency, tracks fingertip immediately)
            d_min = 2.0
            d_max = 40.0
            norm_speed = max(0.0, min(1.0, (dist - d_min) / (d_max - d_min)))

            slow_alpha = max(0.12, min(0.40, (1.0 - self.smoothing) * 0.85))
            fast_alpha = max(0.82, min(0.96, 1.0 - (self.smoothing * 0.12)))
            alpha = slow_alpha + (fast_alpha - slow_alpha) * (norm_speed ** 1.4)

            # Dynamic acceleration
            acc_factor = 1.0
            if dist > 18.0 and self.acceleration > 1.0:
                acc_factor = 1.0 + (self.acceleration - 1.0) * min(2.2, (dist - 18.0) / 100.0)

            step_x = dx * alpha * acc_factor
            step_y = dy * alpha * acc_factor

            self.filtered_x += step_x
            self.filtered_y += step_y

        final_x = int(round(self.filtered_x))
        final_y = int(round(self.filtered_y))

        # Map to virtual desktop 0-65535 absolute coordinates
        # Note: (screen_x - vx) * 65535 / (vw - 1)
        if virtual_width > 1 and virtual_height > 1:
            norm_abs_x = int(((final_x - virtual_left) * 65535) / (virtual_width - 1))
            norm_abs_y = int(((final_y - virtual_top) * 65535) / (virtual_height - 1))
        else:
            norm_abs_x = 0
            norm_abs_y = 0

        norm_abs_x = max(0, min(65535, norm_abs_x))
        norm_abs_y = max(0, min(65535, norm_abs_y))

        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        self._send_mouse_event(flags, dx=norm_abs_x, dy=norm_abs_y)

    def mouse_down(self) -> None:
        """Sends native Left Mouse Down."""
        if not self.is_dragging:
            self._send_mouse_event(MOUSEEVENTF_LEFTDOWN)
            self.is_dragging = True
            logger.debug("Mouse Down (Drag Started)")

    def mouse_up(self) -> None:
        """Sends native Left Mouse Up."""
        if self.is_dragging:
            self._send_mouse_event(MOUSEEVENTF_LEFTUP)
            self.is_dragging = False
            logger.debug("Mouse Up (Drag Released)")

    def click(self) -> None:
        """Sends a single discrete Left Click (Down + Up)."""
        self._send_mouse_event(MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.02)
        self._send_mouse_event(MOUSEEVENTF_LEFTUP)
        logger.debug("Mouse Click")

    def scroll(self, delta_y: float) -> None:
        """
        Scrolls vertically.
        Positive delta_y scrolls up; negative scrolls down.
        """
        # Standard Windows wheel delta is 120 units per detent
        wheel_amount = int(delta_y * 120 * self.scroll_sensitivity)
        if wheel_amount != 0:
            self._send_mouse_event(MOUSEEVENTF_WHEEL, data=wheel_amount)

    def trigger_navigation(self, direction: str) -> None:
        """
        Triggers keyboard navigation shortcut.
        'left' -> ALT + LEFT (Back)
        'right' -> ALT + RIGHT (Forward)
        """
        vk_key = VK_LEFT if direction.lower() == "left" else VK_RIGHT

        # Alt Down, Key Down, Key Up, Alt Up
        inputs = (INPUT * 4)()

        # 1. Alt Down
        inputs[0].type = INPUT_KEYBOARD
        inputs[0].union.ki.wVk = VK_MENU
        inputs[0].union.ki.dwFlags = 0

        # 2. Key Down
        inputs[1].type = INPUT_KEYBOARD
        inputs[1].union.ki.wVk = vk_key
        inputs[1].union.ki.dwFlags = 0

        # 3. Key Up
        inputs[2].type = INPUT_KEYBOARD
        inputs[2].union.ki.wVk = vk_key
        inputs[2].union.ki.dwFlags = KEYEVENTF_KEYUP

        # 4. Alt Up
        inputs[3].type = INPUT_KEYBOARD
        inputs[3].union.ki.wVk = VK_MENU
        inputs[3].union.ki.dwFlags = KEYEVENTF_KEYUP

        self.user32.SendInput(4, ctypes.byref(inputs), ctypes.sizeof(INPUT))
        logger.info(f"Triggered navigation shortcut: ALT + {direction.upper()}")

    def lock_workstation(self) -> bool:
        """
        Locks the Windows workstation using native Win32 LockWorkStation (Win+L equivalent).
        """
        logger.info("Executing native Windows LockWorkStation (Win+L equivalent)")
        try:
            res = self.user32.LockWorkStation()
            return bool(res)
        except Exception as e:
            logger.error(f"Failed to lock workstation: {e}")
            return False

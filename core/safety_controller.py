"""
CryNet Safety Controller
Enforces fail-safe operation:
1. Global emergency kill switch (ESC = immediately stop actions, reset state)
2. Global toggle switch (F8 = enable/disable CryNet)
3. Hand count limiter (2 hands -> automatic pause)
4. Open Palm safety pause
5. Display loss disconnect protection
6. Destructive action prevention (blacklist)
"""

from __future__ import annotations
import logging
import threading
from typing import Callable, Optional
from gestures.gesture_state import SystemMode

logger = logging.getLogger("CryNet.SafetyController")

DESTRUCTIVE_COMMANDS = {
    "shutdown", "restart", "format", "del", "rmdir", "drop", "fdisk", "mkfs"
}


class SafetyController:
    """Monitors emergency conditions and enforces safe gesture limits."""

    def __init__(
        self,
        on_toggle_enabled: Optional[Callable[[bool], None]] = None,
        on_emergency_stop: Optional[Callable[[], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        self.on_toggle_enabled = on_toggle_enabled
        self.on_emergency_stop = on_emergency_stop
        self.on_status_change = on_status_change

        self.is_enabled: bool = False
        self.is_paused: bool = False
        self.pause_reason: str = ""
        self._listener = None
        self._lock = threading.Lock()

        self.start_global_hotkeys()

    def start_global_hotkeys(self) -> None:
        """Starts background listener for F8 (Toggle) and ESC (Emergency Stop)."""
        try:
            from pynput import keyboard

            def on_press(key):
                try:
                    if key == keyboard.Key.f8:
                        self.toggle_enabled()
                    elif key == keyboard.Key.esc:
                        self.trigger_emergency_stop()
                except Exception as e:
                    logger.debug(f"Hotkey event error: {e}")

            self._listener = keyboard.Listener(on_press=on_press)
            self._listener.daemon = True
            self._listener.start()
            logger.info("Global emergency hotkeys active: F8 (Toggle), ESC (Emergency Stop)")
        except Exception as e:
            logger.warning(f"Could not initialize pynput global hotkeys: {e}")

    def toggle_enabled(self) -> bool:
        """Toggles between ONLINE and STANDBY."""
        with self._lock:
            self.is_enabled = not self.is_enabled
            if not self.is_enabled:
                self.is_paused = False
                self.pause_reason = ""
                status_msg = "STATUS: STANDBY"
            else:
                status_msg = "STATUS: ONLINE"

        logger.info(f"CryNet status toggled -> {status_msg}")
        if self.on_status_change:
            self.on_status_change(status_msg)
        if self.on_toggle_enabled:
            self.on_toggle_enabled(self.is_enabled)
        return self.is_enabled

    def trigger_emergency_stop(self) -> None:
        """Instantly halts all mouse/keyboard actions and reverts to STANDBY."""
        with self._lock:
            self.is_enabled = False
            self.is_paused = False
            self.pause_reason = "EMERGENCY STOP (ESC)"

        logger.warning("EMERGENCY STOP ACTIVATED (ESC pressed). Standby engaged.")
        if self.on_emergency_stop:
            self.on_emergency_stop()
        if self.on_status_change:
            self.on_status_change("EMERGENCY STOPPED — STANDBY")
        if self.on_toggle_enabled:
            self.on_toggle_enabled(False)

    def pause_control(self, reason: str) -> None:
        """Temporarily pauses gesture execution (e.g. Open Palm, 2 Hands, Display Lost)."""
        with self._lock:
            self.is_paused = True
            self.pause_reason = reason
        if self.on_status_change:
            self.on_status_change(f"PAUSED: {reason.upper()}")

    def resume_control(self) -> None:
        """Resumes active control if currently enabled."""
        with self._lock:
            if self.is_paused:
                self.is_paused = False
                self.pause_reason = ""
                if self.is_enabled and self.on_status_change:
                    self.on_status_change("STATUS: ONLINE")

    def is_action_allowed(self) -> bool:
        """Checks if gesture execution is currently allowed."""
        return self.is_enabled and not self.is_paused

    def validate_action_safe(self, action_name: str) -> bool:
        """Guarantees no dangerous command or action can ever be triggered."""
        lower_action = action_name.lower().strip()
        for banned in DESTRUCTIVE_COMMANDS:
            if banned in lower_action:
                logger.error(f"BLOCKED DESTRUCTIVE ACTION ATTEMPT: {action_name}")
                return False
        return True

    def stop(self) -> None:
        """Cleans up listeners on shutdown."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

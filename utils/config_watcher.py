import os
import time
import threading
from typing import Callable, Optional

from utils.config import load_config


class ConfigWatcher:
    def __init__(self, config_path: str = "config/settings.yaml",
                 interval: float = 5.0,
                 callback: Optional[Callable] = None):
        self.config_path = config_path
        self.interval = interval
        self.callback = callback
        self._last_mtime: float = 0.0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _get_mtime(self) -> float:
        try:
            return os.path.getmtime(self.config_path)
        except OSError:
            return 0.0

    def _check_and_reload(self):
        current_mtime = self._get_mtime()
        if current_mtime != self._last_mtime and self._last_mtime != 0:
            try:
                config = load_config(self.config_path)
                if self.callback:
                    self.callback(config)
            except Exception:
                pass
        self._last_mtime = current_mtime

    def _watch_loop(self):
        self._last_mtime = self._get_mtime()
        while not self._stop_event.is_set():
            self._check_and_reload()
            self._stop_event.wait(self.interval)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

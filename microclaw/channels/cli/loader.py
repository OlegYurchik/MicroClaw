import itertools
import sys
import threading
import time


class LoadingIndicator:
    def __init__(self):
        self._loading_thread = None
        self._stop_loading = threading.Event()
        self._spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        self._stop_loading.clear()
        self._loading_thread = threading.Thread(target=self._loading_animation, daemon=True)
        self._loading_thread.start()

    def stop(self):
        self._stop_loading.set()
        if self._loading_thread and self._loading_thread.is_alive():
            self._loading_thread.join(timeout=1)

    def toggle(self):
        if self._stop_loading.is_set():
            self.stop()
        else:
            self.start()

    def _loading_animation(self):
        while not self._stop_loading.is_set():
            sys.stdout.write(f" {next(self._spinner)}")
            sys.stdout.flush()
            time.sleep(0.1)
            sys.stdout.write("\b\b")
            sys.stdout.flush()

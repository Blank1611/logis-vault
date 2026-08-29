"""
Thread-safe Cancellation Token for Job Lifecycle Management.

Provides cooperative cancellation signaling across asynchronous asyncio coroutines
and synchronous worker threads (ThreadPoolExecutor, yt-dlp, FFmpeg).
"""

import threading
from typing import Callable, List, Optional


class CancellationToken:
    """
    A thread-safe cancellation token that allows signaling and checking
    cancellation requests across threads and processes.
    """

    def __init__(self):
        self._is_cancelled = False
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[], None]] = []

    def cancel(self):
        """Signal cancellation to all listeners and worker threads."""
        with self._lock:
            if self._is_cancelled:
                return
            self._is_cancelled = True
            callbacks = list(self._callbacks)

        for callback in callbacks:
            try:
                callback()
            except Exception:
                pass

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        with self._lock:
            return self._is_cancelled

    def register(self, callback: Callable[[], None]):
        """
        Register a callback to be invoked when cancellation is signaled.
        If already cancelled, the callback is invoked immediately.
        """
        with self._lock:
            if self._is_cancelled:
                already_cancelled = True
            else:
                self._callbacks.append(callback)
                already_cancelled = False

        if already_cancelled:
            try:
                callback()
            except Exception:
                pass

"""
Multi-Handler Logging & Observability Engine for yt_serve.
Supports Console, Rotating File Handlers, In-Memory Ring Buffer, SSE Streaming, and JSON Formats.
"""

import os
import sys
import json
import logging
import threading
import asyncio
from logging.handlers import RotatingFileHandler
from collections import deque
from datetime import datetime
from typing import List, Dict, Optional, Set, Any
from pathlib import Path

# In-Memory Ring Buffer Storage
DEFAULT_RING_BUFFER_SIZE = 1000
_ring_buffer: deque = deque(maxlen=DEFAULT_RING_BUFFER_SIZE)
_buffer_lock = threading.Lock()

def resize_ring_buffer(capacity: int):
    """Dynamically resize the circular buffer while preserving existing records."""
    global _ring_buffer
    with _buffer_lock:
        items = list(_ring_buffer)
        _ring_buffer = deque(items, maxlen=capacity)

# SSE Broadcaster Queue Registry
_sse_subscribers: Set[asyncio.Queue] = set()
_sse_lock = threading.Lock()
_main_loop: Optional[asyncio.AbstractEventLoop] = None


class JSONLogFormatter(logging.Formatter):
    """Structured JSON Formatter for Grafana Loki / Promtail / Vector log shippers"""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
            "threadName": record.threadName,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


class RingBufferHandler(logging.Handler):
    """
    Thread-safe in-memory ring buffer logging handler.
    Stores structured log records for instant (<1ms) retrieval by UI and API.
    Also dispatches log records to active SSE subscriber queues with sliding window overflow protection.
    """
    def __init__(self, capacity: int = DEFAULT_RING_BUFFER_SIZE):
        super().__init__()
        self.capacity = capacity

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            entry: Dict[str, Any] = {
                "id": f"{int(record.created * 1000)}-{record.msecs:.0f}",
                "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "formatted": msg,
                "source": getattr(record, "source", record.name.split(".")[-1] if "." in record.name else record.name),
                "job_id": getattr(record, "job_id", None),
            }
            if record.exc_info:
                entry["exception"] = self.formatException(record.exc_info)

            # Store in ring buffer
            with _buffer_lock:
                _ring_buffer.append(entry)

            # Dispatch to SSE subscriber queues with sliding window on QueueFull
            with _sse_lock:
                for queue in list(_sse_subscribers):
                    try:
                        queue.put_nowait(entry)
                    except asyncio.QueueFull:
                        # Drop oldest unconsumed event and retry inserting newest
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        try:
                            queue.put_nowait(entry)
                        except asyncio.QueueFull:
                            pass
                    except Exception:
                        pass
        except Exception:
            self.handleError(record)


def get_recent_logs(
    limit: int = 200,
    min_level: Optional[str] = None,
    source: Optional[str] = None,
    job_id: Optional[int] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve logs from the in-memory circular buffer with optional filtering.
    """
    level_order = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "WARN": 30,
        "ERROR": 40,
        "CRITICAL": 50
    }
    target_level_val = level_order.get((min_level or "").upper(), 0)

    with _buffer_lock:
        items = list(_ring_buffer)

    filtered = []
    for item in reversed(items):
        if min_level and level_order.get(item["level"], 0) < target_level_val:
            continue
        if source and item.get("source", "").lower() != source.lower():
            continue
        if job_id is not None and item.get("job_id") != job_id:
            continue
        if search and search.lower() not in item["message"].lower():
            continue
        filtered.append(item)
        if len(filtered) >= limit:
            break

    return filtered


def clear_ring_buffer():
    """Clear all in-memory buffered logs."""
    with _buffer_lock:
        _ring_buffer.clear()


def register_sse_queue(queue: asyncio.Queue):
    """Register an SSE subscriber queue for live log streaming."""
    with _sse_lock:
        _sse_subscribers.add(queue)


def unregister_sse_queue(queue: asyncio.Queue):
    """Unregister an SSE subscriber queue."""
    with _sse_lock:
        _sse_subscribers.discard(queue)


_initialized = False

def setup_logging(
    logs_dir: Optional[str] = None,
    level: int = logging.INFO,
    max_bytes: Optional[int] = None,
    backup_count: Optional[int] = None,
    ring_buffer_size: Optional[int] = None,
):
    """
    Initialize global multi-handler logging engine:
    1. Console (Standard formatted)
    2. In-Memory Ring Buffer (Configurable capacity)
    3. Rotating File Handler (logs/yt_manager.log, configurable maxBytes, backupCount)
    """
    global _initialized
    if _initialized:
        return

    # Fall back to settings for unprovided parameters
    try:
        from app.core.config import settings
        if max_bytes is None:
            max_bytes = getattr(settings, "LOG_MAX_BYTES", 10 * 1024 * 1024)
        if backup_count is None:
            backup_count = getattr(settings, "LOG_BACKUP_COUNT", 5)
        if ring_buffer_size is None:
            ring_buffer_size = getattr(settings, "LOG_RING_BUFFER_SIZE", 1000)
    except Exception:
        max_bytes = max_bytes or 10 * 1024 * 1024
        backup_count = backup_count or 5
        ring_buffer_size = ring_buffer_size or 1000

    # Ensure buffer size is clamped defensively
    ring_buffer_size = max(100, min(50000, ring_buffer_size))
    resize_ring_buffer(ring_buffer_size)

    # Determine logs directory
    if not logs_dir:
        backend_dir = Path(__file__).parent.parent.parent
        logs_dir = str(backend_dir / "logs")

    os.makedirs(logs_dir, exist_ok=True)
    log_file_path = os.path.join(logs_dir, "yt_manager.log")

    standard_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 1. Console Handler (ensure stdout has standard structured formatter for Loki / Alloy)
    console_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)]
    if not console_handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(standard_formatter)
        root_logger.addHandler(console_handler)
    else:
        for ch in console_handlers:
            ch.setFormatter(standard_formatter)
            ch.setLevel(level)

    # 2. Ring Buffer Handler
    ring_handler = RingBufferHandler(capacity=ring_buffer_size)
    ring_handler.setLevel(logging.DEBUG)
    ring_handler.setFormatter(standard_formatter)
    root_logger.addHandler(ring_handler)

    # 3. Rotating File Handler (configurable limit and backup rotations)
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(standard_formatter)
    root_logger.addHandler(file_handler)

    _initialized = True
    logging.getLogger("app.core.logging_engine").info(
        f"Logging engine initialized (maxBytes={max_bytes}, backupCount={backup_count}, ringCapacity={ring_buffer_size}). File sink: {log_file_path}"
    )


def get_logger(name: str) -> logging.Logger:
    """Get a named logger within the app hierarchy."""
    if not _initialized:
        setup_logging()
    return logging.getLogger(name)

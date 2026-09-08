import unittest
import logging
from app.core.logging_engine import (
    setup_logging,
    get_logger,
    get_recent_logs,
    clear_ring_buffer,
    JSONLogFormatter
)

class TestLoggingEngine(unittest.TestCase):

    def setUp(self):
        setup_logging()
        clear_ring_buffer()
        self.logger = get_logger("app.test_logger")

    def tearDown(self):
        clear_ring_buffer()

    def test_ring_buffer_capture(self):
        self.logger.info("Test info message 1")
        self.logger.warning("Test warning message 2")
        self.logger.error("Test error message 3")

        logs = get_recent_logs(limit=10)
        self.assertEqual(len(logs), 3)

        # Most recent first
        self.assertEqual(logs[0]["message"], "Test error message 3")
        self.assertEqual(logs[0]["level"], "ERROR")
        self.assertEqual(logs[1]["message"], "Test warning message 2")
        self.assertEqual(logs[1]["level"], "WARNING")
        self.assertEqual(logs[2]["message"], "Test info message 1")
        self.assertEqual(logs[2]["level"], "INFO")

    def test_level_filtering(self):
        self.logger.debug("Debug msg")
        self.logger.info("Info msg")
        self.logger.warning("Warn msg")
        self.logger.error("Error msg")

        error_logs = get_recent_logs(min_level="ERROR")
        self.assertEqual(len(error_logs), 1)
        self.assertEqual(error_logs[0]["message"], "Error msg")

        warn_logs = get_recent_logs(min_level="WARN")
        self.assertEqual(len(warn_logs), 2)

    def test_search_filtering(self):
        self.logger.info("Apple downloaded")
        self.logger.info("Banana extracted")
        self.logger.info("Orange downloaded")

        searched = get_recent_logs(search="downloaded")
        self.assertEqual(len(searched), 2)
        self.assertIn("Orange downloaded", [l["message"] for l in searched])
        self.assertIn("Apple downloaded", [l["message"] for l in searched])

    def test_clear_buffer(self):
        self.logger.info("Temporary log")
        self.assertEqual(len(get_recent_logs()), 1)

        clear_ring_buffer()
        self.assertEqual(len(get_recent_logs()), 0)

    def test_json_formatter(self):
        formatter = JSONLogFormatter()
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Structured JSON message",
            args=(),
            exc_info=None
        )
        formatted = formatter.format(record)
        self.assertIn('"message": "Structured JSON message"', formatted)
        self.assertIn('"level": "INFO"', formatted)
    def test_buffer_capacity_eviction(self):
        from app.core.logging_engine import resize_ring_buffer
        # Resize to small capacity of 3
        resize_ring_buffer(3)
        self.logger.info("Msg 1")
        self.logger.info("Msg 2")
        self.logger.info("Msg 3")
        self.logger.info("Msg 4")  # Should evict Msg 1

        logs = get_recent_logs(limit=10)
        self.assertEqual(len(logs), 3)
        messages = [l["message"] for l in logs]
        self.assertNotIn("Msg 1", messages)
        self.assertEqual(messages, ["Msg 4", "Msg 3", "Msg 2"])

        # Restore default capacity
        resize_ring_buffer(1000)

    def test_job_manager_cleanup_old_logs(self):
        import tempfile
        import os
        import time
        from app.services.job_manager import JobManager

        jm = JobManager()
        with tempfile.TemporaryDirectory() as temp_logs_dir:
            jm.logs_dir = temp_logs_dir
            now = time.time()

            # Create 5 mock job log files
            for i in range(1, 6):
                fpath = os.path.join(temp_logs_dir, f"job_{i}.log")
                with open(fpath, "w") as f:
                    f.write(f"Log content for job {i}\n")
                # Set older mtime for earlier jobs (job_1 oldest: 40 days ago, job_5 newest: 0 days ago)
                age_seconds = (5 - i) * 10 * 86400
                os.utime(fpath, (now - age_seconds, now - age_seconds))

            # Prune keeping max_files=3 and max_days=30
            # job_1 is 40 days old (>30 days) -> should be deleted
            # files exceeding max_files=3 -> job_2 should also be deleted
            jm._cleanup_old_logs(max_days=30, max_files=3)

            remaining = os.listdir(temp_logs_dir)
            self.assertEqual(len(remaining), 3)
            self.assertIn("job_5.log", remaining)
            self.assertIn("job_4.log", remaining)
            self.assertIn("job_3.log", remaining)
            self.assertNotIn("job_1.log", remaining)
            self.assertNotIn("job_2.log", remaining)

    def test_sse_queue_overflow_protection(self):
        import asyncio
        from app.core.logging_engine import register_sse_queue, unregister_sse_queue

        # Create bounded queue with capacity 2
        test_queue = asyncio.Queue(maxsize=2)
        register_sse_queue(test_queue)

        try:
            self.logger.info("Log Event 1")
            self.logger.info("Log Event 2")
            # 3rd log event should overflow queue, dropping Event 1 safely
            self.logger.info("Log Event 3")

            self.assertEqual(test_queue.qsize(), 2)
            item1 = test_queue.get_nowait()
            item2 = test_queue.get_nowait()
            self.assertEqual(item1["message"], "Log Event 2")
            self.assertEqual(item2["message"], "Log Event 3")
        finally:
            unregister_sse_queue(test_queue)

if __name__ == "__main__":
    unittest.main()

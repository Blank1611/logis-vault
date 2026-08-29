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
        self.assertIn('"logger": "app.test"', formatted)

if __name__ == "__main__":
    unittest.main()

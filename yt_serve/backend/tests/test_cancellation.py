import unittest
import threading
import time
from app.core.cancellation import CancellationToken
from app.services.ytdlp_service import DownloadService

class TestCancellation(unittest.TestCase):

    def test_cancellation_token_basic(self):
        token = CancellationToken()
        self.assertFalse(token.is_cancelled)
        token.cancel()
        self.assertTrue(token.is_cancelled)

    def test_cancellation_token_callbacks(self):
        token = CancellationToken()
        called = []

        def on_cancel():
            called.append(True)

        token.register(on_cancel)
        self.assertEqual(len(called), 0)

        token.cancel()
        self.assertEqual(len(called), 1)

        # Registering on already cancelled token should trigger immediately
        token.register(on_cancel)
        self.assertEqual(len(called), 2)

    def test_cancellation_token_thread_safe(self):
        token = CancellationToken()
        results = []

        def worker():
            while not token.is_cancelled:
                time.sleep(0.01)
            results.append("stopped")

        t = threading.Thread(target=worker)
        t.start()

        time.sleep(0.05)
        token.cancel()
        t.join(timeout=1.0)

        self.assertFalse(t.is_alive())
        self.assertEqual(results, ["stopped"])

    def test_download_service_cancel_current_job(self):
        service = DownloadService(base_path="/tmp", config={})
        self.assertTrue(hasattr(service, "cancel_current_job"))

        token = CancellationToken()
        service.cancel_token = token

        self.assertFalse(token.is_cancelled)
        service.cancel_current_job()
        self.assertTrue(token.is_cancelled)

if __name__ == "__main__":
    unittest.main()

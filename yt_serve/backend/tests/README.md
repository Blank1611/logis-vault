# `yt_serve` Backend Test Suite

Comprehensive unit and integration test suite for `yt_serve`.

> **Important**: Tests should always be run inside the Docker test container (`yt_serve:test`) to ensure consistent dependencies, binary tools (`ffmpeg`, `ffprobe`), and Python runtimes.

---

## 1. Test Suite Structure

```
yt_serve/backend/tests/
├── conftest.py                     # Pytest fixtures (for pytest environments)
├── test_db_helper.py               # Isolated in-memory SQLite sandbox & disposal helpers
├── test_adhoc_downloads.py         # On-demand / single-track video download workflows
├── test_batch_recovery_guards.py   # Atomic Git sync, commit scheduling, lock recovery
├── test_cancellation.py            # CancellationToken and worker thread termination
├── test_deduplication_service.py   # Zero-space hardlinking & deduplication analysis
├── test_dual_tier_progress.py      # Dual-tier progress hooks and in-flight job fields
├── test_logging_engine.py          # Structured logs, ring-buffer eviction, SSE queues
├── test_onboarding_service.py      # Video ID extraction & existing library indexing
├── test_repositories.py            # Central Data Access Layer (DAL) repositories
└── test_track_indexer.py           # Track movements, hardlinks, metadata indexing
```

---

## 2. Running Tests via Docker CLI

### Step 1: Refresh Test Container Target
The test target (`backend-test`) bypasses Node.js and frontend compilation, rebuilding in ~2–3 seconds with Docker cache:
```bash
# From workspace root:
./yt_serve/dist_utils/build_image.py -e test

# Or from yt_serve/ directory:
./dist_utils/build_image.py -e test
```
*(Note: Do not prepend `python3`; `build_image.py` has executable permissions and a `#!/usr/bin/env python3` shebang).*

### Step 2: Run Tests

#### Run All Test Suites
```bash
docker run --rm yt_serve:test
```

#### Run a Specific Test Module
```bash
docker run --rm yt_serve:test tests.test_logging_engine
```

#### Run a Specific Test Case or Method
```bash
docker run --rm yt_serve:test tests.test_logging_engine.TestLoggingEngine.test_buffer_capacity_eviction
```

#### Verify Clean Teardown (Zero ResourceWarnings)
```bash
docker run --rm --entrypoint python yt_serve:test -W error::ResourceWarning -m unittest discover tests
```

---

## 3. Running Tests in VS Code (UI Tasks)

Preconfigured tasks in [`.vscode/tasks.json`](../../../.vscode/tasks.json) allow running tests directly from the VS Code command palette (**Terminal $\rightarrow$ Run Task...**):

1. **`Docker: Run All Tests`**: Executes the entire test suite inside a transient container.
2. **`Docker: Run Specific Test`**: Prompts with an input box for the test namespace (e.g. `tests.test_logging_engine` or `tests.test_adhoc_downloads.TestAdhocDownloads.test_format_duration`).

---

## 4. Writing Isolated Database Tests

All tests requiring database access must use the in-memory SQLite sandbox helper in [`test_db_helper.py`](test_db_helper.py):

```python
import unittest
from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db

class ExampleTest(unittest.TestCase):

    def setUp(self):
        self.test_engine, self.TestingSession = create_isolated_test_db()
        self.db = self.TestingSession()

    def tearDown(self):
        dispose_isolated_test_db(self.test_engine, self.db)
```
Using `dispose_isolated_test_db` guarantees connection pools are explicitly closed, preventing `ResourceWarning: unclosed database` warnings in Python 3.12+.

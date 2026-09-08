---
name: yt-serve-testing
description: >-
  Use this skill whenever running, adding, debugging, or verifying unit and
  integration tests for yt_serve inside the Docker container environment.
---

# `yt_serve` Container Testing Workflow

This skill defines the mandatory test execution and verification standards for `yt_serve`.

## 1. Core Principles
* **Always Test in Container**: Never run tests directly against the host Python environment. The host environment may have mismatched Python versions, missing system packages, or missing native binaries (`ffmpeg`, `ffprobe`).
* **Dist Tool Shebang Convention**: [`build_image.py`](file:///home/tech-priest/myProjects/yt_playlist_dnlder/yt_serve/dist_utils/build_image.py) begins with `#!/usr/bin/env python3` and has executable permissions. **Never prepend `python3` or `python`**. Invoke it directly as an executable script:
  * From workspace root: `./yt_serve/dist_utils/build_image.py <args>`
  * From `yt_serve/` directory: `./dist_utils/build_image.py <args>`

## 2. Standard Test Workflow

### Step 1: Rebuild Test Container Target (Fast & Cached)
Rebuild the test image target before running tests to ensure your latest code changes are reflected:
```bash
./yt_serve/dist_utils/build_image.py -e test
```
> **Tip**: This target (`backend-test`) completely bypasses Node.js and frontend compilation. When layers are cached, rebuilds complete in ~2–3 seconds.

### Step 2: Run Tests

#### A. Run All Tests
```bash
docker run --rm yt_serve:test
```

#### B. Run a Specific Test Module
```bash
docker run --rm yt_serve:test tests.test_logging_engine
```

#### C. Run a Specific Test Class or Method
```bash
docker run --rm yt_serve:test tests.test_logging_engine.TestLoggingEngine.test_buffer_capacity_eviction
```

### Step 3: Verify Zero ResourceWarnings
Ensure no unclosed database connections, sockets, or file handles remain after tests run:
```bash
docker run --rm --entrypoint python yt_serve:test -W error::ResourceWarning -m unittest discover tests
```

## 3. Writing New Database Tests
When writing tests that touch database tables, repositories, or models:
* Always use the isolated in-memory SQLite sandbox from `tests.test_db_helper`:
  ```python
  from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db

  class MyTest(unittest.TestCase):
      def setUp(self):
          self.test_engine, self.TestingSession = create_isolated_test_db()
          self.db = self.TestingSession()

      def tearDown(self):
          dispose_isolated_test_db(self.test_engine, self.db)
  ```
* Never query `app.models.database.SessionLocal()` directly in tests, as it connects to the production database and can leave unclosed pooled connections.

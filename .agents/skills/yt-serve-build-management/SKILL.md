---
name: yt-serve-build-management
description: >-
  Use this skill whenever building Docker images, tagging releases, promoting
  dev images to production, or managing the container distribution lifecycle for yt_serve.
---

# `yt_serve` Container Build & Distribution Management

This skill defines conventions and commands for packaging, tagging, releasing, and pruning `yt_serve` container images using [`build_image.py`](file:///home/tech-priest/myProjects/yt_playlist_dnlder/yt_serve/dist_utils/build_image.py).

## 1. Tooling & Invocation Rules
* **Direct Execution**: [`build_image.py`](file:///home/tech-priest/myProjects/yt_playlist_dnlder/yt_serve/dist_utils/build_image.py) starts with `#!/usr/bin/env python3` and has executable permissions. **Never prepend `python3` or `python`**.
  * From workspace root: `./yt_serve/dist_utils/build_image.py <args>`
  * From `yt_serve/` directory: `./dist_utils/build_image.py <args>`
* **Separation of Concerns**: The build tool is dedicated strictly to image lifecycle management (building, tagging, promoting, pruning, releasing). Do **not** run or execute unit test suites through the build tool.

## 2. Target Environments (`-e`)

| Environment | Flag | Description |
| :--- | :--- | :--- |
| **Test** | `-e test` | Builds lightweight `backend-test` target. Bypasses Node.js/frontend build. Fast cached builds (~2–3s). Tags as `yt_serve:test`. |
| **Development** | `-e dev` | Full multi-stage build including frontend. Appends `-dirty` suffix if uncommitted git changes exist. Tags as `yt_serve:<version>-dev[-dirty]`. |
| **Production** | `-e prod` | Production-optimized build. Requires a clean git commit (or `--allow-dirty`). Tags as `yt_serve:<version>-release`. |

## 3. Common Operational Workflows

### A. Fast Test Build
```bash
./yt_serve/dist_utils/build_image.py -e test
```

### B. Development Build (Allows Dirty Workspace)
```bash
./yt_serve/dist_utils/build_image.py -e dev
```

### C. Clean Production Release
Production builds enforce that your git working tree has no uncommitted changes:
```bash
./yt_serve/dist_utils/build_image.py -e prod
```
To bypass git tree checks during experimentation:
```bash
./yt_serve/dist_utils/build_image.py -e prod --allow-dirty
```

### D. Promote Dev Image to Production (Zero Rebuild)
Promote an existing, verified dev image to production without recompiling layers:
```bash
./yt_serve/dist_utils/build_image.py --promote-to-prod
```

### E. Tagging Latest
`latest` tagging is decoupled from normal builds to prevent accidental overwrite in production:
```bash
./yt_serve/dist_utils/build_image.py -e prod --tag-latest
```

### F. Cache & Disk Pruning
Safely prune untagged dangling images and intermediate build layers:
```bash
./yt_serve/dist_utils/build_image.py --prune
```

### G. Force Clean Rebuild
Force complete rebuild without Docker layer cache:
```bash
./yt_serve/dist_utils/build_image.py -e test --fresh
```

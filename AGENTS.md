# Project Guidelines

## 1. GitHub Issue & Project Board Tracking
When creating, updating, categorizing, or tracking GitHub issues, milestones, or items on the Project Board, activate and follow the [`github-issue-tracking`](.agents/skills/github-issue-tracking/SKILL.md) skill.

## 2. Container Testing for `yt_serve`
* **Mandatory Container Rule**: Never run unit or integration tests directly against the host Python environment. Differing host packages, missing binary dependencies (`ffmpeg`, `ffprobe`), or local database files can produce false results. Always run tests inside the Docker test container.
* When running, debugging, or adding tests for `yt_serve`, activate and follow the [`yt-serve-testing`](.agents/skills/yt-serve-testing/SKILL.md) skill.

## 3. Container Builds & Distribution for `yt_serve`
* When packaging multi-stage images, managing tags, promoting dev images to production, or cleaning build cache, activate and follow the [`yt-serve-build-management`](.agents/skills/yt-serve-build-management/SKILL.md) skill.
* **Build Tool Invocation**: [`build_image.py`](yt_serve/dist_utils/build_image.py) contains a `#!/usr/bin/env python3` shebang and executable permissions. **Do NOT prepend `python3` or `python`**. Invoke it directly as `./yt_serve/dist_utils/build_image.py <args>` (or `./dist_utils/build_image.py <args>` from inside `yt_serve/`).

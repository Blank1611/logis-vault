---
name: github-issue-tracking
description: >-
  Use this skill whenever creating, updating, categorizing, or tracking GitHub issues,
  milestones, or Project Board items for Blank1611/yt_playlist_dnlder.
---

# GitHub Issue & Project Board Tracking

This skill defines the repository's standard issue and project tracking workflow for agents working on `Blank1611/yt_playlist_dnlder`.

## 1. Tooling & MCP Integration
* **Check MCP Availability**: Always verify if the GitHub MCP server (`github`) is active. When available, prefer using MCP tools (`create_issue`, `update_issue`, `list_issues`, etc.) to perform issue operations directly.
* **Target Repository**: `Blank1611/yt_playlist_dnlder`
* **Target Project Board**: GitHub Project #1 ([Blank1611's ytdld video download utility](https://github.com/users/Blank1611/projects/1))

## 2. Issue Title Conventions
Issue titles must always be prefixed with the appropriate category tag in square brackets:
* `[Feature]` — New capabilities, modules, or major features (e.g., `[Feature] Smooth Dual-Tier Progress Bar...`)
* `[Enhancement]` — Improvements to existing working features or UX enhancements
* `[Bug]` or `[Bug / Enhancement]` — Bug fixes, error handling, cancellation, or crash recovery (e.g., `[Bug / Enhancement] Robust Cancellation Engine...`)
* `[Refactor]` — Codebase restructuring, modularization, or architectural cleanups (e.g., `[Refactor] Frontend Modularization: Split Monolithic App.tsx`)
* `[Testing]` — Test harness, containerized testing, or test framework additions (e.g., `[Feature] Implement End-to-End (E2E) Test Suite with Full-Stack Container`)

> **Important**: Never prefix issue titles with `[RoadMap]`. The GitHub Project Board itself tracks the roadmap.

## 3. Standard Issue Metadata
* **Assignee**: `@Blank1611`
* **Labels**: Assign appropriate repository labels (e.g., `feature`, `enhancement`, `bug`, `testing`, `automation`, `refactor`).
* **Milestone**: Associate with the target milestone (e.g., `v2.1.0`, `v2.1.2`) when applicable.
* **Body Structure**:
  1. **Problem Statement / Motivation**: Clear explanation of what is needed and why.
  2. **Technical Architecture / Implementation Details**: Specific modules, classes, and APIs involved.
  3. **Acceptance Criteria**: Concrete, bulleted checklist of testable conditions.
  4. **Affected Components**: File paths or subsystems involved.

## 4. Documentation Synchronization
* Whenever an issue is created or updated, check if relevant local roadmap or architecture documents exist under `yt_serve/DOCS/` (e.g., `DOCS/ROADMAP_E2E_TESTING.md`).
* Ensure issue titles, milestone tags, and numbers remain synchronized between GitHub and local documentation.

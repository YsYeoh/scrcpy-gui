# scrcpy-gui design spec

**Date:** 2026-04-26  
**Status:** approved

## 1. Purpose

Build an **open source** desktop **GUI** that lets **non-technical Android testers** install and use **scrcpy** (screen mirroring) on **Windows** in v1, with **first-run download** of **ADB** and **scrcpy** into a user cache, plus clear status and help for **USB debugging**.

**Portfolio goal:** public GitHub repo, tagged releases, honest licensing and third-party notices, reproducible builds in CI.

## 2. Constraints (from product decisions)

| Topic | Decision |
|--------|----------|
| v1 platform | **Windows** first; macOS and Linux in later milestones |
| ADB + scrcpy | **On first use**, download from official/standard locations and **cache** under user data; **not** embedded in a fat installer (small wrapper installer) |
| Network | Normal internet; **GitHub and Google** CDNs allowed in v1 |
| UI scope (v1) | **Minimum:** list devices, **Start mirroring**, status/errors, short help for **USB debugging**; **no** big options screen |
| Distribution | **Open source** on **GitHub**; releases host the Windows `exe`/archive |

## 3. Out of scope (v1)

- Full scrcpy CLI options in the UI  
- iOS; wireless/WiFi pairing flows (can be future)  
- macOS notarization / Linux packages  
- Private corporate download mirrors and offline-only installs (design may allow manual path later)  

## 4. Recommended stack

- **Language:** Python **3.11+**  
- **UI:** **PySide6** (Qt 6)  
- **Packaging (Windows v1):** **PyInstaller** (single-folder or one-file, documented)  
- **HTTP:** `urllib` (stdlib) or `httpx` / `requests` (one dependency; `httpx` optional if you prefer) — use **one** and pin it  

*Rationale:* Fast iteration, matches repo’s Python/PyInstaller hints, fine for a small form-based v1, cross-plat when you add Mac/Linux.

## 5. Architecture

Five conceptual units; each is testable with clear IO boundaries.

1. **Paths / cache** — resolve OS-specific data directory, layout for `platform-tools/`, `scrcpy/`, and a small `versions.json` or `manifest` for what was installed.  
2. **Download + verify** — given pinned URLs and expected **SHA-256** (stored in code or a checked-in `vendor-manifest.json`), download to temp, verify hash, extract zip to cache. **Fail** with user-visible messages: network, hash mismatch, disk.  
3. **ADB service** — resolve path to `adb(.exe)` in cache, run `adb devices -l` (or equivalent), **parse** output to structured device list, detect **unauthorized** / **offline**.  
4. **scrcpy runner** — with optional device serial, start `scrcpy` as a **subprocess**; connect stdout/stderr to a log buffer for the UI; report exit code.  
5. **UI (PySide6)** — main window: help strip (USB debugging), table or list of devices, **Start mirroring** (enabled when exactly one device, or for first device in list — see §6), status bar and/or log panel, **Copy details** for support. On startup, **ensure tooling** (download if missing) before enabling actions.

**Dependency rule:** ADB and scrcpy are **not** in PATH by default; the app **only** uses binaries under the cache (unless an advanced “custom path” is added post-v1).

## 6. UX and behavior (v1)

- **Start mirroring** — if **one** device, start scrcpy for that serial. If **multiple**, either disable with hint “unplug until one device” or (preferred if trivial) a **row selection** in the list and start for selected; document which in the implementation plan.  
- **No device** — show message to connect USB, enable file transfer, enable USB debugging, and accept the RSA dialog on phone.  
- **unauthorized** — “Unlock phone, accept USB debugging prompt.”  
- **First run / download** — progress (determinate if content-length, else indeterminate) and no blocking modal without a cancel (optional cancel) path.

## 7. Pinning and updates

- Pin **concrete** `platform-tools` and `scrcpy` **version numbers** and **windows zip URLs** in one manifest.  
- Update policy for v1: **bump** manifest + new release; optional later: “check for newer manifest” (out of v1).  

## 8. Open source, legal, and notices

- Repository **license:** MIT (existing) is OK for this project’s own code.  
- Include **THIRD_PARTY_NOTICES.md** (or `LICENSES/`) for **scrcpy** (Apache-2.0), **Android platform-tools** (per Google’s terms in the download), and **PySide6/Qt** (LGPL); link from README.  
- Do not imply endorsement by scrcpy/Android/Google.  
- CI should **not** re-download in every job without caching, or use fixed artifacts to avoid flakiness (pin SHA in manifest and verify in tests for parsing only if feasible).

## 9. Error handling and logging

- All user-facing errors: **one short line** + optional “details” from process stderr or exception string.  
- **Copy to clipboard** for a blob that includes: app version, Windows version, manifest versions, last command lines (redact paths if PII is a concern — full paths are usually fine for internal debugging).

## 10. Testing (proportionate)

- **Unit tests:** manifest parsing, `adb devices` output parsing, path resolution (mocked env).  
- **No** requirement for integration tests with real ADB in CI in v1 (can be a manual checklist in README).

## 11. Success criteria

- A new tester on Windows can: install from **GitHub Release**, run app, see **first-time download** complete, connect one phone with **USB debugging**, and see the **mirroring window** without the terminal.  
- A second run uses **cached** binaries and starts faster.  
- License and **third-party** documentation are complete enough for a portfolio reviewer.

## 12. Follow-on (not v1)

- macOS (notarization), Linux (AppImage or similar)  
- Common scrcpy toggles (bitrate, resolution)  
- Optional internal mirror for downloads  

---

*This spec is the source of truth for the implementation plan dated the same day.*

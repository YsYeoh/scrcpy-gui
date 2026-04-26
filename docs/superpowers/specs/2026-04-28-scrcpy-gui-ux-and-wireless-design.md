# scrcpy-gui — UX, reliability, and wireless ADB (unified)

**Date:** 2026-04-28  
**Status:** draft (pending product review)  
**Supersedes for this scope:** Wireless ADB and several Phase 2 “optional/ future” items from `2026-04-27-scrcpy-gui-phase-2-design.md` (this doc is the new source of truth for the listed work below). v1 and Phase 2 shipped behaviors remain the baseline; this spec **adds and replaces** only what is written here.  
**Depends on:** `2026-04-26-scrcpy-gui-design.md`, `2026-04-27-scrcpy-gui-phase-2-design.md` (current `src/` as of implementation)

---

## 1. Purpose and scope

**Goal:** Improve **GUI usability**, **threading**, **scrcpy session lifecycle**, **supportability**, and add **two first-class wireless ADB flows** (USB→`tcpip` and **Android 11+ pairing**), in one coherent release, on **Windows** (same as today).

**In scope**

| Area | Deliverable |
|------|-------------|
| First-run / bootstrap | **Determinate** progress (bytes or %) when `Content-Length` is known; at minimum **indeterminate** bar with status text when not; `ensure_tooling` receives a real `on_progress` callback. |
| ADB device refresh | **No** `subprocess` blocking the **UI thread** for `adb devices`, `adb connect`, `adb pair`, `adb tcpip`, etc. |
| scrcpy process | **Single** managed session in the UI: **Start** disabled or replaced while running, **status** “Mirroring: running / exited (code)”, optional **Stop** to terminate the child, **no** silent second Start while one instance is already running (unless an explicit “New window” is later added — **out of scope**). |
| Log + support | **Capped** retained log for display and “Copy details” to avoid unbounded memory; “Copy details” still includes app version, paths, OS, and recent log tail. |
| Discoverability | **Window title** including **version**; **About** dialog: short description, version, **MIT**, pointer to `THIRD_PARTY_NOTICES` / project URL. |
| Device table | **Optional** **Model** column (from `adb devices -l`); parser extended to surface display-only model string when present. |
| A11y / polish | Sensible **focus order**; **F5** → Refresh devices; **Ctrl+Enter** → Start mirroring when enabled. |
| Wireless (both flows) | **Flow A — Over USB (tcpip):** user has a **USB-authorized** `device`; run `adb tcpip <port>` (default **5555** if unspecified), then user enters **IP:port**, **`adb connect`**, then Refresh. **Flow B — Android 11+ pairing:** user enters **pairing address:port** and **pairing code**, run **`adb pair`**, then **`adb connect`** to the **separate** connection address (from phone UI or history), then Refresh. **Connection help** updated: short “**Which method should I use?**” table. |

**Out of scope (this spec)**

- **Web UI**, system tray, **simultaneous multi-scrcpy** windows per machine.  
- **Manifest “update check”** against a remote URL (v1 spec still allows release-time manifest bump only).  
- **Free-form “custom scrcpy args”** text field (deferred; presets + current toggles stay the primary surface).  
- Exposing the **full** scrcpy feature set (audio, recording, turn screen off, etc.) as separate checkboxes — deferred unless a follow-up spec ties each flag to the **pinned** vendored scrcpy CLI.  
- **macOS/Linux** packaging; non-Win cache paths may exist in code but are not validated here.  

---

## 2. Architectural approaches (2–3 options) and recommendation

### Option 1 — Minimal change: ad hoc `QThread` in `main_window` only

Add more `QThread` subclasses beside `BootstrapThread` for refresh / wireless / start-path ADB, keep all orchestration in `MainWindow`.  

- **Pros:** Smallest file touch count at first.  
- **Cons:** `main_window.py` already large; more threads and state machines **without** a clear service boundary increase regression risk and complicate tests.

### Option 2 — `adb` + worker façade (recommended)

- **`adb.py`** (or a sibling `adb_ops.py`) exposes **small, testable** helpers: e.g. `run_adb(adb: Path, args: list[str]) -> CompletedProcess` (no UI), and higher-level `devices`, `connect`, `pair`, `tcpip` that **only** build `argv` and call `run_adb`. **Never** `shell=True`; **always** a list.  
- **UI layer:** `QObject` or `QThread` workers (one pattern or a small family) that call these helpers and emit `PySide6` signals with **structured** results (success, stderr+stdout, exit code). `MainWindow` only connects signals and updates widgets.  
- **scrcpy:** Prefer **`QProcess`** for the mirror process if feasible (native `stateChanged` / `finished`); if migration cost is high, a **dedicated** background thread that waits on `subprocess.Popen` and emits a **finished** signal is acceptable in the first increment, with a follow-up to consolidate on `QProcess`.  

- **Pros:** **Unit tests** for argv construction and output parsing; UI stays thin; matches existing **pure** modules like `connection_ux`, `mirroring_options`.  
- **Cons:** Slightly more files and upfront structure.

### Option 3 — asyncio + Qt (`qasync` or similar)

- **Pros:** Theoretical model for many concurrent IO operations.  
- **Cons:** New **runtime dependency** and event-loop bridging; **not** recommended for this codebase today.

**Recommendation:** **Option 2** for all ADB and wireless operations; scrcpy lifecycle on **`QProcess`** or a well-isolated “waiter” with explicit exit signal, never polling on the main thread.

---

## 3. Data flow and state

1. **Bootstrap (first run):** `ensure_tooling(m, log, on_progress)`; progress forwarded to a **QProgressBar** and/or **status** label. On completion, `adb devices` runs **off the UI thread**, then the main window applies the list.  
2. **Refresh:** same as (1) for `adb devices` only, off UI thread, then table + status from `connection_ux` (extended where needed for *only* wireless *hint* if useful — e.g. if list empty after failed connect, not raw adb spam).  
3. **Start mirroring:** re-fetch `adb devices` **off the UI thread** (or use last result if *very* recent — **optional** optimization, spec **requires** *correctness* on Start: **must** re-query list before launch to match current behavior intent). **Then** start scrcpy; UI shows **running** until `finished` / **Stop**.  
4. **Wireless — Flow A (USB tcpip):** user selects a **USB `device` row** (or exactly one) → `adb tcpip <port>` (Worker) → user enters `IP:port` → `adb connect IP:port` (Worker) → refresh list → user starts mirroring as for USB, using the new **emulator- or tcp- style** serial.  
5. **Wireless — Flow B (pair):** user runs `adb pair <addr:pairport> <code>` (Worker) → then `adb connect <addr:port>` (Worker) → refresh; address/port fields are **typed**; copy-paste from phone is supported.  

**QSettings (suggested keys, not exhaustive):** mirror existing `mirroring/…`; add e.g. `ui/window_geometry` (optional), `wireless/last_connect_host`, `wireless/last_connect_port`, `wireless/last_pair_host`, `wireless/last_pair_port` to reduce retyping (never store **pairing codes** or secrets).  

**Security:** ADB is **local trust**; binding nothing to a non-localhost server. The app only invokes **vendored** `adb` with **explicit argv**; do not pass user text through `cmd.exe` as a single string.

---

## 4. UI specification (condensed)

- **Main window:** Keep **table + status** as the **primary focus** (spacing: mirroring group may be collapsed or reordered in implementation so the device list reads as the center of attention; exact layout is implementation detail, goal is *visual hierarchy*).  
- **First-run / download:** **Progress** affordance in the same window (no long modal unless error).  
- **Scrcpy bar:** “**Mirroring:** Stopped / **Running** / **Exited (0)** / **Failed**” + **Stop** enabled only while running.  
- **Log:** **Circular / capped** buffer (e.g. last **N** lines and/or **max character** count for the widget); “Copy details” takes a **bounded** tail.  
- **Menu or buttons:** **About**; **Connection help** remains; help text extended per §1.  
- **Table:** **Serial** | **State** | **Model** (or “—” if unknown).  
- **Shortcuts:** **F5** refresh, **Ctrl+Enter** start.  
- **Wireless:** Either a **dialog** (recommended) or a **collapsible** group: two subflows with clear labels: **“Switch to network (USB required)”** and **“Pair new device (Android 11+)”**; do not block the main list behind a mandatory wizard.  

**Errors:** user-facing **one line** + log detail; `QMessageBox` for hard failures; pairing/connect failures must show **adb** stderr tail (capped) in the log, not a wall of text in a modal.

---

## 5. Testing

- **Unit tests:** all **new** argv builders and **extended** `parse_adb_devices_line` (or replace with structured parse) for `-l` model; golden tests for **pair** / **connect** / **tcpip** *argument lists* (no network in CI).  
- **Optional:** `pytest-qt` smoke for shortcuts — **not** required if timeboxed; **manual** checklist in README for wireless.  
- **No** requirement for ADB in CI.  

---

## 6. Success criteria

- On a slow link, a user can see **first-run** progress, not just log line spam.  
- The window **stays responsive** while ADB runs (no multi-second “white” freeze in typical cases).  
- After **Start mirroring**, the user cannot accidentally spawn a **second** scrcpy from the app without **Stop** or natural exit, and the UI always reflects **running** vs not.  
- A user can, following **in-app** help, complete **Flow A** or **Flow B** to get a `device` row and mirror **over Wi‑Fi**, as far as the device and network allow.  
- **Model** column shows a value when `adb devices -l` provides `model:…` for a row.  
- **About** and **version in title** make support handoffs easier.  

---

## 7. Relation to other docs

- **`2026-04-27-scrcpy-gui-phase-2-design.md`** said wireless and download progress were **out** or **future**; **this** document **promotes** them into a single implementation track. Where they conflict, **this** document wins.  
- After approval: create an **implementation plan** (superpowers: `writing-plans` skill) with ordered tasks: threading refactors, UI, `adb` extensions, dialog, help text, tests, README.  

---

## 8. Spec self-review (internal)

| Check | Result |
|-------|--------|
| Placeholders | None intentional; pin exact default **tcpip** port in the plan (spec allows **5555** as the usual default) so implementation is not ambiguous. |
| Consistency | Flow A and B are both in scope; Option 2 (service façade + workers) matches §3. |
| Scope | Large but bounded by §1 **Out of scope**; no web/tray/manifest check. |
| Ambiguity | **QProcess vs. thread wait** for scrcpy: spec allows first increment “waiter thread” with explicit follow-up; prefer `QProcess` in plan when low risk. **Pairing code** is not persisted — explicit in §3. |
| Concurrency | `adb` helpers must be safe to call from a **single** worker at a time per logical operation, or a **mutex** for shared `adb` subprocess usage if the platform requires serializing (document in plan if ADB is flaky when invoked concurrently; typical approach: **queue** operations in one worker). |

**Follow-up to resolve in implementation plan:** whether **one** serial ADB “command queue” thread is simpler than *N* ad hoc threads — **recommend** a single `AdbJobRunner` to avoid interleaved `adb` calls.

---

*User review gate: read §1–4 for product fit; §2–3 for engineering alignment. After any edits, re-run the placeholder row in §8.*  

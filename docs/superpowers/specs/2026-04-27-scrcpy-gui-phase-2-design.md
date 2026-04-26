# scrcpy-gui — Phase 2 (two releases: 1.1, then 1.2)

**Date:** 2026-04-27  
**Status:** approved (dialogue)  
**Depends on:** `docs/superpowers/specs/2026-04-26-scrcpy-gui-design.md` (v1 scope)

## 1. Why phase 2

v1 delivers **download ADB + scrcpy**, **list devices**, **start scrcpy** for **one** `device` with minimal UI. **Phase 2** extends that in **two** releases so non-technical testers get **reliability and clarity** before we add **mirroring quality** controls.

| Release | Version theme | User goal |
|--------|---------------|------------|
| **1.1** | *Connection & trust* | Always know the **next step** when the phone does not show as ready, and support **picking a device** when more than one is valid. |
| **1.2** | *Mirroring comfort* | Tweak how mirroring **looks and feels** (presets and a few checkboxes) without learning scrcpy’s CLI. |

**Non-goals for both:** parity with `scrcpy --help`, macOS/Linux packaging, wireless/TCPIP pairing — unless promoted in a later spec.

## 2. Release 1.1 — UX, guidance, and selection (no new scrcpy “quality” flags)

### 2.1 Objectives

- **Plain-language status** that depends on the **parsed device list** (and updates on Refresh and after bootstrap), not on raw ADB text.
- **Connection help** available as a first-class **Help** or **“Connection help”** action: short steps for **USB**, **USB debugging**, **RSA prompt** — *not* a crammed 100px text box in the main window. Optional: collapsible panel; acceptable MVP is a **modal dialog** or a **dedicated sub-panel** opened from a button.
- **Multiple `device` rows:** user **selects a row** in the table; **Start** runs scrcpy for the **selected serial** when that row’s state is `device`. If there is **exactly one** `device`, selection may be implicit (auto-select the row).
- **`unauthorized` / `offline` / empty list:** the status line and/or inline hint describe **one clear next action** (unlock phone, accept dialog, try another port/cable, use Refresh after fixing).
- **“Restart ADB”** (or **“Reset USB connection (ADB)”**): a button that runs `adb kill-server` then `adb start-server` (using the app’s **bundled** `adb`), with a one-line “try this if the list looks stuck” label. **Errors** show in the log; success refreshes the device list or shows a short confirmation in status.

### 2.2 Out of scope for 1.1

- Bitrate, max resolution, stay-awake, show-touches, **presets** — all **1.2**  
- “Download progress bar” is **optional**; only if v1 is missing a visible first-run progress affordance and it fits without scope creep

### 2.3 Technical notes (1.1)

- **Pure “guidance” logic** in a small module (e.g. one-line primary message, optional secondary detail) with **unit tests** from table-driven fixtures. No Qt in that module.
- **ADB server restart** implemented next to existing `subprocess` usage, Windows-only `CREATE_NO_WINDOW` where used elsewhere.
- **Table selection:** `QTableWidget` single-row selection; on **Start**, resolve serial from the **current row**; validate `state == "device"` before launching scrcpy.

### 2.4 Success criteria (1.1)

- With **two phones** in `device` state, a tester can **select** one and start mirroring **without** unplugging the other (they may still mirror one window only — that is a scrcpy limit unless we document otherwise).
- With `unauthorized`, the UI tells the user to **allow on the phone** and **Refresh** — with no need to read stderr.
- **Restart ADB** is one click and has no worse behavior than the user running the same `adb` commands in a hidden terminal.

## 3. Release 1.2 — Mirroring options (presets + a few toggles)

### 3.1 Objectives

- **Presets** (plain names), e.g. “Balanced”, “Faster (lower quality)”, “Sharper (higher quality)”, each mapping to a **documented, pinned** set of scrcpy CLI arguments compatible with the **vendored scrcpy** in `vendor-windows.json`.
- A small set of **checkboxes** (labels in everyday language) for things like **keep screen on**, **show touches**, **stay on top** — **only** if the pinned scrcpy on Windows supports them; drop or hide flags that are flaky.
- **Persist** last choice in **per-user** settings (e.g. `QSettings` or JSON under app data on Windows).
- **Scrcpy argv** built in a **single place** (pure function or small builder) with **golden tests** for each preset, so the main window does not hand-assemble command strings ad hoc.

### 3.2 Out of scope for 1.2

- Wireless debugging / `adb connect` flows (future spec)  
- Exposing every scrcpy switch  
- Changing the **1.1** device-selection or guidance model unless a bug fix requires it

### 3.3 Success criteria (1.2)

- After choosing a **preset**, a restart of the app **remembers** the choice.  
- Mirroring visibly **changes** along preset lines on a test device (manual acceptance); CI stays **unit-test-only**.

## 4. Documentation and support

- **README:** 1.1: “Connection help” and “Restart ADB.” 1.2: “Quality presets” and what they roughly do.  
- **THIRD_PARTY_NOTICES:** unchanged in spirit; scrcpy is still a separate work.

## 5. Spec self-review (internal)

1. **Placeholders:** none.  
2. **Consistency:** 1.1 = UX + ADB + selection; 1.2 = scrcpy argv + settings; matches the approved **C** split.  
3. **Scope:** Two releases are sufficient; wireless and CLI parity are explicitly out.  
4. **Ambiguity:** “One primary status line + optional help dialog” is fixed as dialog-or-panel opened by a **button** for 1.1 to avoid over-specifying Qt widgets.  
5. **Relation to v1 spec:** v1 is unchanged; this doc **adds** Phase 2 only.

---

*Next artifact after this spec: implementation plan for **1.1 only** (`docs/superpowers/plans/2026-04-27-scrcpy-gui-1.1-ux-reliability.md`). 1.2 is planned in a follow-up after 1.1 is shipped.*

from __future__ import annotations

# Preset values stored in QSettings and combo userData
PRESET_BALANCED = "balanced"
PRESET_FAST = "fast"
PRESET_SHARP = "sharp"

ALL_PRESETS = (PRESET_BALANCED, PRESET_FAST, PRESET_SHARP)


def build_scrcpy_args(
    preset: str,
    *,
    stay_awake: bool,
    show_touches: bool,
    always_on_top: bool,
) -> list[str]:
    """
    Return extra CLI args for the vendored scrcpy 3.3.x on Windows, after
    the executable path. ``-s SERIAL`` is added by the caller.
    """
    if preset not in ALL_PRESETS:
        msg = f"Unknown preset: {preset!r}"
        raise ValueError(msg)
    args: list[str] = []
    if preset == PRESET_FAST:
        args.extend(["--max-size=1024", "--video-bit-rate=4M"])
    elif preset == PRESET_SHARP:
        args.extend(["--max-size=1920", "--video-bit-rate=12M"])
    if stay_awake:
        args.append("--stay-awake")
    if show_touches:
        args.append("--show-touches")
    if always_on_top:
        args.append("--always-on-top")
    return args

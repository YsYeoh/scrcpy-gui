import pytest

from scrcpy_gui.mirroring_options import (
    PRESET_BALANCED,
    PRESET_FAST,
    PRESET_SHARP,
    build_scrcpy_args,
)


def test_balanced_is_empty_without_toggles() -> None:
    assert build_scrcpy_args(
        PRESET_BALANCED, stay_awake=False, show_touches=False, always_on_top=False
    ) == []


def test_fast_includes_size_and_rate() -> None:
    a = build_scrcpy_args(
        PRESET_FAST, stay_awake=False, show_touches=False, always_on_top=False
    )
    assert "--max-size=1024" in a
    assert "--video-bit-rate=4M" in a


def test_sharp_includes_higher_size_and_rate() -> None:
    a = build_scrcpy_args(
        PRESET_SHARP, stay_awake=False, show_touches=False, always_on_top=False
    )
    assert "--max-size=1920" in a
    assert "--video-bit-rate=12M" in a


def test_toggles() -> None:
    a = build_scrcpy_args(
        PRESET_BALANCED,
        stay_awake=True,
        show_touches=True,
        always_on_top=True,
    )
    assert a == [
        "--stay-awake",
        "--show-touches",
        "--always-on-top",
    ]


def test_unknown_preset_raises() -> None:
    with pytest.raises(ValueError, match="Unknown preset"):
        build_scrcpy_args("nope", stay_awake=False, show_touches=False, always_on_top=False)

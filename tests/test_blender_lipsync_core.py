from pathlib import Path

from blender_addons.mfa_lip_sync.core import (
    build_align_one_command,
    interval_to_frame_range,
    normalize_phone_label,
    parse_phone_intervals,
    phone_to_viseme,
)


def test_build_align_one_command():
    command = build_align_one_command(
        mfa_command="/opt/mfa/bin/mfa",
        wav_path="/data/audio.wav",
        transcript_path="/data/audio.lab",
        dictionary_path="english.dict",
        acoustic_model_path="english_am",
        output_path="/tmp/audio.TextGrid",
        temporary_directory="/tmp/mfa-work",
    )
    assert command == [
        "/opt/mfa/bin/mfa",
        "align_one",
        "/data/audio.wav",
        "/data/audio.lab",
        "english.dict",
        "english_am",
        "/tmp/audio.TextGrid",
        "--output_format",
        "long_textgrid",
        "--temporary_directory",
        "/tmp/mfa-work",
    ]


def test_parse_phone_intervals():
    tg_path = Path(__file__).parent.joinpath("data", "textgrid", "lipsync_fixture.TextGrid")
    intervals = parse_phone_intervals(tg_path)
    assert len(intervals) == 4
    assert intervals[0].label == "sil"
    assert intervals[-1].end == 1.2


def test_phone_normalization_and_viseme_mapping():
    assert normalize_phone_label("ay1") == "AY"
    assert normalize_phone_label("th_B") == "TH"
    assert phone_to_viseme("AY1") == "AI"
    assert phone_to_viseme("f") == "FV"
    assert phone_to_viseme("ZZZ", unknown_viseme="rest") == "rest"
    assert phone_to_viseme("P", phone_to_viseme_mapping={"P": "AI"}) == "AI"


def test_interval_to_frame_range():
    start_frame, end_frame = interval_to_frame_range(0.2, 0.5, fps=24, frame_start=1)
    assert start_frame == 6
    assert end_frame == 13

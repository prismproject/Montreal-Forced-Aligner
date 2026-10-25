from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import typing

DEFAULT_PHONE_TO_VISEME: typing.Dict[str, str] = {
    "AA": "AI",
    "AE": "AI",
    "AH": "AI",
    "AO": "O",
    "AW": "WQ",
    "AY": "AI",
    "B": "MBP",
    "CH": "TH",
    "D": "L",
    "DH": "TH",
    "EH": "E",
    "ER": "E",
    "EY": "E",
    "F": "FV",
    "G": "WQ",
    "HH": "rest",
    "IH": "E",
    "IY": "E",
    "JH": "TH",
    "K": "WQ",
    "L": "L",
    "M": "MBP",
    "N": "L",
    "NG": "L",
    "OW": "O",
    "OY": "O",
    "P": "MBP",
    "R": "WQ",
    "S": "TH",
    "SH": "TH",
    "T": "L",
    "TH": "TH",
    "UH": "U",
    "UW": "U",
    "V": "FV",
    "W": "WQ",
    "Y": "AI",
    "Z": "TH",
    "ZH": "TH",
    "SIL": "rest",
    "SP": "rest",
    "SPN": "rest",
}


@dataclass(frozen=True)
class PhoneInterval:
    start: float
    end: float
    label: str


def build_align_one_command(
    mfa_command: str,
    wav_path: typing.Union[str, Path],
    transcript_path: typing.Union[str, Path],
    dictionary_path: typing.Union[str, Path],
    acoustic_model_path: typing.Union[str, Path],
    output_path: typing.Union[str, Path],
    temporary_directory: typing.Optional[typing.Union[str, Path]] = None,
) -> typing.List[str]:
    command = [
        mfa_command,
        "align_one",
        str(wav_path),
        str(transcript_path),
        str(dictionary_path),
        str(acoustic_model_path),
        str(output_path),
        "--output_format",
        "long_textgrid",
    ]
    if temporary_directory:
        command.extend(["--temporary_directory", str(temporary_directory)])
    return command


def normalize_phone_label(label: str) -> str:
    normalized = (label or "").strip().upper()
    if not normalized:
        return ""
    if normalized.startswith("<") and normalized.endswith(">"):
        return "SIL"
    normalized = normalized.split("_")[0]
    normalized = re.sub(r"\d+$", "", normalized)
    normalized = re.sub(r"[^A-Z]", "", normalized)
    if normalized in {"", "SIL", "SP", "SPN"}:
        return normalized or "SIL"
    return normalized


def phone_to_viseme(
    phone_label: str,
    phone_to_viseme_mapping: typing.Optional[typing.Mapping[str, str]] = None,
    unknown_viseme: str = "rest",
) -> str:
    mapping = dict(DEFAULT_PHONE_TO_VISEME)
    if phone_to_viseme_mapping:
        mapping.update({normalize_phone_label(k): v for k, v in phone_to_viseme_mapping.items()})
    normalized = normalize_phone_label(phone_label)
    return mapping.get(normalized, unknown_viseme)


def seconds_to_frame(seconds: float, fps: float, frame_start: int = 1) -> int:
    return int(round(frame_start + (seconds * fps)))


def interval_to_frame_range(
    start_seconds: float,
    end_seconds: float,
    fps: float,
    frame_start: int = 1,
) -> typing.Tuple[int, int]:
    start_frame = seconds_to_frame(start_seconds, fps, frame_start=frame_start)
    end_frame = max(start_frame, seconds_to_frame(end_seconds, fps, frame_start=frame_start))
    return start_frame, end_frame


def _strip_textgrid_string(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def parse_phone_intervals(textgrid_path: typing.Union[str, Path]) -> typing.List[PhoneInterval]:
    tg_path = Path(textgrid_path)
    if not tg_path.exists():
        raise FileNotFoundError(f"Alignment file does not exist: {tg_path}")

    target_tier_names = {"phones", "phone", "segments"}
    selected_tier = None
    current_tier = None
    in_target_tier = False
    in_interval = False

    intervals: typing.List[PhoneInterval] = []

    current_start: typing.Optional[float] = None
    current_end: typing.Optional[float] = None
    current_label = ""

    with tg_path.open("r", encoding="utf8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("item ["):
                in_interval = False
                current_tier = None
                in_target_tier = False
                continue
            if line.startswith("name ="):
                current_tier = _strip_textgrid_string(line.split("=", 1)[1]).lower()
                if selected_tier is None and current_tier in target_tier_names:
                    selected_tier = current_tier
                if selected_tier is None and current_tier:
                    selected_tier = current_tier
                in_target_tier = current_tier == selected_tier
                continue
            if not in_target_tier:
                continue
            if line.startswith("intervals ["):
                if (
                    in_interval
                    and current_start is not None
                    and current_end is not None
                    and current_end > current_start
                ):
                    intervals.append(
                        PhoneInterval(start=current_start, end=current_end, label=current_label)
                    )
                in_interval = True
                current_start = None
                current_end = None
                current_label = ""
                continue
            if not in_interval:
                continue
            if line.startswith("xmin ="):
                current_start = float(line.split("=", 1)[1].strip())
            elif line.startswith("xmax ="):
                current_end = float(line.split("=", 1)[1].strip())
            elif line.startswith("text ="):
                current_label = _strip_textgrid_string(line.split("=", 1)[1])

    if in_interval and current_start is not None and current_end is not None and current_end > current_start:
        intervals.append(PhoneInterval(start=current_start, end=current_end, label=current_label))

    if not selected_tier:
        raise ValueError(f"No phone tier found in alignment file: {tg_path}")
    if not intervals:
        raise ValueError(f"No phone intervals found in alignment file: {tg_path}")

    valid_intervals = []
    for interval in intervals:
        if interval.end <= interval.start:
            continue
        valid_intervals.append(interval)
    return valid_intervals

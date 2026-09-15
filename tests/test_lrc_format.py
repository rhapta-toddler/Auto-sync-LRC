import pytest

from auto_sync_lrc.cli import (
    LyricLine,
    build_lrc,
    format_timestamp,
    parse_lyrics,
    validate_timestamps,
)


def test_parse_lyrics_separates_tags_blanks_and_sung_lines():
    source = "[intro]\n\n[verse]\n\nHush now baby close your eyes\nThe moon is watching from the skies\n\n[outro]\n"
    parsed = parse_lyrics(source)

    assert [line.text for line in parsed.sung] == [
        "Hush now baby close your eyes",
        "The moon is watching from the skies",
    ]
    assert [line.index for line in parsed.sung] == [0, 1]
    assert parsed.raw_lines[0] == "[intro]"


def test_parse_lyrics_no_sung_lines():
    parsed = parse_lyrics("[intro]\n\n[outro]\n")
    assert parsed.sung == []


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0.0, "[00:00.00]"),
        (5.5, "[00:05.50]"),
        (65.2, "[01:05.20]"),
        (600.0, "[10:00.00]"),
    ],
)
def test_format_timestamp(seconds, expected):
    assert format_timestamp(seconds) == expected


def test_format_timestamp_rejects_negative():
    with pytest.raises(ValueError):
        format_timestamp(-1.0)


def test_validate_timestamps_accepts_good_input():
    sung = [LyricLine(0, "a"), LyricLine(1, "b"), LyricLine(2, "c")]
    timestamps = {0: 1.0, 1: 2.0, 2: 3.0}
    assert validate_timestamps(sung, timestamps, duration=10.0) == []


def test_validate_timestamps_flags_missing_index():
    sung = [LyricLine(0, "a"), LyricLine(1, "b")]
    timestamps = {0: 1.0}
    problems = validate_timestamps(sung, timestamps, duration=10.0)
    assert any("missing" in p for p in problems)


def test_validate_timestamps_flags_non_increasing():
    sung = [LyricLine(0, "a"), LyricLine(1, "b")]
    timestamps = {0: 5.0, 1: 5.0}
    problems = validate_timestamps(sung, timestamps, duration=10.0)
    assert any("strictly increase" in p for p in problems)


def test_validate_timestamps_flags_out_of_range():
    sung = [LyricLine(0, "a")]
    timestamps = {0: 20.0}
    problems = validate_timestamps(sung, timestamps, duration=10.0)
    assert any("outside the song's duration" in p for p in problems)


def test_build_lrc_stamps_sung_lines_and_preserves_tags():
    source = "[verse]\n\nHush now baby\nSleep soon\n\n[outro]\n"
    parsed = parse_lyrics(source)
    timestamps = {0: 1.5, 1: 4.0}

    lrc = build_lrc(parsed, timestamps)

    assert "[verse]" in lrc
    assert "[00:01.50] Hush now baby" in lrc
    assert "[00:04.00] Sleep soon" in lrc
    assert "[outro]" in lrc

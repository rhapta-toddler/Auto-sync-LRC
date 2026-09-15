#!/usr/bin/env python3
"""Auto-sync-LRC: turn a plain-text lyric sheet + its MP3 into a timed .lrc file.

Pipeline: local Whisper (large model) transcribes the audio with word-level
timestamps; an LLM (Anthropic, OpenAI, or any OpenAI-compatible provider)
reads that transcript alongside the clean lyric lines and returns a timestamp
for each line (robust to ASR mishearings, reordering, and script/
transliteration differences); the result is validated and written out as a
standard [mm:ss.xx]-tagged .lrc file.

Usage:
    auto-sync-lrc SONG.mp3 LYRICS.txt --language ja [--whisper-model large-v3] [--out SONG.lrc]

Env vars (see README.md for the full list): set ANTHROPIC_API_KEY (default
provider) or OPENAI_API_KEY / LLM_PROVIDER+LLM_API_KEY+LLM_BASE_URL for any
other OpenAI-compatible provider.
"""
import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

from auto_sync_lrc.align import align_lines
from auto_sync_lrc.transcribe import transcribe

TAG_RE = re.compile(r"^\[[^\]]+\]$")


@dataclass
class LyricLine:
    index: int
    text: str


@dataclass
class ParsedLyrics:
    """The lyric file's lines, in original order, each tagged untimed or sung."""

    raw_lines: list[str]
    sung: list[LyricLine]


def parse_lyrics(source: str) -> ParsedLyrics:
    """Split a plain lyric sheet into structural lines and sung lines.

    A line that is only a bracketed tag (`[verse]`, `[chorus]`, ...) or blank is
    structural and stays untimed; everything else is a sung line needing a
    timestamp, numbered in the order it appears.
    """
    raw_lines = [line.rstrip("\n") for line in source.splitlines()]
    sung: list[LyricLine] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped or TAG_RE.match(stripped):
            continue
        sung.append(LyricLine(index=len(sung), text=stripped))
    return ParsedLyrics(raw_lines=raw_lines, sung=sung)


def probe_duration(mp3_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(mp3_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def format_timestamp(seconds: float) -> str:
    if seconds < 0:
        raise ValueError(f"negative timestamp: {seconds}")
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"[{minutes:02d}:{remainder:05.2f}]"


def validate_timestamps(sung: list[LyricLine], timestamps: dict[int, float], duration: float) -> list[str]:
    """Return a list of problems; empty means the timestamps are usable."""
    problems: list[str] = []
    expected = {line.index for line in sung}
    got = set(timestamps.keys())
    if got != expected:
        missing = expected - got
        extra = got - expected
        if missing:
            problems.append(f"missing timestamps for line index(es): {sorted(missing)}")
        if extra:
            problems.append(f"unexpected line index(es) in response: {sorted(extra)}")
        return problems

    ordered = [timestamps[line.index] for line in sung]
    for i, t in enumerate(ordered):
        if not (0 <= t <= duration):
            problems.append(
                f"line {i} timestamp {t:.2f}s is outside the song's duration (0-{duration:.2f}s)"
            )
    for i in range(1, len(ordered)):
        if ordered[i] <= ordered[i - 1]:
            problems.append(
                f"line {i} timestamp {ordered[i]:.2f}s does not strictly increase over "
                f"line {i - 1}'s {ordered[i - 1]:.2f}s"
            )
    return problems


def build_lrc(parsed: ParsedLyrics, timestamps: dict[int, float]) -> str:
    """Re-emit the original lines, stamping sung lines and leaving tags untimed."""
    out_lines: list[str] = []
    sung_cursor = 0
    for raw in parsed.raw_lines:
        stripped = raw.strip()
        if not stripped or TAG_RE.match(stripped):
            out_lines.append(raw)
            continue
        line = parsed.sung[sung_cursor]
        sung_cursor += 1
        stamp = format_timestamp(timestamps[line.index])
        out_lines.append(f"{stamp} {line.text}")
    return "\n".join(out_lines) + "\n"


def run(mp3_path: Path, lyrics_path: Path, language: str, whisper_model: str, out_path: Path, provider: str | None = None) -> None:
    source = lyrics_path.read_text(encoding="utf-8")
    parsed = parse_lyrics(source)
    if not parsed.sung:
        sys.exit("no sung lines found in the lyrics file - nothing to time")

    print(f"probing {mp3_path} ...")
    duration = probe_duration(mp3_path)
    print(f"duration: {duration:.2f}s, {len(parsed.sung)} sung lines to time")

    print(f"transcribing with faster-whisper ({whisper_model}) ...")
    transcript = transcribe(mp3_path, language=language, model_size=whisper_model)

    print("aligning lyric lines against the transcript with the configured LLM ...")
    timestamps = align_lines(parsed.sung, transcript, language=language, provider=provider)
    problems = validate_timestamps(parsed.sung, timestamps, duration)

    if problems:
        print("first alignment attempt had problems, retrying once:")
        for p in problems:
            print(f"  - {p}")
        timestamps = align_lines(parsed.sung, transcript, language=language, retry_feedback=problems, provider=provider)
        problems = validate_timestamps(parsed.sung, timestamps, duration)

    if problems:
        print("alignment failed validation after retry - refusing to write a guessed .lrc:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    lrc = build_lrc(parsed, timestamps)
    out_path.write_text(lrc, encoding="utf-8")
    print(f"wrote {out_path}")


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))  # picks up a .env from the cwd or any parent, if present

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mp3", type=Path, help="path to the song's MP3 file")
    parser.add_argument("lyrics", type=Path, help="path to the plain-text lyrics file")
    parser.add_argument("--language", required=True, help="ISO 639-1 language code the song is sung in, e.g. en, ja, yue")
    parser.add_argument("--whisper-model", default="large-v3", help="faster-whisper model size (default: large-v3)")
    parser.add_argument("--out", type=Path, default=None, help="output .lrc path (default: alongside the MP3)")
    parser.add_argument(
        "--provider",
        default=None,
        help="LLM provider for the alignment step: anthropic (default), openai, or any other "
        "OpenAI-compatible name (with LLM_BASE_URL set). Overrides LLM_PROVIDER.",
    )
    args = parser.parse_args()

    out_path = args.out or args.mp3.with_suffix(".lrc")
    run(args.mp3, args.lyrics, args.language, args.whisper_model, out_path, provider=args.provider)


if __name__ == "__main__":
    main()

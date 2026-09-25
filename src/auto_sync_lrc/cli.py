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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv, find_dotenv

from auto_sync_lrc.align import align_lines
from auto_sync_lrc.errors import SyncError
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


def probe_duration(audio_path: Path) -> float:
    import av

    try:
        with av.open(str(audio_path)) as container:
            if container.duration is None:
                raise SyncError(f"could not read the length of {audio_path.name}")
            return container.duration / av.time_base
    except av.error.FFmpegError as exc:
        raise SyncError(f"could not open {audio_path.name} as audio: {exc}") from exc


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


def sync_song(
    mp3_path: Path,
    lyrics_text: str,
    language: str,
    whisper_model: str,
    out_path: Path,
    provider: str | None = None,
    log: Callable[[str], None] = print,
) -> Path:
    """Run the whole pipeline and write the .lrc. Raises SyncError on any user-actionable problem."""
    parsed = parse_lyrics(lyrics_text)
    if not parsed.sung:
        raise SyncError("No lyrics found - paste or open the song's words first.")

    log(f"Reading {mp3_path.name} ...")
    duration = probe_duration(mp3_path)
    log(f"Song length {duration:.0f}s, {len(parsed.sung)} lyric lines to time.")

    log(f"Listening to the song with Whisper ({whisper_model}). The first run downloads the speech model, which can take a while ...")
    transcript = transcribe(mp3_path, language=language, model_size=whisper_model)

    log("Matching your lyrics to what was heard ...")
    timestamps = align_lines(parsed.sung, transcript, language=language, provider=provider)
    problems = validate_timestamps(parsed.sung, timestamps, duration)

    if problems:
        log("First attempt had problems, retrying once ...")
        timestamps = align_lines(parsed.sung, transcript, language=language, retry_feedback=problems, provider=provider)
        problems = validate_timestamps(parsed.sung, timestamps, duration)

    if problems:
        raise SyncError(
            "Could not line the lyrics up with the song reliably, so no file was written:\n- "
            + "\n- ".join(problems)
        )

    out_path.write_text(build_lrc(parsed, timestamps), encoding="utf-8")
    log(f"Done: {out_path}")
    return out_path


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
    try:
        lyrics_text = args.lyrics.read_text(encoding="utf-8")
        sync_song(args.mp3, lyrics_text, args.language, args.whisper_model, out_path, provider=args.provider)
    except SyncError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()

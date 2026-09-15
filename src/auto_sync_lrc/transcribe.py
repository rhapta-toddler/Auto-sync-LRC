"""Local speech-to-text via faster-whisper, with word-level timestamps.

No API key, no per-call cost - this is why the pipeline uses a local Whisper
model for the audio-heavy step instead of a paid multimodal LLM. `large-v3` is
the default because there's no cost penalty for using the most accurate model
locally, only a slower first run (the model, ~3 GB, downloads once from
Hugging Face and is cached).

Cantonese note: only `large-v3` recognizes Cantonese (`yue`) as such - smaller
Whisper models silently fall back to Mandarin recognition. Always request
`large-v3` for Cantonese songs.
"""
from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel

_model_cache: dict[str, WhisperModel] = {}


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Transcript:
    words: list[Word]

    def as_prompt_text(self) -> str:
        """Render as `[start-end] word` lines, one per word, for an LLM prompt."""
        return "\n".join(f"[{w.start:.2f}-{w.end:.2f}] {w.text}" for w in self.words)


def _get_model(model_size: str) -> WhisperModel:
    if model_size not in _model_cache:
        _model_cache[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model_cache[model_size]


def transcribe(mp3_path: Path, language: str, model_size: str = "large-v3") -> Transcript:
    model = _get_model(model_size)
    segments, _info = model.transcribe(
        str(mp3_path),
        language=language,
        word_timestamps=True,
        vad_filter=False,
        beam_size=5,
    )
    words: list[Word] = []
    for segment in segments:
        for word in segment.words or []:
            words.append(Word(text=word.word.strip(), start=word.start, end=word.end))
    return Transcript(words=words)

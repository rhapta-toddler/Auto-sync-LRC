# Auto-sync-LRC

Turn a plain-text lyric sheet plus its MP3 into a timed `.lrc` file, in any
language.

Pipeline: local Whisper (`large-v3` by default) transcribes the audio with
word-level timestamps; an LLM reads that transcript alongside the clean lyric
lines and returns a timestamp for each line; the result is validated and
written out as a standard `[mm:ss.xx]`-tagged `.lrc` file.

Whisper does the audio-heavy work locally and for free; the LLM only ever
sees text (never the audio itself), so that step stays cheap even for a full
song's worth of lines - and because it's text-only, it's provider-agnostic:
plug in Anthropic, OpenAI, or any other OpenAI-compatible chat-completions
endpoint.

## Setup

1. `ffmpeg` must be on `PATH` (`faster-whisper` and `ffprobe` both need it).
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` (or otherwise export the variables). Pick a
   provider for the alignment step:
   - **Anthropic (default)**: set `ANTHROPIC_API_KEY`. `ANTHROPIC_MODEL` is
     optional - see `.env.example` for cheaper/higher-accuracy alternatives.
   - **OpenAI**: set `LLM_PROVIDER=openai` and `OPENAI_API_KEY`. `OPENAI_MODEL`
     and `OPENAI_BASE_URL` (e.g. for Azure OpenAI) are optional.
   - **Anything else OpenAI-compatible** (Groq, DeepSeek, Together, a local
     vLLM server, ...): set `LLM_PROVIDER` to any name, plus `LLM_API_KEY`,
     `LLM_MODEL`, and `LLM_BASE_URL` pointing at its chat-completions
     endpoint.
   `--provider` on the command line overrides `LLM_PROVIDER` for a single run.
4. First run downloads the Whisper model from Hugging Face - `large-v3` is
   about 3 GB, one-time.

## Usage

Lyrics file format: one sung line per line; a line that is *only* a bracketed
tag (`[verse]`, `[chorus]`, `[intro]`, `[outro]`, `[bridge]`, ...) or blank is
treated as a structural marker and stays untimed in the output.

```
python lrc_sync.py SONG.mp3 LYRICS.txt --language ja
```

- `--language` is an ISO 639-1 code Whisper understands (`en`, `es`, `fr`,
  `de`, `ja`, `ko`, `zh`, `yue`, `pt`, `ru`, ...).
- `--whisper-model` overrides the model size (default `large-v3`).
- `--out` overrides the output path (default: the MP3's name with `.lrc`).

**Cantonese and other less-common languages/dialects**: only `large-v3`
reliably recognizes Cantonese (`yue`) as Cantonese - smaller Whisper models
silently fall back to Mandarin recognition. Always use `large-v3` (the
default) for those; check the output more carefully regardless.

If the alignment step can't produce a fully valid set of timestamps (every
line covered, strictly increasing, inside the song's duration) after one
retry, the tool refuses to write a guessed `.lrc` and reports exactly what
went wrong instead.

## Tests

```
pytest tests/
```

Covers lyric parsing, timestamp formatting, and validation - no network or
Whisper model download required.

## License

MIT - see [LICENSE](LICENSE).

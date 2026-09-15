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

## Quick start

Pick whichever fits how you work. All three need an API key for one LLM
provider (Anthropic by default, OpenAI, or any other OpenAI-compatible
endpoint) - see [Provider setup](#provider-setup) below.

### Option A - Docker (no local Python/ffmpeg needed)

```
docker run --rm -v "$PWD":/data -e ANTHROPIC_API_KEY \
  ghcr.io/luoarting-hub/auto-sync-lrc:latest song.mp3 lyrics.txt --language ja
```

Everything (`ffmpeg`, Whisper, the alignment SDKs) is baked into the image -
just Docker and an API key. Swap `-e ANTHROPIC_API_KEY` for `-e
OPENAI_API_KEY -e LLM_PROVIDER=openai` (or the equivalent `LLM_*` vars) to use
a different provider. `-v "$PWD":/data` mounts your current folder so the tool
can read `song.mp3`/`lyrics.txt` and write the `.lrc` back into it.

### Option B - pip install

```
pip install git+https://github.com/luoarting-hub/Auto-sync-LRC.git
export ANTHROPIC_API_KEY=sk-ant-...
auto-sync-lrc song.mp3 lyrics.txt --language ja
```

Needs `ffmpeg` on `PATH` yourself (`brew install ffmpeg` / `apt install
ffmpeg` / `winget install ffmpeg`).

### Option C - clone + one setup script

```
git clone https://github.com/luoarting-hub/Auto-sync-LRC.git
cd Auto-sync-LRC
./install.sh        # or .\install.ps1 on Windows
```

Checks for `ffmpeg`, creates a `.venv`, installs the package into it, and
walks you through writing a `.env` with your chosen provider's API key (auto-
loaded on every run afterward - no need to `export` it yourself).

First run of any option downloads the Whisper model from Hugging Face -
`large-v3` is about 3 GB, one-time.

## Provider setup

- **Anthropic (default)**: set `ANTHROPIC_API_KEY`. `ANTHROPIC_MODEL` is
  optional - see `.env.example` for cheaper/higher-accuracy alternatives.
- **OpenAI**: set `LLM_PROVIDER=openai` and `OPENAI_API_KEY`. `OPENAI_MODEL`
  and `OPENAI_BASE_URL` (e.g. for Azure OpenAI) are optional.
- **Anything else OpenAI-compatible** (Groq, DeepSeek, Together, a local
  vLLM server, ...): set `LLM_PROVIDER` to any name, plus `LLM_API_KEY`,
  `LLM_MODEL`, and `LLM_BASE_URL` pointing at its chat-completions endpoint.

`--provider` on the command line overrides `LLM_PROVIDER` for a single run.
A `.env` file in the current (or a parent) directory is loaded automatically.

## Usage

Lyrics file format: one sung line per line; a line that is *only* a bracketed
tag (`[verse]`, `[chorus]`, `[intro]`, `[outro]`, `[bridge]`, ...) or blank is
treated as a structural marker and stays untimed in the output.

```
auto-sync-lrc SONG.mp3 LYRICS.txt --language ja
```

(Docker users: drop `auto-sync-lrc` and use the `docker run ...` form above -
the image's entrypoint already runs it.)

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
pip install -e ".[test]"
pytest tests/
```

Covers lyric parsing, timestamp formatting, and validation - no network or
Whisper model download required.

## License

MIT - see [LICENSE](LICENSE).

# Auto-sync-LRC

Turn a song (MP3) and its plain lyrics into a synced `.lrc` file, so the words
light up in time with the music in any lyrics-aware player. Works in any
language.

Website: <https://rhapta-toddler.github.io/Auto-sync-LRC/> (source in [`site/`](site/)).

## Install on Windows (no technical skills needed)

1. Open the [latest release](https://github.com/luoarting-hub/Auto-sync-LRC/releases/latest)
   and download **Auto-sync-LRC-Setup.exe**.
2. Double-click it. Windows may say *"Windows protected your PC"* because the
   app is new and not yet code-signed. Click **More info**, then **Run anyway**.
3. Click **Next**, then **Install**, then **Finish**. No administrator password
   is needed.
4. In the window that opens:
   1. Choose your song.
   2. Paste the lyrics (or open a `.txt` file).
   3. Pick the language it is sung in.
   4. Paste your AI **API key** (see below), then click **Create synced lyrics**.

The finished `song.lrc` is saved right next to your song.

**What you need**

- **An API key** from an AI service - the app uses it to match your lyrics to
  what was heard in the song. Get one from
  [Anthropic (Claude)](https://console.anthropic.com/settings/keys) or
  [OpenAI](https://platform.openai.com/api-keys). It is billed by the AI
  service (a few lines of text per song, so very cheap) and is saved only on
  your own computer.
- **An internet connection**, and about 3 GB of free space the first time: the
  app downloads its speech-recognition model once. Choose *Balanced* or *Fast*
  accuracy in the window for a smaller download and quicker results; *Best
  quality* is slowest on computers without a powerful graphics card.

Mac and Linux: there is no one-click installer yet, use one of the options
under [For developers](#for-developers) below.

## How it works

A speech-recognition model ([Whisper](https://github.com/SYSTRAN/faster-whisper))
runs on your own computer and listens to the song to find when each word is
sung. An AI service then matches your clean lyrics to those timings, line by
line. It only ever receives text, never the audio. The result is checked
(every line covered, times strictly increasing, inside the song's length)
and, if it cannot be made reliable, no file is written rather than a guessed
one.

## For developers

Pick whichever fits how you work. All options need an API key for one LLM
provider (Anthropic by default, OpenAI, or any OpenAI-compatible endpoint) -
see [Provider setup](#provider-setup).

### Option A - Docker

```
docker run --rm -v "$PWD":/data -e ANTHROPIC_API_KEY \
  ghcr.io/luoarting-hub/auto-sync-lrc:latest song.mp3 lyrics.txt --language ja
```

Everything is baked into the image - just Docker and an API key. Swap `-e
ANTHROPIC_API_KEY` for `-e OPENAI_API_KEY -e LLM_PROVIDER=openai` (or the
equivalent `LLM_*` vars) to use a different provider. `-v "$PWD":/data`
mounts your current folder so the tool can read `song.mp3`/`lyrics.txt` and
write the `.lrc` back into it.

### Option B - pip install

```
pip install git+https://github.com/luoarting-hub/Auto-sync-LRC.git
export ANTHROPIC_API_KEY=sk-ant-...
auto-sync-lrc song.mp3 lyrics.txt --language ja
```

This also installs a `auto-sync-lrc-gui` command that opens the same window
as the Windows app.

### Option C - clone + one setup script

```
git clone https://github.com/luoarting-hub/Auto-sync-LRC.git
cd Auto-sync-LRC
./install.sh        # or .\install.ps1 on Windows
```

Creates a `.venv`, installs the package into it, and walks you through
writing a `.env` with your chosen provider's API key (auto-loaded on every
run afterward - no need to `export` it yourself).

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

## Command-line usage

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

## Building the Windows installer

Pushing a tag such as `v0.2.0` runs
[`.github/workflows/build-windows-installer.yml`](.github/workflows/build-windows-installer.yml),
which builds the app with PyInstaller, wraps it with Inno Setup
([`packaging/auto-sync-lrc.iss`](packaging/auto-sync-lrc.iss)), smoke-tests
both the packaged app and a silent install, and attaches
`Auto-sync-LRC-Setup.exe` to the GitHub release. The same workflow can be run
by hand from the Actions tab to get the installer as a build artifact.

## Tests

```
pip install -e ".[test]"
pytest tests/
```

Covers lyric parsing, timestamp formatting, and validation - no network or
Whisper model download required.

## License

MIT - see [LICENSE](LICENSE).

"""Align clean lyric lines against a Whisper transcript using an LLM.

Provider-agnostic: the alignment step is text-only (the model never hears the
audio - it only ever sees the ordered lyric lines and Whisper's timestamped
word transcript), so unlike the audio-transcription step this genuinely works
across vendors. Built in: Anthropic (Claude) and OpenAI, plus any other
OpenAI-compatible chat-completions endpoint (Groq, DeepSeek, Together, a
local vLLM server, ...) via a base URL.

Its job is semantic matching (ASR mishearings, reordering, transliteration/
script differences), anchored strictly to the given lines and the given
timestamps, not free transcription. That keeps the call cheap (text tokens
only, no audio) and keeps output verifiable, since every returned timestamp
must trace back to a word Whisper actually heard.
"""
import json
import os
import re
import sys

SYSTEM_PROMPT = """\
You align song lyrics to an ASR transcript. You will be given:
1. A numbered list of the song's lyric lines, in the order they are sung.
2. A word-level transcript from Whisper, as `[start-end] word` lines, in \
chronological order.

The transcript may misspell or mishear words, use a different script or \
romanization, or drop words the singer held or ran together - do not let \
that stop you from matching a lyric line to the closest matching stretch of \
the transcript by sound and meaning, in the target language given to you.

Return ONLY a JSON array, one object per lyric line, in the exact form:
[{"index": 0, "start_seconds": 12.34}, {"index": 1, "start_seconds": 15.02}, ...]

Rules:
- Every lyric line index must appear exactly once.
- start_seconds must be a timestamp that appears in (or between) the given \
transcript word timestamps - do not invent times outside the transcript's range.
- Timestamps must strictly increase with the lyric lines' order, since the \
lines are sung in that order.
- Output nothing but the JSON array - no prose, no code fences.
"""


def _build_user_prompt(sung_lines, transcript, language: str, retry_feedback=None) -> str:
    lines_block = "\n".join(f"{line.index}: {line.text}" for line in sung_lines)
    parts = [
        f"Language the song is sung in: {language}",
        "",
        "Lyric lines:",
        lines_block,
        "",
        "Whisper transcript:",
        transcript.as_prompt_text(),
    ]
    if retry_feedback:
        parts += [
            "",
            "Your previous answer had problems - fix them and answer again:",
            *(f"- {p}" for p in retry_feedback),
        ]
    return "\n".join(parts)


def _parse_response(text: str) -> dict[int, float]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON array found in the model's response: {text[:200]!r}")
    data = json.loads(match.group(0))
    return {int(item["index"]): float(item["start_seconds"]) for item in data}


def _resolve_config(provider: str | None):
    """Work out (provider, api_key, model, base_url) from CLI/env, or exit with a clear message."""
    provider = (provider or os.environ.get("LLM_PROVIDER") or "anthropic").lower()

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY")
        model = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("LLM_MODEL") or "claude-sonnet-5"
        base_url = None
        key_hint = "ANTHROPIC_API_KEY (or LLM_API_KEY)"
    else:
        # "openai" itself, or any other OpenAI-compatible chat-completions endpoint.
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        model = os.environ.get("OPENAI_MODEL") or os.environ.get("LLM_MODEL")
        base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("LLM_BASE_URL")
        key_hint = "OPENAI_API_KEY (or LLM_API_KEY)" if provider == "openai" else "LLM_API_KEY"
        if provider == "openai":
            model = model or "gpt-4o"
        elif not base_url:
            sys.exit(
                f"Provider '{provider}' is not built in by name - set LLM_BASE_URL to its "
                "OpenAI-compatible chat-completions endpoint (and LLM_MODEL, LLM_API_KEY)."
            )
        if not model:
            sys.exit(f"No model configured for provider '{provider}'. Set LLM_MODEL (or OPENAI_MODEL).")

    if not api_key:
        sys.exit(
            f"No API key found for provider '{provider}'. Export {key_hint}, e.g.\n"
            f"  export {key_hint.split(' ')[0]}=...\n"
            "before running lrc_sync.py. Set LLM_PROVIDER to switch providers "
            "(anthropic / openai / any OpenAI-compatible name + LLM_BASE_URL)."
        )
    return provider, api_key, model, base_url


def _call_anthropic(api_key: str, model: str, system: str, user: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _call_openai_compatible(api_key: str, model: str, base_url: str | None, system: str, user: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content


def align_lines(sung_lines, transcript, language: str, retry_feedback=None, provider: str | None = None) -> dict[int, float]:
    provider, api_key, model, base_url = _resolve_config(provider)
    user_prompt = _build_user_prompt(sung_lines, transcript, language, retry_feedback)

    if provider == "anthropic":
        text = _call_anthropic(api_key, model, SYSTEM_PROMPT, user_prompt)
    else:
        text = _call_openai_compatible(api_key, model, base_url, SYSTEM_PROMPT, user_prompt)

    return _parse_response(text)

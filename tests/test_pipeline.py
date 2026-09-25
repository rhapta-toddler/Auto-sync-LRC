import pytest

from auto_sync_lrc import cli
from auto_sync_lrc.align import _resolve_config
from auto_sync_lrc.errors import SyncError

LYRICS = "[verse]\n\nHush now baby\nSleep soon\n"


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "probe_duration", lambda _p: 30.0)
    monkeypatch.setattr(cli, "transcribe", lambda *a, **k: object())
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"")
    return mp3


def test_sync_song_writes_lrc_and_logs(monkeypatch, stubbed):
    monkeypatch.setattr(cli, "align_lines", lambda *a, **k: {0: 1.5, 1: 4.0})
    messages = []

    out = cli.sync_song(stubbed, LYRICS, "en", "large-v3", stubbed.with_suffix(".lrc"), log=messages.append)

    assert out.read_text(encoding="utf-8") == "[verse]\n\n[00:01.50] Hush now baby\n[00:04.00] Sleep soon\n"
    assert messages and messages[-1].startswith("Done")


def test_sync_song_rejects_empty_lyrics(stubbed):
    with pytest.raises(SyncError, match="No lyrics"):
        cli.sync_song(stubbed, "[intro]\n\n", "en", "large-v3", stubbed.with_suffix(".lrc"))


def test_sync_song_retries_once_then_succeeds(monkeypatch, stubbed):
    answers = iter([{0: 5.0, 1: 5.0}, {0: 1.0, 1: 2.0}])
    calls = []

    def fake_align(*a, **k):
        calls.append(k.get("retry_feedback"))
        return next(answers)

    monkeypatch.setattr(cli, "align_lines", fake_align)
    cli.sync_song(stubbed, LYRICS, "en", "large-v3", stubbed.with_suffix(".lrc"), log=lambda _m: None)

    assert calls[0] is None and calls[1]


def test_sync_song_refuses_to_write_a_guess(monkeypatch, stubbed):
    monkeypatch.setattr(cli, "align_lines", lambda *a, **k: {0: 5.0, 1: 5.0})
    out = stubbed.with_suffix(".lrc")

    with pytest.raises(SyncError, match="no file was written"):
        cli.sync_song(stubbed, LYRICS, "en", "large-v3", out, log=lambda _m: None)

    assert not out.exists()


def test_missing_api_key_is_a_friendly_error(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SyncError, match="API key"):
        _resolve_config("anthropic")


def test_unknown_provider_needs_a_base_url(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    with pytest.raises(SyncError, match="LLM_BASE_URL"):
        _resolve_config("groq")

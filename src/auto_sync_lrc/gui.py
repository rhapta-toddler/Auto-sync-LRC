"""Point-and-click window for Auto-sync-LRC: no command line needed."""
import json
import os
import queue
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from auto_sync_lrc import __version__
from auto_sync_lrc.errors import SyncError

APP_NAME = "Auto-sync-LRC"

LANGUAGES = [
    ("English", "en"), ("Spanish", "es"), ("French", "fr"), ("German", "de"),
    ("Japanese", "ja"), ("Korean", "ko"), ("Chinese (Mandarin)", "zh"), ("Cantonese", "yue"),
    ("Portuguese", "pt"), ("Russian", "ru"), ("Italian", "it"), ("Arabic", "ar"),
    ("Hindi", "hi"), ("Turkish", "tr"), ("Vietnamese", "vi"), ("Thai", "th"),
    ("Indonesian", "id"), ("Dutch", "nl"), ("Polish", "pl"), ("Ukrainian", "uk"),
]

QUALITY = [
    ("Best quality (slowest, ~3 GB one-time download)", "large-v3"),
    ("Balanced (faster, ~1.5 GB one-time download)", "medium"),
    ("Fast (quickest, ~500 MB one-time download)", "small"),
]

PROVIDERS = [
    ("Claude (Anthropic)", "anthropic"),
    ("ChatGPT (OpenAI)", "openai"),
    ("Other AI service", "custom"),
]

KEY_PAGES = {
    "anthropic": "https://console.anthropic.com/settings/keys",
    "openai": "https://platform.openai.com/api-keys",
}

ENV_NAMES = (
    "LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL",
    "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
    "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL",
)


def config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / APP_NAME / "config.json"


def load_config() -> dict:
    try:
        return json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(data: dict) -> None:
    try:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def apply_env(provider: str, key: str, model: str, base_url: str) -> None:
    for name in ENV_NAMES:
        os.environ.pop(name, None)
    if provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = key
        if model:
            os.environ["ANTHROPIC_MODEL"] = model
    elif provider == "openai":
        os.environ["OPENAI_API_KEY"] = key
        if model:
            os.environ["OPENAI_MODEL"] = model
    else:
        os.environ["LLM_API_KEY"] = key
        os.environ["LLM_MODEL"] = model
        os.environ["LLM_BASE_URL"] = base_url


def reveal_in_folder(path: Path) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("720x700")
        self.minsize(640, 600)
        self.config_data = load_config()
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.output_path: Path | None = None

        self.mp3_var = tk.StringVar(value=self.config_data.get("last_mp3", ""))
        self.language_var = tk.StringVar(value=self.config_data.get("language", "English"))
        self.quality_var = tk.StringVar(value=self.config_data.get("quality", QUALITY[0][0]))
        self.provider_var = tk.StringVar(value=self.config_data.get("provider", PROVIDERS[0][0]))
        self.key_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.base_url_var = tk.StringVar()
        self.show_key_var = tk.BooleanVar(value=False)

        self._build()
        self._load_provider_fields()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)

    # ---- layout ----
    def _build(self) -> None:
        style = ttk.Style(self)
        style.configure("Step.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Go.TButton", font=("Segoe UI", 12, "bold"), padding=8)

        pad = {"padx": 16}
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, pady=12)
        root.columnconfigure(0, weight=1)

        ttk.Label(root, text="1. Choose the song (MP3)", style="Step.TLabel").grid(row=0, column=0, sticky="w", **pad)
        row = ttk.Frame(root)
        row.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 12))
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.mp3_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse...", command=self._browse_mp3).grid(row=0, column=1, padx=(8, 0))

        head = ttk.Frame(root)
        head.grid(row=2, column=0, sticky="ew", **pad)
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="2. Paste the lyrics (one line per sung line)", style="Step.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(head, text="Open a .txt file...", command=self._open_lyrics).grid(row=0, column=1, sticky="e")
        lyr = ttk.Frame(root)
        lyr.grid(row=3, column=0, sticky="nsew", padx=16, pady=(4, 12))
        lyr.columnconfigure(0, weight=1)
        lyr.rowconfigure(0, weight=1)
        root.rowconfigure(3, weight=2)
        self.lyrics = tk.Text(lyr, height=6, wrap="word", font=("Segoe UI", 10), undo=True)
        self.lyrics.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(lyr, command=self.lyrics.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.lyrics.configure(yscrollcommand=scroll.set)

        ttk.Label(root, text="3. Language and quality", style="Step.TLabel").grid(row=5, column=0, sticky="w", **pad)
        opts = ttk.Frame(root)
        opts.grid(row=6, column=0, sticky="ew", padx=16, pady=(4, 12))
        opts.columnconfigure(1, weight=1)
        ttk.Label(opts, text="Language sung:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Combobox(opts, textvariable=self.language_var, values=[n for n, _ in LANGUAGES], state="readonly").grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=2
        )
        ttk.Label(opts, text="Accuracy:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Combobox(opts, textvariable=self.quality_var, values=[n for n, _ in QUALITY], state="readonly").grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=2
        )

        ttk.Label(root, text="4. AI service and your API key", style="Step.TLabel").grid(row=7, column=0, sticky="w", **pad)
        ai = ttk.Frame(root)
        ai.grid(row=8, column=0, sticky="ew", padx=16, pady=(4, 8))
        ai.columnconfigure(1, weight=1)
        ttk.Label(ai, text="Service:").grid(row=0, column=0, sticky="w", pady=2)
        provider_box = ttk.Combobox(ai, textvariable=self.provider_var, values=[n for n, _ in PROVIDERS], state="readonly")
        provider_box.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=2)
        provider_box.bind("<<ComboboxSelected>>", lambda _e: self._load_provider_fields())

        ttk.Label(ai, text="API key:").grid(row=1, column=0, sticky="w", pady=2)
        self.key_entry = ttk.Entry(ai, textvariable=self.key_var, show="*")
        self.key_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Checkbutton(ai, text="Show", variable=self.show_key_var, command=self._toggle_key).grid(
            row=1, column=2, padx=(8, 0)
        )
        self.key_link = ttk.Label(ai, text="", foreground="#0b5cad", cursor="hand2")
        self.key_link.grid(row=2, column=1, sticky="w", padx=(8, 0))
        self.key_link.bind("<Button-1>", lambda _e: self._open_key_page())

        self.model_label = ttk.Label(ai, text="Model name:")
        self.model_entry = ttk.Entry(ai, textvariable=self.model_var)
        self.url_label = ttk.Label(ai, text="Service address:")
        self.url_entry = ttk.Entry(ai, textvariable=self.base_url_var)

        self.start_btn = ttk.Button(root, text="Create synced lyrics", style="Go.TButton", command=self._start)
        self.start_btn.grid(row=9, column=0, sticky="ew", padx=16, pady=(8, 6))
        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.grid(row=10, column=0, sticky="ew", padx=16)

        logf = ttk.Frame(root)
        logf.grid(row=11, column=0, sticky="nsew", padx=16, pady=(8, 0))
        logf.columnconfigure(0, weight=1)
        logf.rowconfigure(0, weight=1)
        root.rowconfigure(11, weight=1)
        self.log = tk.Text(logf, height=3, wrap="word", state="disabled", background="#f4f4f4", font=("Segoe UI", 9))
        self.log.grid(row=0, column=0, sticky="nsew")
        self.show_btn = ttk.Button(root, text="Show the finished .lrc file", command=self._show_output)

    # ---- provider fields ----
    def _provider_id(self) -> str:
        return dict(PROVIDERS).get(self.provider_var.get(), "anthropic")

    def _load_provider_fields(self) -> None:
        pid = self._provider_id()
        saved = self.config_data.get("providers", {}).get(pid, {})
        self.key_var.set(saved.get("key", ""))
        self.model_var.set(saved.get("model", ""))
        self.base_url_var.set(saved.get("base_url", ""))
        self.key_link.configure(text="Where do I get a key?" if pid in KEY_PAGES else "")
        custom = pid == "custom"
        for w in (self.model_label, self.model_entry, self.url_label, self.url_entry):
            w.grid_remove()
        if custom:
            self.model_label.grid(row=3, column=0, sticky="w", pady=2)
            self.model_entry.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=2)
            self.url_label.grid(row=4, column=0, sticky="w", pady=2)
            self.url_entry.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=2)

    def _toggle_key(self) -> None:
        self.key_entry.configure(show="" if self.show_key_var.get() else "*")

    def _open_key_page(self) -> None:
        url = KEY_PAGES.get(self._provider_id())
        if url:
            webbrowser.open(url)

    # ---- file pickers ----
    def _browse_mp3(self) -> None:
        path = filedialog.askopenfilename(title="Choose the song", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.flac *.ogg"), ("All files", "*.*")])
        if path:
            self.mp3_var.set(path)

    def _open_lyrics(self) -> None:
        path = filedialog.askopenfilename(title="Open lyrics", filetypes=[("Text", "*.txt *.md"), ("All files", "*.*")])
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror(APP_NAME, f"Could not read that file:\n{exc}")
            return
        self.lyrics.delete("1.0", "end")
        self.lyrics.insert("1.0", text)

    # ---- running ----
    def _log(self, message: str) -> None:
        self.events.put(("log", message))

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _start(self) -> None:
        if self.busy:
            return
        mp3 = Path(self.mp3_var.get().strip().strip('"'))
        if not mp3.is_file():
            messagebox.showwarning(APP_NAME, "Step 1: choose the song file first.")
            return
        lyrics_text = self.lyrics.get("1.0", "end").strip()
        if not lyrics_text:
            messagebox.showwarning(APP_NAME, "Step 2: paste the lyrics (or open a .txt file).")
            return
        key = self.key_var.get().strip()
        pid = self._provider_id()
        if not key:
            messagebox.showwarning(APP_NAME, "Step 4: paste your API key.")
            return
        model, base_url = self.model_var.get().strip(), self.base_url_var.get().strip()
        if pid == "custom" and not (model and base_url):
            messagebox.showwarning(APP_NAME, "For another AI service, fill in both the model name and the service address.")
            return

        language = dict(LANGUAGES)[self.language_var.get()]
        whisper_model = dict(QUALITY)[self.quality_var.get()]
        if language == "yue" and whisper_model != "large-v3":
            whisper_model = "large-v3"
            self._append_log("Cantonese is only recognised by the Best quality setting, so that will be used.")

        out_path = mp3.with_suffix(".lrc")
        if out_path.exists() and not messagebox.askyesno(APP_NAME, f"{out_path.name} already exists next to the song. Replace it?"):
            return

        saved = self.config_data.setdefault("providers", {})
        saved[pid] = {"key": key, "model": model, "base_url": base_url}
        self.config_data.update(
            provider=self.provider_var.get(), language=self.language_var.get(),
            quality=self.quality_var.get(), last_mp3=str(mp3),
        )
        save_config(self.config_data)

        self.busy = True
        self.output_path = None
        self.show_btn.grid_remove()
        self.start_btn.configure(state="disabled", text="Working... please keep this window open")
        self.progress.start(12)
        threading.Thread(
            target=self._work, args=(mp3, lyrics_text, language, whisper_model, out_path, pid, key, model, base_url), daemon=True
        ).start()

    def _work(self, mp3, lyrics_text, language, whisper_model, out_path, pid, key, model, base_url) -> None:
        try:
            from auto_sync_lrc.cli import sync_song

            apply_env(pid, key, model, base_url)
            result = sync_song(mp3, lyrics_text, language, whisper_model, out_path, provider=pid, log=self._log)
            self.events.put(("done", result))
        except SyncError as exc:
            self.events.put(("error", str(exc)))
        except Exception as exc:  # last-resort: never leave the window stuck
            self.events.put(("error", f"Something unexpected went wrong: {exc}"))

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                else:
                    self._finish(kind, payload)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _finish(self, kind: str, payload) -> None:
        self.busy = False
        self.progress.stop()
        self.start_btn.configure(state="normal", text="Create synced lyrics")
        if kind == "done":
            self.output_path = payload
            self.show_btn.grid(row=12, column=0, sticky="w", padx=16, pady=8)
            messagebox.showinfo(APP_NAME, f"All done!\n\nYour synced lyrics were saved next to the song:\n{payload.name}")
        else:
            self._append_log("Stopped: " + payload)
            messagebox.showerror(APP_NAME, payload)

    def _show_output(self) -> None:
        if self.output_path:
            reveal_in_folder(self.output_path)

    def _on_close(self) -> None:
        if self.busy and not messagebox.askyesno(APP_NAME, "Still working. Quit anyway?"):
            return
        self.destroy()


def selftest(report_path: str) -> int:
    """Used by the build pipeline: proves the packaged app can load every bundled component."""
    lines: list[str] = []
    try:
        import numpy as np
        import av
        import anthropic  # noqa: F401
        import openai  # noqa: F401
        from faster_whisper import WhisperModel

        tk.Tcl().eval("info patchlevel")
        lines.append("imports and Tcl/Tk: ok")

        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language="en")
        list(segments)
        lines.append("whisper model load and transcribe: ok")

        wav = Path(report_path).with_suffix(".wav")
        import wave

        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 32000)
        from auto_sync_lrc.cli import probe_duration

        lines.append(f"audio duration probe: ok ({probe_duration(wav):.1f}s)")
        wav.unlink()
        lines.append("SELFTEST OK")
        code = 0
    except Exception as exc:  # noqa: BLE001
        lines.append(f"SELFTEST FAILED: {type(exc).__name__}: {exc}")
        code = 1
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")
    return code


def main() -> None:
    # A windowed (no-console) build has no stdout/stderr; libraries that print would crash.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        sys.exit(selftest(sys.argv[2]))

    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass
    App().mainloop()


if __name__ == "__main__":
    main()

# Builds the Windows app folder with PyInstaller. Run from the repo root after `pip install . pyinstaller`.
# Output: dist\Auto-sync-LRC\Auto-sync-LRC.exe (the installer script then wraps this folder).
param([string]$DistPath = "dist", [string]$WorkPath = "build")
$ErrorActionPreference = "Stop"

python -m PyInstaller --noconfirm --clean --windowed --name "Auto-sync-LRC" `
    --distpath $DistPath --workpath $WorkPath --specpath $WorkPath `
    --hidden-import auto_sync_lrc.cli --hidden-import auto_sync_lrc.align --hidden-import auto_sync_lrc.transcribe `
    --collect-all faster_whisper --collect-all ctranslate2 --collect-all av `
    --collect-all onnxruntime --collect-all tokenizers `
    --collect-all anthropic --collect-all openai `
    --exclude-module torch --exclude-module torchaudio --exclude-module scipy --exclude-module numba `
    --exclude-module llvmlite --exclude-module boto3 --exclude-module botocore --exclude-module imageio_ffmpeg `
    --exclude-module matplotlib --exclude-module pandas --exclude-module PIL --exclude-module IPython `
    packaging/gui_entry.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

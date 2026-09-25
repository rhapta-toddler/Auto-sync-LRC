# One-command native setup for Windows: creates a virtualenv,
# installs Auto-sync-LRC into it, and writes a .env with your chosen LLM
# provider's API key. Run from the repo root: .\install.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Creating virtual environment in .venv ..."
python -m venv .venv
& .\.venv\Scripts\Activate.ps1

Write-Host "Installing Auto-sync-LRC ..."
pip install --quiet --upgrade pip
pip install --quiet -e .

if (-not (Test-Path .env)) {
    Write-Host ""
    Write-Host "Which LLM provider should do the text-alignment step?"
    Write-Host "  1) Anthropic (default)"
    Write-Host "  2) OpenAI"
    Write-Host "  3) Another OpenAI-compatible endpoint (Groq, DeepSeek, a local server, ...)"
    $choice = Read-Host "Choice [1]"
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }

    switch ($choice) {
        "2" {
            $apiKey = Read-Host "OPENAI_API_KEY"
            @"
LLM_PROVIDER=openai
OPENAI_API_KEY=$apiKey
"@ | Set-Content -Encoding utf8 .env
        }
        "3" {
            $provider = Read-Host "Provider name (e.g. groq)"
            $apiKey = Read-Host "LLM_API_KEY"
            $model = Read-Host "LLM_MODEL"
            $baseUrl = Read-Host "LLM_BASE_URL"
            @"
LLM_PROVIDER=$provider
LLM_API_KEY=$apiKey
LLM_MODEL=$model
LLM_BASE_URL=$baseUrl
"@ | Set-Content -Encoding utf8 .env
        }
        default {
            $apiKey = Read-Host "ANTHROPIC_API_KEY"
            @"
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=$apiKey
"@ | Set-Content -Encoding utf8 .env
        }
    }
    Write-Host "Wrote .env"
} else {
    Write-Host ".env already exists - leaving it as-is."
}

Write-Host ""
Write-Host "Setup complete. Activate the environment in new shells with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Then run, e.g.:"
Write-Host "  auto-sync-lrc song.mp3 lyrics.txt --language en"

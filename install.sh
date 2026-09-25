#!/usr/bin/env bash
# One-command native setup for macOS/Linux/WSL: creates a
# virtualenv, installs Auto-sync-LRC into it, and writes a .env with your
# chosen LLM provider's API key. Run it from the repo root: ./install.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "Creating virtual environment in .venv ..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing Auto-sync-LRC ..."
pip install --quiet --upgrade pip
pip install --quiet -e .

if [ ! -f .env ]; then
    echo
    echo "Which LLM provider should do the text-alignment step?"
    echo "  1) Anthropic (default)"
    echo "  2) OpenAI"
    echo "  3) Another OpenAI-compatible endpoint (Groq, DeepSeek, a local server, ...)"
    read -rp "Choice [1]: " choice
    choice="${choice:-1}"

    case "$choice" in
        2)
            read -rp "OPENAI_API_KEY: " api_key
            {
                echo "LLM_PROVIDER=openai"
                echo "OPENAI_API_KEY=$api_key"
            } > .env
            ;;
        3)
            read -rp "Provider name (e.g. groq): " provider
            read -rp "LLM_API_KEY: " api_key
            read -rp "LLM_MODEL: " model
            read -rp "LLM_BASE_URL: " base_url
            {
                echo "LLM_PROVIDER=$provider"
                echo "LLM_API_KEY=$api_key"
                echo "LLM_MODEL=$model"
                echo "LLM_BASE_URL=$base_url"
            } > .env
            ;;
        *)
            read -rp "ANTHROPIC_API_KEY: " api_key
            {
                echo "LLM_PROVIDER=anthropic"
                echo "ANTHROPIC_API_KEY=$api_key"
            } > .env
            ;;
    esac
    echo "Wrote .env"
else
    echo ".env already exists - leaving it as-is."
fi

echo
echo "Setup complete. Activate the environment in new shells with:"
echo "  source .venv/bin/activate"
echo "Then run, e.g.:"
echo "  auto-sync-lrc song.mp3 lyrics.txt --language en"

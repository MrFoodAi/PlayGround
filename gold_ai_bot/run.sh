#!/usr/bin/env bash
# Avvio del GoldAI XAU Bot (modalità paper trading di default)
set -e

cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "Creazione ambiente virtuale..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo "Avvio GoldAI XAU Bot con dashboard su http://localhost:8080"
python -m src.dashboard.app

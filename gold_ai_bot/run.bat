@echo off
cd /d "%~dp0"

if not exist venv (
  echo Creazione ambiente virtuale...
  python -m venv venv
)

call venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo Avvio GoldAI XAU Bot con dashboard su http://localhost:8080
python -m src.dashboard.app

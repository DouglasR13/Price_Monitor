@echo off
title Price Monitor Bot - Servidor e Painel Web
echo =====================================================================
echo           PriceRadar AI - Monitor de Precos Inteligente
echo =====================================================================
echo.
cd /d "%~dp0backend"

echo [1/2] Iniciando o servidor FastAPI e Painel Web...
start http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause

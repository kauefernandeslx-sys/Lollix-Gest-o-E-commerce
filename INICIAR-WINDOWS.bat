@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Criando ambiente Python...
  python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Nao foi possivel instalar as dependencias. Verifique sua conexao e a instalacao do Python.
  pause
  exit /b 1
)
echo.
echo LOLLIX GESTAO sera iniciado. Abra http://127.0.0.1:5000 no navegador.
echo Para encerrar, pressione Ctrl+C nesta janela.
python app.py
pause

@echo off
REM Corre la aplicacion sin compilar (modo desarrollo)
cd /d "%~dp0"
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
REM Se corre siempre, no solo al crear el .venv: si requirements.txt
REM cambio despues (una dependencia nueva, una version distinta), un
REM .venv que ya existia se quedaba desactualizado sin avisar. pip no
REM reinstala lo que ya esta al dia, asi que este paso de mas es rapido.
pip install -r requirements.txt --quiet
set PYTHONPATH=%CD%\src
python -m spamed
pause
